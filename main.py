"""
main.py — JARVIS entry point.

Starts all services in parallel daemon threads:
  1. Voice listener (always-on mic + Whisper STT)
  2. MCP tool server      (ws://localhost:8765)
  3. REST/WebSocket API   (http://localhost:8000)
  4. System tray icon
  5. Background scheduler

After starting all services, drops into an interactive text loop so the
user can also type commands directly in the terminal.
"""

import logging
import logging.handlers
import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Bootstrap — load .env and configure logging BEFORE importing anything else
# ---------------------------------------------------------------------------

load_dotenv()

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            LOG_DIR / "jarvis.log",
            maxBytes=5 * 1024 * 1024,   # 5 MB
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger("jarvis")


# ---------------------------------------------------------------------------
# Sanity check
# ---------------------------------------------------------------------------

def _check_api_key():
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key == "your_claude_api_key_here":
        logger.warning("=" * 60)
        logger.warning("ANTHROPIC_API_KEY is not set!")
        logger.warning("Edit your .env file and add: ANTHROPIC_API_KEY=sk-ant-...")
        logger.warning("JARVIS will start but the AI brain will not function.")
        logger.warning("=" * 60)


# ---------------------------------------------------------------------------
# Service threads
# ---------------------------------------------------------------------------

def _start_voice_listener(agent_run_fn):
    """Start the always-on microphone listener."""
    try:
        from voice.listener import get_listener
        from voice.wake_word import start_detection

        listener = get_listener(on_text=agent_run_fn)

        # Wire up: wake word → start listening
        def _on_wake():
            listener.trigger_listen()

        start_detection(_on_wake)

        # Start the listener loop (blocks)
        listener.start()
    except Exception as e:
        logger.error("Voice listener error: %s", e, exc_info=True)


def _start_mcp_server():
    """Start the MCP tool server on port 8765."""
    try:
        import yaml
        cfg_path = Path(__file__).parent / "config.yaml"
        port = 8765
        try:
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            port = cfg.get("server", {}).get("mcp_port", 8765)
        except FileNotFoundError:
            pass

        from mcp.server import start as mcp_start
        mcp_start(port=port)
    except Exception as e:
        logger.error("MCP server error: %s", e, exc_info=True)


def _start_api_server():
    """Start the FastAPI REST + WebSocket server on port 8000."""
    try:
        import yaml
        cfg_path = Path(__file__).parent / "config.yaml"
        port = 8000
        try:
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            port = cfg.get("server", {}).get("api_port", 8000)
        except FileNotFoundError:
            pass

        from api.server import start as api_start
        api_start(port=port)
    except Exception as e:
        logger.error("API server error: %s", e, exc_info=True)


def _start_tray():
    try:
        from ui.tray import start as tray_start
        tray_start()
    except Exception as e:
        logger.debug("Tray icon unavailable: %s", e)


def _start_scheduler():
    try:
        from core.scheduler import get_scheduler
        scheduler = get_scheduler()
        scheduler.start()   # blocks
    except Exception as e:
        logger.error("Scheduler error: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# Response handler — speak + print every JARVIS response
# ---------------------------------------------------------------------------

def _handle_response(text: str):
    """Print and optionally speak a JARVIS response."""
    print(f"\n[JARVIS] {text}\n")
    try:
        from voice.speaker import speak
        speak(text)
    except Exception:
        pass   # TTS is optional


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("  J.A.R.V.I.S  —  Starting up")
    logger.info("=" * 60)

    _check_api_key()

    # Purge old trash on startup
    try:
        from tools.filesystem import purge_old_trash
        result = purge_old_trash()
        logger.info(result)
    except Exception:
        pass

    # Pre-load the agent (validates API key, builds tools)
    from core.agent import get_agent
    agent = get_agent()

    def _agent_respond(text: str):
        """Called by voice listener OR terminal input."""
        response = agent.run(text)
        _handle_response(response)

    # -----------------------------------------------------------------------
    # Launch service threads
    # -----------------------------------------------------------------------

    threads = [
        threading.Thread(target=_start_voice_listener, args=(_agent_respond,), name="voice-listener", daemon=True),
        threading.Thread(target=_start_mcp_server,    name="mcp-server",       daemon=True),
        threading.Thread(target=_start_api_server,    name="api-server",       daemon=True),
        threading.Thread(target=_start_tray,           name="tray-icon",        daemon=True),
        threading.Thread(target=_start_scheduler,     name="scheduler",        daemon=True),
    ]

    for t in threads:
        t.start()
        logger.info("Started thread: %s", t.name)

    logger.info("-" * 60)
    logger.info("Dashboard: http://localhost:3000")
    logger.info("API:       http://localhost:8000")
    logger.info("MCP:       ws://localhost:8765/mcp")
    logger.info("-" * 60)
    print('\n[JARVIS] All systems online. Type your commands below, or say "Hey JARVIS".')
    print('[JARVIS] Type "quit" or "exit" to shut down.\n')

    # -----------------------------------------------------------------------
    # Interactive terminal input loop (main thread)
    # -----------------------------------------------------------------------

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "bye", "shutdown"):
                print("[JARVIS] Shutting down. Goodbye, sir.")
                break

            _agent_respond(user_input)

    except KeyboardInterrupt:
        print("\n[JARVIS] Interrupted. Shutting down.")

    logger.info("JARVIS shutdown complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
