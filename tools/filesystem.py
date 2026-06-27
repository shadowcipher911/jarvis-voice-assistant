"""
tools/filesystem.py — Full file-system control for JARVIS.

All destructive operations (delete, overwrite) use safe defaults:
  - Files are moved to .jarvis_trash/{timestamp}/ rather than permanently deleted.
  - Auto-purge after trash_retention_hours (default 24 h) on the next start.
"""

import logging
import os
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("jarvis.filesystem")

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    try:
        with open(cfg_path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def _trash_root() -> Path:
    root = Path(__file__).parent.parent / ".jarvis_trash"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _allowed_paths() -> list[str]:
    return _config().get("filesystem", {}).get("allowed_paths", [])


def _check_allowed(path: str) -> None:
    allowed = _allowed_paths()
    if not allowed:
        return  # unrestricted
    p = Path(path).resolve()
    for a in allowed:
        if p.is_relative_to(Path(a).resolve()):
            return
    raise PermissionError(f"Path '{path}' is outside the allowed directories.")


# ---------------------------------------------------------------------------
# Read / Write
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    """Read and return the text content of any file."""
    _check_allowed(path)
    p = Path(path)
    if not p.exists():
        return f"ERROR: File not found: {path}"
    try:
        # Try plain text first
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"ERROR reading {path}: {e}"


def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with content."""
    _check_allowed(path)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    logger.info("Wrote file: %s (%d chars)", path, len(content))
    return f"File written: {path}"


def append_file(path: str, content: str) -> str:
    """Append content to an existing file (creates it if missing)."""
    _check_allowed(path)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(content)
    return f"Appended to: {path}"


# ---------------------------------------------------------------------------
# Safe delete
# ---------------------------------------------------------------------------

def delete_file(path: str) -> str:
    """Move a file to the JARVIS trash (recoverable)."""
    _check_allowed(path)
    p = Path(path)
    if not p.exists():
        return f"ERROR: File not found: {path}"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = _trash_root() / ts / p.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(dest))
    logger.warning("Trashed file: %s → %s", path, dest)
    return f"Moved to trash: {p.name} (restore with 'undo deletion')"


def delete_folder(path: str) -> str:
    """Move a folder to the JARVIS trash (recoverable)."""
    _check_allowed(path)
    p = Path(path)
    if not p.exists():
        return f"ERROR: Folder not found: {path}"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = _trash_root() / ts / p.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(dest))
    logger.warning("Trashed folder: %s → %s", path, dest)
    return f"Folder moved to trash: {p.name}"


def restore_from_trash(name: str) -> str:
    """Restore the most recently trashed item matching the given name."""
    trash = _trash_root()
    matches = sorted(trash.rglob(name), key=lambda x: x.stat().st_mtime, reverse=True)
    if not matches:
        return f"Nothing named '{name}' found in trash."
    item = matches[0]
    dest = Path.cwd() / item.name
    shutil.move(str(item), str(dest))
    return f"Restored '{item.name}' to {dest}"


def purge_old_trash(retention_hours: Optional[int] = None) -> str:
    """Delete trash items older than retention_hours (default: from config)."""
    if retention_hours is None:
        retention_hours = _config().get("filesystem", {}).get("trash_retention_hours", 24)
    cutoff = datetime.now() - timedelta(hours=retention_hours)
    trash = _trash_root()
    purged = 0
    for ts_dir in trash.iterdir():
        try:
            dir_time = datetime.strptime(ts_dir.name, "%Y%m%d_%H%M%S")
            if dir_time < cutoff:
                shutil.rmtree(str(ts_dir))
                purged += 1
        except (ValueError, OSError):
            pass
    return f"Purged {purged} old trash entries."


# ---------------------------------------------------------------------------
# Move / Copy / Rename
# ---------------------------------------------------------------------------

def move(src: str, dst: str) -> str:
    _check_allowed(src)
    _check_allowed(dst)
    shutil.move(src, dst)
    return f"Moved {src} → {dst}"


def copy(src: str, dst: str) -> str:
    _check_allowed(src)
    _check_allowed(dst)
    if Path(src).is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return f"Copied {src} → {dst}"


def rename(path: str, new_name: str) -> str:
    _check_allowed(path)
    p = Path(path)
    dest = p.parent / new_name
    p.rename(dest)
    return f"Renamed to {dest}"


# ---------------------------------------------------------------------------
# Directory listing / search
# ---------------------------------------------------------------------------

def list_dir(path: str, file_filter: str = "") -> str:
    """List directory contents, optionally filtered by extension or name pattern."""
    _check_allowed(path)
    p = Path(path)
    if not p.is_dir():
        return f"ERROR: Not a directory: {path}"

    entries = []
    for item in sorted(p.iterdir()):
        if file_filter and file_filter.lower() not in item.name.lower():
            continue
        kind = "DIR" if item.is_dir() else "FILE"
        size = item.stat().st_size if item.is_file() else 0
        entries.append(f"[{kind}] {item.name}  ({size:,} bytes)")

    return "\n".join(entries) if entries else "Directory is empty."


def search_files(query: str, root_path: str = ".") -> str:
    """Search for files by name or text content under root_path."""
    _check_allowed(root_path)
    root = Path(root_path)
    results = []

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        # Name match
        if query.lower() in p.name.lower():
            results.append(str(p))
            continue
        # Content match (text files only)
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            if query.lower() in text.lower():
                results.append(f"{p} [content match]")
        except (OSError, UnicodeDecodeError):
            pass

        if len(results) >= 50:
            results.append("... (truncated at 50 results)")
            break

    return "\n".join(results) if results else f"No files matching '{query}' found in {root_path}."


def make_dir(path: str) -> str:
    _check_allowed(path)
    Path(path).mkdir(parents=True, exist_ok=True)
    return f"Directory created: {path}"


def get_info(path: str) -> str:
    """Return file/folder metadata: size, dates, permissions."""
    _check_allowed(path)
    p = Path(path)
    if not p.exists():
        return f"ERROR: Path not found: {path}"
    stat = p.stat()
    created = datetime.fromtimestamp(stat.st_ctime).isoformat()
    modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
    return (
        f"Path: {p.resolve()}\n"
        f"Type: {'Directory' if p.is_dir() else 'File'}\n"
        f"Size: {stat.st_size:,} bytes\n"
        f"Created: {created}\n"
        f"Modified: {modified}\n"
        f"Permissions: {oct(stat.st_mode)}"
    )


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------

def zip_files(src_paths: str, output: str) -> str:
    """Compress one or more comma-separated paths into a ZIP archive."""
    paths = [s.strip() for s in src_paths.split(",")]
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            p = Path(path)
            if p.is_dir():
                for file in p.rglob("*"):
                    zf.write(file, file.relative_to(p.parent))
            elif p.is_file():
                zf.write(p, p.name)
    return f"Archive created: {output}"


def unzip(archive: str, dest: str = ".") -> str:
    """Extract a ZIP archive to dest directory."""
    _check_allowed(archive)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(dest)
    return f"Extracted {archive} → {dest}"


# ---------------------------------------------------------------------------
# Folder watcher (simple polling)
# ---------------------------------------------------------------------------

import threading
import time as _time


def watch_folder(path: str, callback, interval: float = 2.0) -> threading.Thread:
    """Spawn a daemon thread that calls callback(changed_files) on changes."""
    def _watch():
        known = {str(f): f.stat().st_mtime for f in Path(path).rglob("*") if f.is_file()}
        while True:
            _time.sleep(interval)
            current = {str(f): f.stat().st_mtime for f in Path(path).rglob("*") if f.is_file()}
            changed = [f for f, t in current.items() if known.get(f) != t]
            new_files = [f for f in current if f not in known]
            deleted = [f for f in known if f not in current]
            events = changed + new_files + deleted
            if events:
                callback(events)
            known = current

    t = threading.Thread(target=_watch, daemon=True, name=f"watch-{Path(path).name}")
    t.start()
    return t
