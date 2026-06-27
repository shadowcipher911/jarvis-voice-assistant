"""
core/scheduler.py — Background task scheduler.

JARVIS can create, list, and cancel timed or recurring tasks via voice/text.
Runs in a daemon thread so it never blocks the main event loop.
"""

import logging
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Callable, Optional

import schedule

logger = logging.getLogger("jarvis.scheduler")


class Task:
    """Represents one scheduled task."""

    def __init__(
        self,
        task_id: str,
        description: str,
        callback: Callable,
        schedule_str: str,
        run_once: bool = False,
    ):
        self.task_id = task_id
        self.description = description
        self.callback = callback
        self.schedule_str = schedule_str   # human-readable, e.g. "daily at 09:00"
        self.run_once = run_once
        self.created_at = datetime.now().isoformat()
        self.last_run: Optional[str] = None
        self._job = None                   # schedule.Job reference

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "schedule": self.schedule_str,
            "run_once": self.run_once,
            "created_at": self.created_at,
            "last_run": self.last_run,
        }


class Scheduler:
    """Manages all scheduled tasks and the background runner thread."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # -----------------------------------------------------------------------
    # Task creation helpers
    # -----------------------------------------------------------------------

    def every_minutes(self, minutes: int, callback: Callable, description: str) -> str:
        """Schedule a recurring task every N minutes."""
        task_id = str(uuid.uuid4())[:8]
        job = schedule.every(minutes).minutes.do(self._wrap(task_id, callback))
        task = Task(task_id, description, callback, f"every {minutes} minutes")
        task._job = job
        with self._lock:
            self._tasks[task_id] = task
        logger.info("Scheduled '%s' every %d minutes (id=%s)", description, minutes, task_id)
        return task_id

    def every_hours(self, hours: int, callback: Callable, description: str) -> str:
        task_id = str(uuid.uuid4())[:8]
        job = schedule.every(hours).hours.do(self._wrap(task_id, callback))
        task = Task(task_id, description, callback, f"every {hours} hours")
        task._job = job
        with self._lock:
            self._tasks[task_id] = task
        return task_id

    def daily_at(self, time_str: str, callback: Callable, description: str) -> str:
        """Schedule a recurring daily task at a specific time (HH:MM)."""
        task_id = str(uuid.uuid4())[:8]
        job = schedule.every().day.at(time_str).do(self._wrap(task_id, callback))
        task = Task(task_id, description, callback, f"daily at {time_str}")
        task._job = job
        with self._lock:
            self._tasks[task_id] = task
        logger.info("Scheduled '%s' daily at %s (id=%s)", description, time_str, task_id)
        return task_id

    def in_minutes(self, minutes: int, callback: Callable, description: str) -> str:
        """Schedule a one-shot task to run in N minutes from now."""
        task_id = str(uuid.uuid4())[:8]
        run_at = datetime.now() + timedelta(minutes=minutes)
        time_str = run_at.strftime("%H:%M")

        # Use schedule to fire once at the calculated time
        job = schedule.every().day.at(time_str).do(self._wrap(task_id, callback))
        task = Task(task_id, description, callback, f"in {minutes} minutes", run_once=True)
        task._job = job
        with self._lock:
            self._tasks[task_id] = task
        logger.info("Scheduled '%s' once in %d min at %s (id=%s)", description, minutes, time_str, task_id)
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Cancel a scheduled task by ID."""
        with self._lock:
            task = self._tasks.pop(task_id, None)
        if task and task._job:
            schedule.cancel_job(task._job)
            logger.info("Cancelled task %s ('%s')", task_id, task.description)
            return True
        return False

    def list_tasks(self) -> list[dict]:
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _wrap(self, task_id: str, callback: Callable) -> Callable:
        """Wrap callback to update last_run and handle run-once cleanup."""
        def wrapper():
            with self._lock:
                task = self._tasks.get(task_id)
            if task:
                task.last_run = datetime.now().isoformat()
            try:
                callback()
            except Exception as exc:
                logger.error("Task %s error: %s", task_id, exc)
            finally:
                # Auto-cancel one-shot tasks after they run
                if task and task.run_once:
                    self.cancel(task_id)
        return wrapper

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def start(self):
        """Start the background scheduler loop (blocking — run in a daemon thread)."""
        self._running = True
        logger.info("Scheduler started.")
        while self._running:
            schedule.run_pending()
            time.sleep(1)

    def stop(self):
        self._running = False
        logger.info("Scheduler stopped.")

    def start_background(self):
        """Convenience: start scheduler in its own daemon thread."""
        self._thread = threading.Thread(target=self.start, name="jarvis-scheduler", daemon=True)
        self._thread.start()
        return self._thread


# Module-level singleton
_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler
