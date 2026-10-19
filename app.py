import asyncio
import os
from contextlib import asynccontextmanager
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import config
from squid_service import monitor
from domain_blocker import domain_blocker
from retention_manager import retention_manager

class BlockDomainRequest(BaseModel):
    domain: str

metrics_task = None
retention_task = None

async def metrics_worker():
    """Background worker that updates stats every 2 seconds and saves periodic snapshots"""
    tick_count = 0
    while True:
        try:
            await asyncio.to_thread(monitor.tick)
            tick_count += 1
            # Save daily aggregated snapshot to SQLite every ~60 seconds (30 ticks)
            if tick_count % 30 == 0:
                state = monitor.get_summary_state()
                await asyncio.to_thread(retention_manager.save_daily_metrics, state)
        except Exception as e:
            print(f"Error in metrics worker: {e}")
        await asyncio.sleep(2.0)

async def retention_worker():
    """Runs Graylog-style retention pipeline (archive > consolidate > purge > prune) every hour"""
    # Initial run after 10 seconds of startup
    await asyncio.sleep(10.0)
    while True:
        try:
            logs_copy = list(monitor.recent_logs)
            await asyncio.to_thread(retention_manager.run_full_lifecycle, logs_copy)
        except Exception as e:
            print(f"Error in retention worker: {e}")
        await asyncio.sleep(3600.0) # Run every hour

@asynccontextmanager
async def lifespan(app: FastAPI):
    global metrics_task, retention_task
    metrics_task = asyncio.create_task(metrics_worker())
    retention_task = asyncio.create_task(retention_worker())
    yield
    if metrics_task:
        metrics_task.cancel()
    if retention_task:
        retention_task.cancel()

app = FastAPI(title="Squid Proxy Monitor", lifespan=lifespan)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/api/stats")
async def get_stats():
    return monitor.get_summary_state()

@app.get("/api/logs")
async def get_logs(
    search: str = Query(None), 
    filter_type: str = Query("ALL"), # ALL, HIT, MISS, DENIED
    limit: int = Query(100, le=500)
):
    logs = list(monitor.recent_logs)
    if search:
        search_lower = search.lower()
        logs = [
            l for l in logs 
            if search_lower in l["client_ip"].lower() 
            or search_lower in l["domain"].lower() 
            or search_lower in l["result_code"].lower()
            or search_lower in l["url"].lower()
        ]
    
    if filter_type == "HIT":
        logs = [l for l in logs if l["is_hit"]]
    elif filter_type == "MISS":
        logs = [l for l in logs if not l["is_hit"] and not l["is_denied"]]
    elif filter_type == "DENIED":
        logs = [l for l in logs if l["is_denied"]]
        
    return {"logs": logs[-limit:]}

@app.get("/api/squidmgr/{action}")
async def query_cache_manager(action: str):
    valid_actions = ["info", "5min", "utilization", "client_list", "ipcache", "counters", "filedescriptors"]
    if action not in valid_actions and not action.isalnum():
        return JSONResponse(status_code=400, content={"error": "Invalid action"})
    
    output = await asyncio.to_thread(monitor.query_squid_mgr, action)
    return {"action": action, "output": output}

# --- Domain Blocking Endpoints ---
@app.get("/api/blocked-domains")
async def get_blocked_domains():
    return domain_blocker.get_blocked_domains()

@app.post("/api/blocked-domains")
async def add_blocked_domain(req: BlockDomainRequest):
    result = await asyncio.to_thread(domain_blocker.add_domain, req.domain)
    if not result.get("success"):
        return JSONResponse(status_code=400, content=result)
    return result

@app.delete("/api/blocked-domains/{domain:path}")
async def remove_blocked_domain(domain: str):
    result = await asyncio.to_thread(domain_blocker.remove_domain, domain)
    if not result.get("success"):
        return JSONResponse(status_code=400, content=result)
    return result

@app.post("/api/blocked-domains/reconfigure")
async def reconfigure_squid():
    result = await asyncio.to_thread(domain_blocker.reconfigure_squid)
    return result

# --- 365-Day Metrics & Graylog-style Retention Endpoints ---
@app.get("/api/history/metrics")
async def get_historical_metrics(days: int = Query(30, ge=1, le=365)):
    # Save current live state before querying
    state = monitor.get_summary_state()
    await asyncio.to_thread(retention_manager.save_daily_metrics, state)
    return await asyncio.to_thread(retention_manager.get_historical_metrics, days)

@app.get("/api/history/retention-status")
async def get_retention_status():
    return await asyncio.to_thread(retention_manager.get_retention_overview)

@app.post("/api/history/run-maintenance")
async def trigger_maintenance():
    logs_copy = list(monitor.recent_logs)
    state = monitor.get_summary_state()
    await asyncio.to_thread(retention_manager.save_daily_metrics, state)
    result = await asyncio.to_thread(retention_manager.run_full_lifecycle, logs_copy)
    return result

@app.get("/api/system/info")
async def get_system_info():
    return {
        "dashboard": {
            "host": config.HOST,
            "port": config.PORT,
            "version": "1.2.0"
        },
        "squid": {
            "host": config.SQUID_HOST,
            "port": config.SQUID_PORT,
            "access_log": config.SQUID_ACCESS_LOG,
            "access_log_exists": os.path.exists(config.SQUID_ACCESS_LOG),
            "blocked_domains_file": config.SQUID_BLOCKED_DOMAINS_FILE,
            "blocked_domains_exists": os.path.exists(config.SQUID_BLOCKED_DOMAINS_FILE),
            "reconfigure_cmd": config.SQUID_RECONFIGURE_CMD,
            "alive": monitor.squid_alive,
            "version": monitor.squid_version
        },
        "retention": {
            "data_dir": config.DATA_DIR,
            "metrics_days": config.METRICS_RETENTION_DAYS,
            "archive_days": config.LOG_ARCHIVE_DAYS,
            "consolidation_days": config.LOG_CONSOLIDATION_DAYS,
            "purge_days": config.LOG_PURGE_DAYS
        }
    }


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            state = monitor.get_summary_state()
            await websocket.send_json(state)
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=config.HOST, port=config.PORT, reload=False)
