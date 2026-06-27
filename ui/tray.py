"""
ui/tray.py — System tray icon.

Menu:
  Open Dashboard  — opens http://localhost:3000 in the default browser
  Mute JARVIS     — toggles TTS mute
  Quit            — gracefully shuts down all services

Uses pystray for cross-platform tray support.
Requires Pillow for the icon image.
"""

import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.tray")

UI_PORT = int(os.getenv("JARVIS_UI_PORT", "3000"))


def _make_icon():
    """Generate a simple JARVIS-blue circle icon."""
    try:
        from PIL import Image, ImageDraw

        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Outer circle — steel blue
        draw.ellipse([2, 2, size - 2, size - 2], fill="#1565C0")
        # Inner ring
        draw.ellipse([10, 10, size - 10, size - 10], outline="#4FC3F7", width=3)
        # Centre dot
        draw.ellipse([26, 26, size - 26, size - 26], fill="#4FC3F7")

        return img
    except ImportError:
        logger.warning("Pillow not installed — tray icon will be blank.")
        from PIL import Image
        return Image.new("RGB", (64, 64), color=(21, 101, 192))


def _open_dashboard(icon, item):
    webbrowser.open(f"http://localhost:{UI_PORT}")


def _toggle_mute(icon, item):
    try:
        from voice.speaker import get_speaker
        speaker = get_speaker()
        if speaker.is_muted:
            speaker.unmute()
            logger.info("JARVIS unmuted via tray.")
        else:
            speaker.mute()
            logger.info("JARVIS muted via tray.")
    except Exception as e:
        logger.error("Mute toggle error: %s", e)


def _quit(icon, item):
    logger.info("Quit requested from system tray.")
    icon.stop()
    # Give a moment for cleanup, then hard-exit
    threading.Timer(0.5, lambda: os._exit(0)).start()


def start():
    """Start the system tray icon (blocking — run in a daemon thread)."""
    try:
        import pystray
        from pystray import MenuItem as Item, Menu

        menu = Menu(
            Item("Open Dashboard", _open_dashboard, default=True),
            Menu.SEPARATOR,
            Item("Mute JARVIS", _toggle_mute),
            Menu.SEPARATOR,
            Item("Quit", _quit),
        )

        icon = pystray.Icon(
            name="jarvis",
            icon=_make_icon(),
            title="JARVIS",
            menu=menu,
        )

        logger.info("System tray icon ready.")
        icon.run()   # blocks until icon.stop() is called

    except ImportError:
        logger.warning("pystray not installed — system tray disabled.")
    except Exception as e:
        logger.error("Tray error: %s", e)
