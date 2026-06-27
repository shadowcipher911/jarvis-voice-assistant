"""
mcp/server.py — Model Context Protocol tool server.

Exposes all JARVIS tools as an MCP server on localhost:8765.
Compatible with Claude Desktop, Continue.dev, Cursor, and any MCP client.

Transport: WebSocket (JSON-RPC 2.0 style messages).

Protocol summary:
  Client → Server:  {"id": 1, "method": "tools/list"}
  Client → Server:  {"id": 2, "method": "tools/call", "params": {"name": "filesystem.read_file", "arguments": {"path": "..."}}}
  Server → Client:  {"id": 1, "result": [...]}
  Server → Client:  {"id": 2, "result": {"content": [{"type": "text", "text": "..."}]}}
"""

import json
import logging
import os
import traceback
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from mcp.registry import get_registry

logger = logging.getLogger("jarvis.mcp")

app = FastAPI(title="JARVIS MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REST endpoint — health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    registry = get_registry()
    return {"status": "ok", "tools": len(registry.list_schemas())}


@app.get("/tools")
def list_tools_rest():
    """REST endpoint to list all available tools (for debugging)."""
    return get_registry().list_schemas()


# ---------------------------------------------------------------------------
# WebSocket MCP handler
# ---------------------------------------------------------------------------

@app.websocket("/mcp")
async def mcp_endpoint(websocket: WebSocket):
    await websocket.accept()
    client = websocket.client
    logger.info("MCP client connected: %s:%s", client.host if client else "?", client.port if client else "?")

    registry = get_registry()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "error": {"code": -32700, "message": "Parse error"}
                }))
                continue

            msg_id = message.get("id")
            method = message.get("method", "")
            params = message.get("params", {})

            response = await _handle_message(method, params, registry)
            await websocket.send_text(json.dumps({"id": msg_id, **response}))

    except WebSocketDisconnect:
        logger.info("MCP client disconnected.")
    except Exception as e:
        logger.error("MCP WebSocket error: %s", e)


async def _handle_message(method: str, params: dict, registry) -> dict:
    """Route an MCP message to the appropriate handler."""

    if method == "initialize":
        return {
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "jarvis", "version": "1.0.0"},
            }
        }

    if method == "tools/list":
        return {"result": {"tools": registry.list_schemas()}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        return await _call_tool(tool_name, arguments, registry)

    if method == "ping":
        return {"result": {}}

    return {"error": {"code": -32601, "message": f"Method not found: {method}"}}


async def _call_tool(tool_name: str, arguments: dict, registry) -> dict:
    """Execute a tool and format the result as an MCP content block."""
    try:
        result = registry.call(tool_name, arguments)
        text = str(result) if not isinstance(result, str) else result
        return {
            "result": {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            }
        }
    except KeyError as e:
        return {
            "result": {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True,
            }
        }
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Tool '%s' error: %s", tool_name, tb)
        return {
            "result": {
                "content": [{"type": "text", "text": f"Tool error: {e}"}],
                "isError": True,
            }
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def start(host: str = "localhost", port: int = 8765):
    """Start the MCP WebSocket server (blocking)."""
    logger.info("MCP server starting on ws://%s:%d/mcp", host, port)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    start()
