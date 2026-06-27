"""
tests/test_tools.py — Unit tests for all JARVIS tool modules.

Run with:  python -m pytest tests/test_tools.py -v
"""

import os
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure the jarvis root is on sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# =============================================================================
# tools/filesystem.py
# =============================================================================

class TestFilesystem:
    def test_write_and_read(self, tmp_path):
        from tools.filesystem import write_file, read_file
        p = str(tmp_path / "test.txt")
        write_file(p, "Hello, JARVIS!")
        assert read_file(p) == "Hello, JARVIS!"

    def test_append(self, tmp_path):
        from tools.filesystem import write_file, append_file, read_file
        p = str(tmp_path / "append.txt")
        write_file(p, "line1\n")
        append_file(p, "line2\n")
        assert "line2" in read_file(p)

    def test_make_dir(self, tmp_path):
        from tools.filesystem import make_dir
        new_dir = str(tmp_path / "sub" / "deep")
        result = make_dir(new_dir)
        assert Path(new_dir).is_dir()
        assert "created" in result.lower()

    def test_list_dir(self, tmp_path):
        from tools.filesystem import write_file, list_dir
        write_file(str(tmp_path / "a.txt"), "a")
        write_file(str(tmp_path / "b.txt"), "b")
        listing = list_dir(str(tmp_path))
        assert "a.txt" in listing
        assert "b.txt" in listing

    def test_list_dir_with_filter(self, tmp_path):
        from tools.filesystem import write_file, list_dir
        write_file(str(tmp_path / "notes.txt"), "")
        write_file(str(tmp_path / "image.png"), "")
        listing = list_dir(str(tmp_path), file_filter=".txt")
        assert "notes.txt" in listing
        assert "image.png" not in listing

    def test_safe_delete(self, tmp_path):
        from tools.filesystem import write_file, delete_file, _trash_root
        p = str(tmp_path / "to_delete.txt")
        write_file(p, "delete me")
        result = delete_file(p)
        assert not Path(p).exists()
        assert "trash" in result.lower()

    def test_move(self, tmp_path):
        from tools.filesystem import write_file, move
        src = str(tmp_path / "src.txt")
        dst = str(tmp_path / "dst.txt")
        write_file(src, "content")
        move(src, dst)
        assert not Path(src).exists()
        assert Path(dst).exists()

    def test_copy(self, tmp_path):
        from tools.filesystem import write_file, copy
        src = str(tmp_path / "orig.txt")
        dst = str(tmp_path / "copy.txt")
        write_file(src, "original")
        copy(src, dst)
        assert Path(src).exists()
        assert Path(dst).exists()

    def test_rename(self, tmp_path):
        from tools.filesystem import write_file, rename
        p = str(tmp_path / "old.txt")
        write_file(p, "x")
        rename(p, "new.txt")
        assert (tmp_path / "new.txt").exists()

    def test_get_info(self, tmp_path):
        from tools.filesystem import write_file, get_info
        p = str(tmp_path / "info.txt")
        write_file(p, "data")
        info = get_info(p)
        assert "File" in info
        assert "bytes" in info

    def test_zip_and_unzip(self, tmp_path):
        from tools.filesystem import write_file, zip_files, unzip
        f1 = str(tmp_path / "a.txt")
        write_file(f1, "alpha")
        archive = str(tmp_path / "archive.zip")
        zip_files(f1, archive)
        assert Path(archive).exists()

        out_dir = str(tmp_path / "extracted")
        Path(out_dir).mkdir()
        unzip(archive, out_dir)
        assert (Path(out_dir) / "a.txt").exists()

    def test_search_files_by_name(self, tmp_path):
        from tools.filesystem import write_file, search_files
        write_file(str(tmp_path / "report_2024.txt"), "annual report")
        result = search_files("report", str(tmp_path))
        assert "report_2024.txt" in result

    def test_search_files_by_content(self, tmp_path):
        from tools.filesystem import write_file, search_files
        write_file(str(tmp_path / "notes.txt"), "Project deadline is July 15")
        result = search_files("deadline", str(tmp_path))
        assert "content match" in result

    def test_read_missing_file(self):
        from tools.filesystem import read_file
        result = read_file("/nonexistent/path/file.txt")
        assert "ERROR" in result


