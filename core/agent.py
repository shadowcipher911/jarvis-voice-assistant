"""
core/agent.py — The JARVIS brain.

Uses LangGraph's prebuilt ReAct agent (the correct API for LangChain 1.x+)
with Mistral AI as the LLM. Tool calls are handled natively via the
LangChain tool-calling interface — no manual ReAct prompt formatting needed.
"""

import logging
import os
from datetime import datetime
from typing import Optional

import yaml
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool as lc_tool
from langchain_mistralai import ChatMistralAI
from langgraph.prebuilt import create_react_agent

from core.context import get_context
from core.memory import get_memory

load_dotenv()

logger = logging.getLogger("jarvis.agent")


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


# ---------------------------------------------------------------------------
# Tool builder — wraps every tool function as a LangChain @tool
# ---------------------------------------------------------------------------

def _build_tools() -> list:
    """
    Build LangChain-compatible tools from all tool modules.
    Each tool is a simple callable wrapped with @lc_tool so LangGraph
    can use native function-calling with Mistral.
    """
    tools = []

    # ---- Filesystem --------------------------------------------------------
    try:
        from tools import filesystem as fs

        @lc_tool
        def read_file(path: str) -> str:
            """Read the contents of any file. Input: absolute or relative file path."""
            return fs.read_file(path)

        @lc_tool
        def write_file(path_and_content: str) -> str:
            """Create or overwrite a file. Input format: 'path|||content'"""
            parts = path_and_content.split("|||", 1)
            return fs.write_file(parts[0], parts[1] if len(parts) > 1 else "")

        @lc_tool
        def append_file(path_and_content: str) -> str:
            """Append content to a file. Input format: 'path|||content'"""
            parts = path_and_content.split("|||", 1)
            return fs.append_file(parts[0], parts[1] if len(parts) > 1 else "")

        @lc_tool
        def delete_file(path: str) -> str:
            """Safely move a file to trash (recoverable). Input: file path."""
            return fs.delete_file(path)

        @lc_tool
        def delete_folder(path: str) -> str:
            """Safely move a folder to trash. Input: folder path."""
            return fs.delete_folder(path)

        @lc_tool
        def move_path(src_and_dst: str) -> str:
            """Move a file or folder. Input format: 'source|||destination'"""
            parts = src_and_dst.split("|||", 1)
            return fs.move(parts[0], parts[1])

        @lc_tool
        def copy_path(src_and_dst: str) -> str:
            """Copy a file or folder. Input format: 'source|||destination'"""
            parts = src_and_dst.split("|||", 1)
            return fs.copy(parts[0], parts[1])

        @lc_tool
        def rename_path(path_and_name: str) -> str:
            """Rename a file or folder. Input format: 'path|||new_name'"""
            parts = path_and_name.split("|||", 1)
            return fs.rename(parts[0], parts[1])

        @lc_tool
        def list_directory(path: str) -> str:
            """List directory contents. Input: folder path."""
            return fs.list_dir(path)

        @lc_tool
        def search_files(query_and_path: str) -> str:
            """Search files by name or content. Input format: 'query|||root_path'"""
            parts = query_and_path.split("|||", 1)
            root = parts[1] if len(parts) > 1 else "."
            return fs.search_files(parts[0], root)

        @lc_tool
        def make_directory(path: str) -> str:
            """Create a folder (and all parents). Input: folder path."""
            return fs.make_dir(path)

        @lc_tool
        def get_file_info(path: str) -> str:
            """Get file size, dates and permissions. Input: file path."""
            return fs.get_info(path)

        @lc_tool
        def zip_files(paths_and_output: str) -> str:
            """Compress files into a ZIP. Input format: 'file1,file2|||output.zip'"""
            parts = paths_and_output.split("|||", 1)
            return fs.zip_files(parts[0], parts[1])

        @lc_tool
        def unzip_file(archive_and_dest: str) -> str:
            """Extract a ZIP archive. Input format: 'archive.zip|||destination_folder'"""
            parts = archive_and_dest.split("|||", 1)
            dest = parts[1] if len(parts) > 1 else "."
            return fs.unzip(parts[0], dest)

        tools += [read_file, write_file, append_file, delete_file, delete_folder,
                  move_path, copy_path, rename_path, list_directory, search_files,
                  make_directory, get_file_info, zip_files, unzip_file]
        logger.debug("Filesystem tools loaded.")
    except ImportError as e:
        logger.warning("filesystem tools unavailable: %s", e)

    # ---- Browser -----------------------------------------------------------
    try:
        from tools import browser as br

        @lc_tool
        def browser_open_url(url: str) -> str:
            """Open a URL in the browser. Input: full URL."""
            return br.open_url(url)

        @lc_tool
        def browser_get_page_text(placeholder: str = "") -> str:
            """Get all visible text from the current browser page."""
            return br.get_page_text()

        @lc_tool
        def browser_screenshot(save_path: str = "screenshot.png") -> str:
            """Take a full-page screenshot. Input: file path to save PNG."""
            return br.screenshot(save_path)

        @lc_tool
        def browser_click(selector_or_text: str) -> str:
            """Click a page element by CSS selector or visible text."""
            return br.click(selector_or_text)

        @lc_tool
        def browser_run_js(javascript: str) -> str:
            """Execute JavaScript in the current browser page. Input: JS code."""
            return br.run_js(javascript)

        @lc_tool
        def browser_get_links(placeholder: str = "") -> str:
            """Return all links from the current browser page."""
            return br.get_links()

        @lc_tool
        def browser_new_tab(url: str) -> str:
            """Open a URL in a new browser tab. Input: URL."""
            return br.new_tab(url)

        tools += [browser_open_url, browser_get_page_text, browser_screenshot,
                  browser_click, browser_run_js, browser_get_links, browser_new_tab]
        logger.debug("Browser tools loaded.")
    except ImportError as e:
        logger.warning("browser tools unavailable: %s", e)

    # ---- Apps --------------------------------------------------------------
    try:
        from tools import apps

        @lc_tool
        def launch_app(app_name: str) -> str:
            """Launch a desktop application by name. Input: app name (e.g. 'notepad', 'spotify')."""
            return apps.launch_app(app_name)

        @lc_tool
        def close_app(app_name: str) -> str:
            """Close a running application gracefully. Input: app name."""
            return apps.close_app(app_name)

        @lc_tool
        def focus_app(app_name: str) -> str:
            """Bring an application window to the foreground. Input: app name."""
            return apps.focus_app(app_name)

        @lc_tool
        def list_open_apps(placeholder: str = "") -> str:
            """List all currently running applications."""
            return apps.list_open_apps()

        @lc_tool
        def send_shortcut(keys: str) -> str:
            """Send a keyboard shortcut. Input: keys like 'ctrl+s' or 'alt+f4'."""
            return apps.send_shortcut(keys)

        @lc_tool
        def type_into_app(text: str) -> str:
            """Type text into the currently focused application. Input: text to type."""
            return apps.type_into_app(text)

        tools += [launch_app, close_app, focus_app, list_open_apps, send_shortcut, type_into_app]
        logger.debug("Apps tools loaded.")
    except ImportError as e:
        logger.warning("apps tools unavailable: %s", e)

    # ---- System ------------------------------------------------------------
    try:
        from tools import system as sys_tools

        @lc_tool
        def get_volume(placeholder: str = "") -> str:
            """Get the current system volume level (0-100)."""
            return sys_tools.get_volume()

        @lc_tool
        def set_volume(level: str) -> str:
            """Set the system volume. Input: number between 0 and 100."""
            return sys_tools.set_volume(level)

        @lc_tool
        def mute_audio(placeholder: str = "") -> str:
            """Mute the system audio."""
            return sys_tools.mute()

        @lc_tool
        def unmute_audio(placeholder: str = "") -> str:
            """Unmute the system audio."""
            return sys_tools.unmute()

        @lc_tool
        def list_processes(placeholder: str = "") -> str:
            """List running processes sorted by CPU usage."""
            return sys_tools.list_processes()

        @lc_tool
        def kill_process(name_or_pid: str) -> str:
            """Terminate a process by name or PID. Input: process name or PID number."""
            return sys_tools.kill_process(name_or_pid)

        @lc_tool
        def get_ip_address(placeholder: str = "") -> str:
            """Get the local and public IP address."""
            return sys_tools.get_ip()

        @lc_tool
        def check_internet(placeholder: str = "") -> str:
            """Check whether the computer has an active internet connection."""
            return sys_tools.check_internet()

        @lc_tool
        def lock_screen(placeholder: str = "") -> str:
            """Lock the computer screen."""
            return sys_tools.lock_screen()

        @lc_tool
        def run_shell_command(command: str) -> str:
            """Run any shell/terminal command and return output. Input: command string."""
            return sys_tools.run_command(command)

        @lc_tool
        def send_desktop_notification(title_and_body: str) -> str:
            """Send a desktop notification. Input format: 'title|||body'"""
            parts = title_and_body.split("|||", 1)
            body = parts[1] if len(parts) > 1 else ""
            return sys_tools.send_notification(parts[0], body)

        tools += [get_volume, set_volume, mute_audio, unmute_audio, list_processes,
                  kill_process, get_ip_address, check_internet, lock_screen,
                  run_shell_command, send_desktop_notification]
        logger.debug("System tools loaded.")
    except ImportError as e:
        logger.warning("system tools unavailable: %s", e)

    # ---- Web Search --------------------------------------------------------
    try:
        from tools import web_search as ws

        @lc_tool
        def web_search(query: str) -> str:
            """Search the internet using DuckDuckGo. Input: search query."""
            return ws.search(query)

        @lc_tool
        def search_and_summarise(query: str) -> str:
            """Search the web and return a summary of the top result. Input: search query."""
            return ws.search_and_summarise(query)

        @lc_tool
        def fetch_page(url: str) -> str:
            """Fetch and return the clean text content of a web page. Input: URL."""
            return ws.fetch_page(url)

        tools += [web_search, search_and_summarise, fetch_page]
        logger.debug("Web search tools loaded.")
    except ImportError as e:
        logger.warning("web_search tools unavailable: %s", e)

    # ---- Code Runner -------------------------------------------------------
    try:
        from tools import code_runner as cr

        @lc_tool
        def run_python_code(code: str) -> str:
            """Write and execute Python code. Input: Python source code as a string."""
            return cr.run_python(code)

        @lc_tool
        def run_shell_script(command: str) -> str:
            """Run a shell command or script. Input: shell command string."""
            return cr.run_shell(command)

        @lc_tool
        def install_python_package(package_name: str) -> str:
            """Install a Python package via pip. Input: package name."""
            return cr.install_package(package_name)

        tools += [run_python_code, run_shell_script, install_python_package]
        logger.debug("Code runner tools loaded.")
    except ImportError as e:
        logger.warning("code_runner tools unavailable: %s", e)

    # ---- Clipboard ---------------------------------------------------------
    try:
        from tools import clipboard as cb

        @lc_tool
        def get_clipboard(placeholder: str = "") -> str:
            """Read the current clipboard text content."""
            return cb.get_clipboard()

        @lc_tool
        def set_clipboard(text: str) -> str:
            """Write text to the system clipboard. Input: text to copy."""
            return cb.set_clipboard(text)

        tools += [get_clipboard, set_clipboard]
        logger.debug("Clipboard tools loaded.")
    except ImportError as e:
        logger.warning("clipboard tools unavailable: %s", e)

    # ---- Memory ------------------------------------------------------------
    memory = get_memory()

    @lc_tool
    def remember_fact(key_and_value: str) -> str:
        """Store a key-value fact for later recall. Input format: 'key|||value'"""
        parts = key_and_value.split("|||", 1)
        if len(parts) == 2:
            memory.save_fact(parts[0], parts[1])
            return f"Fact stored: {parts[0]} = {parts[1]}"
        return "Invalid format. Use 'key|||value'."

    @lc_tool
    def recall_fact(key: str) -> str:
        """Recall a previously stored fact by key. Input: the key name."""
        result = memory.recall_structured(key)
        return result if result else f"No fact found for key: {key}"

    @lc_tool
    def save_memory(text: str) -> str:
        """Save something important to long-term memory. Input: text to remember."""
        memory.save(text)
        return "Memory saved."

    @lc_tool
    def search_memory(query: str) -> str:
        """Search past memories semantically. Input: search query."""
        results = memory.search(query)
        if not results:
            return "No relevant memories found."
        return "\n".join(f"[{r['timestamp'][:10]}] {r['text']}" for r in results)

    @lc_tool
    def pin_memory(text: str) -> str:
        """Pin a memory permanently so it's always recalled. Input: text to pin."""
        memory.pin(text)
        return f"Memory pinned: {text}"

    tools += [remember_fact, recall_fact, save_memory, search_memory, pin_memory]

    logger.info("Total tools loaded: %d", len(tools))
    return tools


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

