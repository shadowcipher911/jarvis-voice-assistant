"""
api/server.py — FastAPI REST + WebSocket server for the dashboard.

Endpoints:
  GET  /api/health          — liveness check
  POST /api/chat            — send a message to JARVIS
  GET  /api/history         — recent conversation history
  GET  /api/activity        — current tool activity
  GET  /api/config          — read config.yaml
  POST /api/config          — write config.yaml
  POST /api/restart         — signal a restart (exits main.py)
  POST /api/memory/clear    — clear session context
  GET  /api/memory/facts    — all stored facts
  GET  /api/memory/pinned   — pinned memories
  POST /api/memory/search   — semantic memory search
  WS   /ws/logs             — live log stream
"""

import asyncio
import json
import logging
import os
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger("jarvis.api")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="JARVIS API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the built React dashboard at "/"
DASHBOARD_DIST = Path(__file__).parent.parent / "ui" / "dashboard" / "dist"
if DASHBOARD_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(DASHBOARD_DIST / "assets")), name="assets")

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

# ---------------------------------------------------------------------------
# Log forwarding queue — filled by LogQueueHandler
# ---------------------------------------------------------------------------

_log_queue: queue.Queue = queue.Queue(maxsize=1000)
_ws_clients: list[WebSocket] = []
_tool_activity = {"active_tool": None, "recent": [], "stats": {"total_calls": 0}}
_activity_lock = threading.Lock()


class LogQueueHandler(logging.Handler):
    """Pushes formatted log records into the in-memory queue."""
    def emit(self, record):
        try:
            msg = self.format(record)
            _log_queue.put_nowait(msg)
        except Exception:
            pass


def install_log_handler():
    """Attach the queue handler to the root logger."""
    handler = LogQueueHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger("jarvis").addHandler(handler)


# ---------------------------------------------------------------------------
# Activity tracking helpers (called by agent.py)
# ---------------------------------------------------------------------------

def set_active_tool(name: str, input_str: str = ""):
    with _activity_lock:
        _tool_activity["active_tool"] = {
            "name": name, "input": input_str,
            "timestamp": datetime.now().isoformat()
        }


def clear_active_tool(name: str, status: str = "done"):
    with _activity_lock:
        _tool_activity["active_tool"] = None
        recent = _tool_activity["recent"]
        recent.insert(0, {
            "name": name, "status": status,
            "timestamp": datetime.now().isoformat()
        })
        _tool_activity["recent"] = recent[:20]
        _tool_activity["stats"]["total_calls"] = _tool_activity["stats"].get("total_calls", 0) + 1


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
def chat(req: ChatRequest):
    from core.agent import get_agent
    agent = get_agent()
    response = agent.run(req.message)
    return {"response": response}


@app.get("/api/history")
def history():
    from core.memory import get_memory
    mem = get_memory()
    return {"history": mem.get_history(limit=100)}


@app.get("/api/activity")
def activity():
    with _activity_lock:
        return dict(_tool_activity)


@app.get("/api/config")
def get_config():
    try:
        content = CONFIG_PATH.read_text(encoding="utf-8")
        return {"content": content}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


class ConfigBody(BaseModel):
    content: str


@app.post("/api/config")
def save_config(body: ConfigBody):
    try:
        # Validate YAML before saving
        yaml.safe_load(body.content)
        CONFIG_PATH.write_text(body.content, encoding="utf-8")
        return {"status": "saved"}
    except yaml.YAMLError as e:
        return JSONResponse(status_code=400, content={"detail": f"Invalid YAML: {e}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


@app.post("/api/restart")
def restart():
    import sys
    threading.Thread(target=lambda: (asyncio.sleep(0.5), os.execv(sys.executable, [sys.executable] + sys.argv)), daemon=True).start()
    return {"status": "restarting"}


@app.post("/api/memory/clear")
def clear_session():
    from core.context import reset_context
    reset_context()
    return {"status": "session cleared"}


@app.get("/api/memory/facts")
def memory_facts():
    from core.memory import get_memory
    return {"facts": get_memory().get_all_facts()}


@app.get("/api/memory/pinned")
def memory_pinned():
    from core.memory import get_memory
    return {"pinned": get_memory().get_pinned()}


class SearchBody(BaseModel):
    query: str
    top_k: int = 5


@app.post("/api/memory/search")
def memory_search(body: SearchBody):
    from core.memory import get_memory
    results = get_memory().search(body.query, top_k=body.top_k)
    return {"results": results}


# ---------------------------------------------------------------------------
# Static file fallback for React SPA routing
# ---------------------------------------------------------------------------

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    index = DASHBOARD_DIST / "index.html"
    if index.exists():
        from fastapi.responses import FileResponse
        return FileResponse(str(index))
    return JSONResponse({"error": "Dashboard not built. Run: cd ui/dashboard && npm run build"})


# ---------------------------------------------------------------------------
# WebSocket — live log stream
# ---------------------------------------------------------------------------

@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    logger.info("Log WebSocket client connected.")
    try:
        while True:
            # Drain the log queue and broadcast to this client
            try:
                msg = _log_queue.get_nowait()
                await websocket.send_text(msg)
            except queue.Empty:
                await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def start(host: str = "0.0.0.0", port: int = 8000):
    install_log_handler()
    logger.info("API server starting on http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    start()
