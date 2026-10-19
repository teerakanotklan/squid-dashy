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
    """Background worker that updates stats every 2 seconds from real Squid"""
    while True:
        try:
            await asyncio.to_thread(monitor.tick)
        except Exception as e:
            print(f"Error in metrics worker: {e}")
        await asyncio.sleep(2.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_task
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

@app.get("/api/squidmgr/{action}")
async def query_cache_manager(action: str):
    valid_actions = ["info", "5min", "utilization", "client_list", "ipcache", "counters", "filedescriptors"]
    if action not in valid_actions and not action.isalnum():
        return JSONResponse(status_code=400, content={"error": "Invalid action"})
    
    output = await asyncio.to_thread(monitor.query_squid_mgr, action)
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
