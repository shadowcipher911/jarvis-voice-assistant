"""
core/context.py — Session context manager.

Tracks the live state of the current JARVIS session so the agent always
knows what it opened, touched, or is waiting on.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class SessionContext:
    """Mutable session state shared across all JARVIS modules."""

    active_task: Optional[str] = None          # current task description
    open_apps: list[str] = field(default_factory=list)   # apps opened this session
    last_file: Optional[str] = None            # last file path touched
    last_url: Optional[str] = None             # last URL visited
    conversation_history: list[dict] = field(default_factory=list)  # full chat log
    pending_confirmations: list[dict] = field(default_factory=list) # awaiting yes/no
    muted: bool = False                        # TTS mute flag
    session_start: str = field(default_factory=lambda: datetime.now().isoformat())
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    # -----------------------------------------------------------------------
    # Conversation helpers
    # -----------------------------------------------------------------------

    def add_message(self, role: str, content: str) -> None:
        """Append a message to the in-session conversation log."""
        with self._lock:
            self.conversation_history.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            })

    def get_recent_messages(self, n: int = 20) -> list[dict]:
        """Return the last n messages from this session."""
        with self._lock:
            return self.conversation_history[-n:]

    # -----------------------------------------------------------------------
    # App tracking
    # -----------------------------------------------------------------------

    def register_app_open(self, app_name: str) -> None:
        with self._lock:
            if app_name not in self.open_apps:
                self.open_apps.append(app_name)

    def register_app_close(self, app_name: str) -> None:
        with self._lock:
            self.open_apps = [a for a in self.open_apps if a.lower() != app_name.lower()]

    # -----------------------------------------------------------------------
    # Confirmation queue
    # -----------------------------------------------------------------------

    def request_confirmation(self, action: str, details: Any = None) -> str:
        """Queue an action for user confirmation. Returns a confirmation ID."""
        import uuid
        conf_id = str(uuid.uuid4())[:8]
        with self._lock:
            self.pending_confirmations.append({
                "id": conf_id,
                "action": action,
                "details": details,
            })
        return conf_id

    def confirm(self, conf_id: str) -> Optional[dict]:
        """Remove and return a pending confirmation by ID."""
        with self._lock:
            for i, c in enumerate(self.pending_confirmations):
                if c["id"] == conf_id:
                    return self.pending_confirmations.pop(i)
        return None

    def clear_confirmations(self) -> None:
        with self._lock:
            self.pending_confirmations.clear()

    # -----------------------------------------------------------------------
    # Serialisation (for dashboard / debug)
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "active_task": self.active_task,
            "open_apps": self.open_apps,
            "last_file": self.last_file,
            "last_url": self.last_url,
            "muted": self.muted,
            "session_start": self.session_start,
            "pending_confirmations": len(self.pending_confirmations),
            "message_count": len(self.conversation_history),
        }


# Module-level singleton — one context per process lifetime
_ctx: Optional[SessionContext] = None


def get_context() -> SessionContext:
    global _ctx
    if _ctx is None:
        _ctx = SessionContext()
    return _ctx


def reset_context() -> SessionContext:
    """Start a fresh session context (e.g. after restart)."""
    global _ctx
    _ctx = SessionContext()
    return _ctx