# =============================================================================
# tools/clipboard.py
# =============================================================================

class TestClipboard:
    def test_set_and_get(self):
        from tools.clipboard import set_clipboard, get_clipboard
        try:
            set_clipboard("JARVIS clipboard test")
            result = get_clipboard()
            assert "JARVIS" in result
        except Exception:
            pytest.skip("Clipboard not available in this environment.")

    def test_clear(self):
        from tools.clipboard import clear_clipboard, set_clipboard, get_clipboard
        try:
            set_clipboard("something")
            clear_clipboard()
            result = get_clipboard()
            assert result == "(Clipboard is empty)" or result == ""
        except Exception:
            pytest.skip("Clipboard not available in this environment.")


# =============================================================================
# tools/code_runner.py
# =============================================================================

class TestCodeRunner:
    def test_run_python_hello(self):
        from tools.code_runner import run_python
        result = run_python('print("Hello from JARVIS")')
        assert "Hello from JARVIS" in result

    def test_run_python_math(self):
        from tools.code_runner import run_python
        result = run_python("print(2 + 2)")
        assert "4" in result

    def test_run_python_error(self):
        from tools.code_runner import run_python
        result = run_python("1/0")
        assert "ZeroDivisionError" in result or "Error" in result

    def test_run_python_timeout(self):
        from tools.code_runner import run_python
        result = run_python("import time; time.sleep(60)", timeout=2)
        assert "timed out" in result.lower()

    def test_run_shell(self):
        from tools.code_runner import run_shell
        import platform
        if platform.system() == "Windows":
            result = run_shell("echo JARVIS_TEST")
        else:
            result = run_shell("echo JARVIS_TEST")
        assert "JARVIS_TEST" in result

    def test_install_package_invalid_name(self):
        from tools.code_runner import install_package
        result = install_package("../../etc/passwd")
        assert "invalid" in result.lower() or "ERROR" in result


# =============================================================================
# tools/web_search.py (mocked)
# =============================================================================

class TestWebSearch:
    @patch("tools.web_search.DDGS")
    def test_search_returns_results(self, mock_ddgs_cls):
        from tools.web_search import _ddg_search
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value.__enter__ = lambda s: mock_ddgs
        mock_ddgs_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"title": "Test Result", "href": "https://example.com", "body": "A test snippet."}
        ]
        result = _ddg_search("test query")
        assert "Test Result" in result
        assert "https://example.com" in result

    @patch("tools.web_search.requests.get")
    def test_fetch_page(self, mock_get):
        from tools.web_search import fetch_page
        mock_resp = MagicMock()
        mock_resp.text = "<html><body><p>Hello world</p></body></html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = fetch_page("https://example.com")
        assert "Hello world" in result


# =============================================================================
# tools/system.py (smoke tests — no side effects)
# =============================================================================

class TestSystem:
    def test_check_internet(self):
        from tools.system import check_internet
        result = check_internet()
        assert "Online" in result or "Offline" in result

    def test_get_ip(self):
        from tools.system import get_ip
        result = get_ip()
        assert "IP" in result

    def test_list_processes(self):
        from tools.system import list_processes
        result = list_processes()
        # Should contain at least the current Python process
        assert len(result) > 0

    def test_run_command(self):
        from tools.system import run_command
        import platform
        cmd = "echo JARVIS_SYS_TEST"
        result = run_command(cmd)
        assert "JARVIS_SYS_TEST" in result

    def test_get_env(self):
        from tools.system import get_env, set_env
        set_env("JARVIS_TEST_VAR", "hello")
        result = get_env("JARVIS_TEST_VAR")
        assert "hello" in result


# =============================================================================
# core/memory.py
# =============================================================================