SYSTEM_MESSAGE = """\
You are JARVIS, a highly capable AI assistant running on the user's local computer.
You have full access to their file system, browser, applications, and system controls.
You are calm, confident, and concise — like a British butler who is also an elite engineer.
Always confirm before destructive actions (deleting files, shutting down, etc).
Use your tools to complete tasks. Be direct and give clear answers."""


class JarvisAgent:
    """The central AI brain — receives commands and orchestrates tools."""

    def __init__(self):
        config = _load_config()
        jarvis_cfg = config.get("jarvis", {})

        self.model_name: str = jarvis_cfg.get("llm", "mistral-small-latest")
        self.max_tool_calls: int = jarvis_cfg.get("max_tool_calls", 15)
        self.memory_top_k: int = jarvis_cfg.get("memory_top_k", 5)

        self._tools = _build_tools()
        self._graph = None
        self._llm = None

        self._init_llm()
        logger.info("JarvisAgent ready — model=%s, tools=%d", self.model_name, len(self._tools))

    def _init_llm(self):
        api_key = os.getenv("MISTRAL_API_KEY", "")
        if not api_key:
            logger.warning("MISTRAL_API_KEY not set — agent will not function.")
            return

        try:
            self._llm = ChatMistralAI(
                model=self.model_name,
                mistral_api_key=api_key,
                temperature=0,
                max_tokens=4096,
            )

            # LangGraph prebuilt ReAct agent — the correct API for LangChain 1.x
            self._graph = create_react_agent(
                model=self._llm,
                tools=self._tools,
                prompt=SYSTEM_MESSAGE,
            )
            logger.info("LangGraph ReAct agent initialised with Mistral: %s", self.model_name)

        except Exception as e:
            logger.error("Failed to initialise agent: %s", e, exc_info=True)
            self._graph = None

    # -----------------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------------

    def run(self, user_input: str) -> str:
        """Process a user command and return JARVIS's response."""
        memory = get_memory()
        context = get_context()

        # Inject relevant memories as context prefix
        memory_ctx = memory.build_context_string(user_input, top_k=self.memory_top_k)

        memory.add_history("user", user_input)
        context.add_message("user", user_input)

        if self._graph is None:
            response = (
                "I'm afraid I cannot function without a valid API key, sir. "
                "Please set MISTRAL_API_KEY in your .env file."
            )
            memory.add_history("assistant", response)
            context.add_message("assistant", response)
            return response

        try:
            # Build the full message — memory context + user query
            full_input = user_input
            if memory_ctx and memory_ctx != "No prior memories.":
                full_input = f"[Context from memory]\n{memory_ctx}\n\n[User request]\n{user_input}"

            result = self._graph.invoke(
                {"messages": [HumanMessage(content=full_input)]},
                config={"recursion_limit": self.max_tool_calls * 2},
            )

            # Extract the final AI message
            messages = result.get("messages", [])
            response = ""
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content and not getattr(msg, "tool_calls", None):
                    response = msg.content
                    break

            if not response:
                response = "Task completed, sir."

        except Exception as exc:
            logger.error("Agent error: %s", exc, exc_info=True)
            response = f"I do beg your pardon, sir — I encountered an error: {exc}"

        # Persist
        memory.add_history("assistant", response)
        memory.save(f"User asked: {user_input} | JARVIS replied: {response}", importance=2)
        context.add_message("assistant", response)
        context.active_task = None

        logger.info("Response: %s", response[:120])
        return response

    def chat(self, message: str) -> str:
        """Alias for run() — used by the REST API and dashboard."""
        return self.run(message)


# Module-level singleton
_agent: Optional[JarvisAgent] = None


def get_agent() -> JarvisAgent:
    global _agent
    if _agent is None:
        _agent = JarvisAgent()
    return _agent
