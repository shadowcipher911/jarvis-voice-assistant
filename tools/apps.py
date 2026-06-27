"""
tools/apps.py — Launch and control desktop applications.

Uses subprocess to open apps, psutil for process management, and
pyautogui for keyboard shortcuts and window interaction.
"""

import logging
import platform
import subprocess
import sys
import time
from typing import Optional

import psutil
import pyautogui

logger = logging.getLogger("jarvis.apps")

SYSTEM = platform.system()  # "Windows", "Darwin", "Linux"


# ---------------------------------------------------------------------------
# App launchers
# ---------------------------------------------------------------------------

_WINDOWS_APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge": "msedge.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "outlook": "OUTLOOK.EXE",
    "vscode": "code",
    "vs code": "code",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "slack": "slack.exe",
    "zoom": "zoom.exe",
    "vlc": "vlc.exe",
}

_MAC_APP_MAP = {
    "finder": "Finder",
    "safari": "Safari",
    "chrome": "Google Chrome",
    "firefox": "Firefox",
    "terminal": "Terminal",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "spotify": "Spotify",
    "discord": "Discord",
    "slack": "Slack",
    "zoom": "zoom.us",
}


def launch_app(name: str) -> str:
    """Open an installed application by name."""
    name_lower = name.lower().strip()

    if SYSTEM == "Windows":
        cmd = _WINDOWS_APP_MAP.get(name_lower, name)
        try:
            subprocess.Popen([cmd], shell=True)
            return f"Launched: {name}"
        except Exception as e:
            # Try start command
            try:
                subprocess.Popen(f'start "" "{cmd}"', shell=True)
                return f"Launched: {name}"
            except Exception as e2:
                return f"ERROR launching {name}: {e2}"

    elif SYSTEM == "Darwin":  # macOS
        app = _MAC_APP_MAP.get(name_lower, name)
        result = subprocess.run(["open", "-a", app], capture_output=True, text=True)
        if result.returncode == 0:
            return f"Launched: {app}"
        return f"ERROR: {result.stderr}"

    else:  # Linux
        result = subprocess.run(["which", name_lower], capture_output=True, text=True)
        if result.returncode == 0:
            subprocess.Popen([name_lower])
            return f"Launched: {name}"
        return f"Application not found: {name}"


def close_app(name: str) -> str:
    """Gracefully terminate an application by name."""
    killed = []
    for proc in psutil.process_iter(["name", "pid"]):
        if name.lower() in proc.info["name"].lower():
            try:
                proc.terminate()
                killed.append(proc.info["name"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    if killed:
        return f"Closed: {', '.join(set(killed))}"
    return f"No running process found matching '{name}'."


def force_quit(name: str) -> str:
    """Force-kill an application."""
    killed = []
    for proc in psutil.process_iter(["name", "pid"]):
        if name.lower() in proc.info["name"].lower():
            try:
                proc.kill()
                killed.append(proc.info["name"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    if killed:
        return f"Force-killed: {', '.join(set(killed))}"
    return f"No process found matching '{name}'."


def focus_app(name: str) -> str:
    """Bring an application window to the foreground."""
    if SYSTEM == "Windows":
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32

        def _enum_callback(hwnd, _):
            _, pid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None), None
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if name.lower() in buf.value.lower():
                user32.ShowWindow(hwnd, 9)   # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(_enum_callback), 0)
        return f"Focused: {name}"

    elif SYSTEM == "Darwin":
        subprocess.run(["osascript", "-e", f'tell application "{name}" to activate'])
        return f"Focused: {name}"

    else:
        subprocess.run(["wmctrl", "-a", name])
        return f"Focused: {name}"


def list_open_apps() -> str:
    """Return a list of all unique running process names."""
    names = set()
    for proc in psutil.process_iter(["name"]):
        try:
            names.add(proc.info["name"])
        except psutil.NoSuchProcess:
            pass
    return "\n".join(sorted(names))


# ---------------------------------------------------------------------------
# Keyboard & text input
# ---------------------------------------------------------------------------

def send_shortcut(keys: str) -> str:
    """
    Send a keyboard shortcut.
    Input format: 'ctrl+s', 'alt+f4', 'win+d', etc.
    """
    parts = [k.strip() for k in keys.lower().split("+")]
    pyautogui.hotkey(*parts)
    return f"Shortcut sent: {keys}"


def type_into_app(text: str) -> str:
    """Type text into the currently focused application."""
    pyautogui.write(text, interval=0.02)
    return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"


# ---------------------------------------------------------------------------
# Screenshot of a specific window
# ---------------------------------------------------------------------------

def screenshot_app(name: str, output: str = "app_screenshot.png") -> str:
    """Take a screenshot of a specific application window (Windows)."""
    focus_app(name)
    time.sleep(0.3)
    if SYSTEM == "Windows":
        import ctypes
        import ctypes.wintypes
        screenshot = pyautogui.screenshot()
        screenshot.save(output)
        return f"Screenshot saved: {output}"
    else:
        screenshot = pyautogui.screenshot()
        screenshot.save(output)
        return f"Screenshot saved: {output}"


# ---------------------------------------------------------------------------
# Image-based click (template matching)
# ---------------------------------------------------------------------------

def click_in_app(image_template: str) -> str:
    """Click a UI element located by image template matching."""
    location = pyautogui.locateCenterOnScreen(image_template, confidence=0.8)
    if location:
        pyautogui.click(location)
        return f"Clicked element from template: {image_template}"
    return f"Could not find element on screen: {image_template}"