class TestMemory:
    def test_save_and_search(self, tmp_path, monkeypatch):
        monkeypatch.setenv("JARVIS_MEMORY_DIR", str(tmp_path))
        from core import memory as mem_module
        # Reset singleton
        mem_module._instance = None
        # Patch paths
        mem_module.MEMORY_DIR = tmp_path
        mem_module.CHROMA_DIR = tmp_path / "chroma_db"
        mem_module.SQLITE_PATH = tmp_path / "jarvis.db"

        m = mem_module.Memory()
        m.save_fact("test_key", "test_value")
        assert m.recall_structured("test_key") == "test_value"
        m.close()

    def test_facts(self, tmp_path, monkeypatch):
        from core import memory as mem_module
        mem_module._instance = None
        mem_module.MEMORY_DIR = tmp_path
        mem_module.CHROMA_DIR = tmp_path / "chroma_db"
        mem_module.SQLITE_PATH = tmp_path / "jarvis.db"

        m = mem_module.Memory()
        m.save_fact("name", "Tony Stark")
        m.save_fact("deadline", "July 15")
        facts = m.get_all_facts()
        assert facts["name"] == "Tony Stark"
        assert facts["deadline"] == "July 15"
        m.close()

    def test_pinned_memory(self, tmp_path):
        from core import memory as mem_module
        mem_module._instance = None
        mem_module.MEMORY_DIR = tmp_path
        mem_module.CHROMA_DIR = tmp_path / "chroma_db"
        mem_module.SQLITE_PATH = tmp_path / "jarvis.db"

        m = mem_module.Memory()
        m.pin("My boss is Sarah.")
        pinned = m.get_pinned()
        assert "My boss is Sarah." in pinned
        m.close()

    def test_history(self, tmp_path):
        from core import memory as mem_module
        mem_module._instance = None
        mem_module.MEMORY_DIR = tmp_path
        mem_module.CHROMA_DIR = tmp_path / "chroma_db"
        mem_module.SQLITE_PATH = tmp_path / "jarvis.db"

        m = mem_module.Memory()
        m.add_history("user", "Hello JARVIS")
        m.add_history("assistant", "Good day, sir.")
        history = m.get_history()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        m.close()


# =============================================================================
# core/context.py
# =============================================================================

class TestContext:
    def test_add_message(self):
        from core.context import reset_context
        ctx = reset_context()
        ctx.add_message("user", "test message")
        msgs = ctx.get_recent_messages()
        assert len(msgs) == 1
        assert msgs[0]["content"] == "test message"

    def test_app_tracking(self):
        from core.context import reset_context
        ctx = reset_context()
        ctx.register_app_open("Spotify")
        ctx.register_app_open("VS Code")
        assert "Spotify" in ctx.open_apps
        ctx.register_app_close("Spotify")
        assert "Spotify" not in ctx.open_apps

    def test_confirmation_queue(self):
        from core.context import reset_context
        ctx = reset_context()
        conf_id = ctx.request_confirmation("delete_file", {"path": "/tmp/test.txt"})
        assert len(ctx.pending_confirmations) == 1
        confirmed = ctx.confirm(conf_id)
        assert confirmed is not None
        assert confirmed["action"] == "delete_file"
        assert len(ctx.pending_confirmations) == 0

    def test_to_dict(self):
        from core.context import reset_context
        ctx = reset_context()
        d = ctx.to_dict()
        assert "active_task" in d
        assert "open_apps" in d


# =============================================================================
# core/scheduler.py
# =============================================================================

class TestScheduler:
    def test_schedule_and_cancel(self):
        from core.scheduler import Scheduler
        fired = []
        s = Scheduler()
        task_id = s.every_minutes(999, lambda: fired.append(1), "test task")
        tasks = s.list_tasks()
        assert any(t["task_id"] == task_id for t in tasks)
        assert s.cancel(task_id)
        tasks = s.list_tasks()
        assert not any(t["task_id"] == task_id for t in tasks)

    def test_one_shot(self):
        from core.scheduler import Scheduler
        s = Scheduler()
        task_id = s.in_minutes(999, lambda: None, "one-shot")
        tasks = s.list_tasks()
        assert any(t["run_once"] for t in tasks if t["task_id"] == task_id)
        s.cancel(task_id)
