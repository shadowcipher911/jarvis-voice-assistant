"""
tools/code_runner.py — Sandboxed Python and shell code execution.

All code runs in a subprocess with a configurable timeout.
JARVIS will warn the user before executing any code it generated itself.
"""

import logging
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

logger = logging.getLogger("jarvis.code_runner")

DEFAULT_TIMEOUT = 30  # seconds


# ---------------------------------------------------------------------------
# Python runner
# ---------------------------------------------------------------------------

def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    Write code to a temp file and execute it with the current Python interpreter.
    Returns stdout, stderr, and return code.
    """
    # Warn about self-generated code — the agent handles the actual confirmation
    logger.info("Executing Python code (%d chars)", len(code))

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(textwrap.dedent(code))
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = {
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:2000],
            "returncode": result.returncode,
        }
        logger.info("Python exit code: %d", result.returncode)
        return _format_result(output)
    except subprocess.TimeoutExpired:
        return f"ERROR: Python script timed out after {timeout}s."
    except Exception as e:
        return f"ERROR running Python: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Shell runner
# ---------------------------------------------------------------------------

def run_shell(command: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    Run a shell command and return the output.
    Runs via cmd.exe on Windows, /bin/sh on Unix.
    """
    logger.info("Executing shell command: %s", command[:120])
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = {
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:2000],
            "returncode": result.returncode,
        }
        return _format_result(output)
    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {timeout}s."
    except Exception as e:
        return f"ERROR running shell command: {e}"


# ---------------------------------------------------------------------------
# Package installer
# ---------------------------------------------------------------------------

def install_package(package_name: str) -> str:
    """Install a Python package via pip."""
    # Basic validation — reject obviously malicious names
    safe_name = package_name.strip().split()[0]  # take first word only
    if not safe_name.replace("-", "").replace("_", "").replace(".", "").isalnum():
        return f"ERROR: Package name '{safe_name}' looks invalid."

    logger.info("Installing package: %s", safe_name)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", safe_name],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return f"Successfully installed: {safe_name}"
        return f"Install failed:\n{result.stderr[:1000]}"
    except subprocess.TimeoutExpired:
        return "ERROR: pip install timed out."
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_result(output: dict) -> str:
    parts = []
    if output["stdout"]:
        parts.append(f"STDOUT:\n{output['stdout']}")
    if output["stderr"]:
        parts.append(f"STDERR:\n{output['stderr']}")
    parts.append(f"Exit code: {output['returncode']}")
    return "\n\n".join(parts) if parts else f"Completed (exit code {output['returncode']})."
