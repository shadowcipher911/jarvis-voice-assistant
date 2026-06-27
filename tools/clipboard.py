"""
tools/clipboard.py — Read and write the system clipboard.
"""

import logging

import pyperclip

logger = logging.getLogger("jarvis.clipboard")


def get_clipboard() -> str:
    """Return the current clipboard text content."""
    try:
        content = pyperclip.paste()
        if not content:
            return "(Clipboard is empty)"
        logger.debug("Clipboard read: %d chars", len(content))
        return content
    except Exception as e:
        return f"ERROR reading clipboard: {e}"


def set_clipboard(text: str) -> str:
    """Write text to the system clipboard."""
    try:
        pyperclip.copy(text)
        logger.debug("Clipboard written: %d chars", len(text))
        return f"Clipboard updated ({len(text)} characters)."
    except Exception as e:
        return f"ERROR writing clipboard: {e}"


def clear_clipboard() -> str:
    """Clear the clipboard."""
    try:
        pyperclip.copy("")
        return "Clipboard cleared."
    except Exception as e:
        return f"ERROR clearing clipboard: {e}"
