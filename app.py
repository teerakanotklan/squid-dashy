import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import config
from squid_service import monitor

background_task = None

async def metrics_worker():
    """Background worker that updates stats every 2 seconds"""
    while True:
        try:
            monitor.tick()
        except Exception as e:
            print(f"Error in metrics worker: {e}")
        await asyncio.sleep(2.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_task
    # Prefill some demo data if demo mode is active so dashboard looks rich immediately
    if monitor.is_demo_mode or not os.path.exists(config.SQUID_ACCESS_LOG):
        for _ in range(30):
            monitor.tick()
    background_task = asyncio.create_task(metrics_worker())
    yield
    if background_task:
        background_task.cancel()

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

@app.post("/api/mode/toggle")
async def toggle_demo_mode():
    monitor.is_demo_mode = not monitor.is_demo_mode
    return {"is_demo_mode": monitor.is_demo_mode}

@app.get("/api/squidmgr/{action}")
async def query_cache_manager(action: str):
    valid_actions = ["info", "5min", "utilization", "client_list", "ipcache", "counters", "filedescriptors"]
    if action not in valid_actions and not action.isalnum():
        return JSONResponse(status_code=400, content={"error": "Invalid action"})
    
    if monitor.is_demo_mode:
        sample_output = f"""Squid Object Cache: Version 6.6 (Demo Mode)
Build Info: Linux 6.1.0-x86_64
Start Time: Mon, 19 Oct 2026 22:00:00 GMT
Current Time: {asyncio.get_event_loop().time()}
Connection information for squid:
    Number of HTTP requests received:          {monitor.total_requests}
    Number of ICP messages received:           0
    Number of ICP messages sent:               0
    Number of queued ICP replies:              0
    Number of HTCP messages received:          0
    Number of HTCP messages sent:              0
    Request failure ratio:                     0.00
    Average HTTP requests per minute:          {round(monitor.metrics['req_per_sec'] * 60, 1)}
    Average ICP messages per minute:           0.0
    Select loop called:                        89234 times, 2.12 ms avg
Cache information for squid:
    Hits as % of all requests:                 5min: {monitor.get_summary_state()['kpi']['req_hit_pct']}%, 60min: {monitor.get_summary_state()['kpi']['req_hit_pct']}%
    Hits as % of bytes sent:                   5min: {monitor.get_summary_state()['kpi']['byte_hit_pct']}%, 60min: {monitor.get_summary_state()['kpi']['byte_hit_pct']}%
    Memory cache hits as % of hit requests:    5min: 42.1%
    Storage Swap size:                         {int(monitor.metrics['disk_cache_used_mb'] * 1024)} KB
    Storage Mem size:                          {int(monitor.metrics['memory_used_mb'] * 1024)} KB
    Mean Object Size:                          34.82 KB
Resource usage for squid:
    UP Time:                                   {monitor.uptime_seconds} seconds
    CPU Time:                                  {round(monitor.uptime_seconds * 0.05, 2)} seconds
    CPU Usage:                                 {monitor.metrics['cpu_usage_pct']}%
    Maximum Resident Size:                     {int(monitor.metrics['memory_used_mb'] * 1024)} KB
    Page faults with physical i/o:             12
    Number of file desc currently in use:      {monitor.metrics['file_descriptors_used']}
    Available number of file descriptors:      {monitor.metrics['file_descriptors_max']}
    Reserved number of file descriptors:       100
"""
        return {"action": action, "output": sample_output}
    
    output = monitor.query_squid_mgr(action)
    return {"action": action, "output": output}

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
