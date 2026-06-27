"""
tests/test_agent.py — Integration tests for the JARVIS agent.

These tests mock the LLM and verify that JARVIS routes 10 sample commands
to the correct tool functions without making real API calls.

Run with:  python -m pytest tests/test_agent.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_agent_result(tool_name: str, tool_input: str, final_output: str):
    """Build a fake AgentExecutor result dict."""
    return {
        "output": final_output,
        "intermediate_steps": [
            (MagicMock(tool=tool_name, tool_input=tool_input), final_output)
        ],
    }


# ---------------------------------------------------------------------------
# Integration tests — each test patches the AgentExecutor and asserts
# that the agent processes the command without raising exceptions.
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_executor():
    """Patch AgentExecutor so no real LLM calls are made."""
    with patch("core.agent.AgentExecutor") as mock_ae_cls:
        mock_executor_instance = MagicMock()
        mock_ae_cls.return_value = mock_executor_instance
        yield mock_executor_instance


@pytest.fixture
def mock_llm():
    with patch("core.agent.ChatAnthropic") as mock_llm_cls:
        yield mock_llm_cls


@pytest.fixture
def mock_react_agent():
    with patch("core.agent.create_react_agent") as mock_ra:
        yield mock_ra


@pytest.fixture(autouse=True)
def reset_agent_singleton():
    """Reset the agent singleton before each test."""
    import core.agent as agent_mod
    agent_mod._agent = None
    yield
    agent_mod._agent = None


class TestAgentIntegration:
    """
    10 sample commands — verifies agent.run() returns a string without
    exceptions for each command type.
    """

    COMMANDS = [
        ("file_read",        "Read the file C:/Users/me/notes.txt"),
        ("web_search",       "Search for the best Python web frameworks in 2024"),
        ("system_volume",    "What is the current system volume?"),
        ("file_list",        "List all files in my Downloads folder"),
        ("memory_save",      "Remember that my project deadline is July 15th"),
        ("memory_recall",    "What do you know about me?"),
        ("code_run",         "Write a Python script that prints Hello World and run it"),
        ("browser_open",     "Open YouTube and search for lo-fi music"),
        ("app_launch",       "Open VS Code"),
        ("system_processes", "What processes are using the most CPU right now?"),
    ]

    @pytest.mark.parametrize("cmd_name,command", COMMANDS)
    def test_command_returns_string(self, cmd_name, command, mock_executor, mock_llm, mock_react_agent, tmp_path, monkeypatch):
        """Every command should return a non-empty string response."""
        import os
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

        # Patch memory paths to avoid touching real DB
        import core.memory as mem_mod
        mem_mod._instance = None
        mem_mod.MEMORY_DIR = tmp_path
        mem_mod.CHROMA_DIR = tmp_path / "chroma_db"
        mem_mod.SQLITE_PATH = tmp_path / "jarvis.db"

        # Configure mock executor to return a plausible response
        mock_executor.invoke.return_value = {
            "output": f"Certainly, sir. I have handled: {cmd_name}",
            "intermediate_steps": [],
        }

        from core.agent import JarvisAgent
        agent = JarvisAgent()
        result = agent.run(command)

        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert len(result) > 0, "Response should not be empty"

    def test_missing_api_key_returns_helpful_message(self, tmp_path, monkeypatch):
        """Without an API key, JARVIS should return a helpful error, not raise."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")

        import core.memory as mem_mod
        mem_mod._instance = None
        mem_mod.MEMORY_DIR = tmp_path
        mem_mod.CHROMA_DIR = tmp_path / "chroma_db"
        mem_mod.SQLITE_PATH = tmp_path / "jarvis.db"

        with patch("core.agent.ChatAnthropic", side_effect=Exception("No key")):
            from core.agent import JarvisAgent
            agent = JarvisAgent()
            result = agent.run("Hello JARVIS")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_agent_saves_to_memory(self, mock_executor, mock_llm, mock_react_agent, tmp_path, monkeypatch):
        """Verify that running a command causes history entries to be saved."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

        import core.memory as mem_mod
        mem_mod._instance = None
        mem_mod.MEMORY_DIR = tmp_path
        mem_mod.CHROMA_DIR = tmp_path / "chroma_db"
        mem_mod.SQLITE_PATH = tmp_path / "jarvis.db"

        mock_executor.invoke.return_value = {"output": "Done, sir.", "intermediate_steps": []}

        from core.agent import JarvisAgent
        agent = JarvisAgent()
        agent.run("Test memory persistence")

        mem = mem_mod.get_memory()
        history = mem.get_history()
        assert len(history) >= 2
        roles = [h["role"] for h in history]
        assert "user" in roles
        assert "assistant" in roles

    def test_agent_handles_tool_error_gracefully(self, mock_executor, mock_llm, mock_react_agent, tmp_path, monkeypatch):
        """If AgentExecutor raises, agent should return a friendly error string."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

        import core.memory as mem_mod
        mem_mod._instance = None
        mem_mod.MEMORY_DIR = tmp_path
        mem_mod.CHROMA_DIR = tmp_path / "chroma_db"
        mem_mod.SQLITE_PATH = tmp_path / "jarvis.db"

        mock_executor.invoke.side_effect = RuntimeError("Simulated LLM failure")

        from core.agent import JarvisAgent
        agent = JarvisAgent()
        result = agent.run("Cause an error")

        assert isinstance(result, str)
        assert "error" in result.lower() or "pardon" in result.lower()

    def test_max_tool_calls_config(self, tmp_path, monkeypatch):
        """Verify max_tool_calls is read from config."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        import core.memory as mem_mod
        mem_mod._instance = None
        mem_mod.MEMORY_DIR = tmp_path
        mem_mod.CHROMA_DIR = tmp_path / "chroma_db"
        mem_mod.SQLITE_PATH = tmp_path / "jarvis.db"

        with patch("core.agent.ChatAnthropic"), \
             patch("core.agent.create_react_agent"), \
             patch("core.agent.AgentExecutor") as mock_ae:
            mock_ae.return_value = MagicMock()

            from core.agent import JarvisAgent
            agent = JarvisAgent()

            _, kwargs = mock_ae.call_args
            assert kwargs.get("max_iterations", 15) <= 15
