"""
tools/system.py — OS-level controls for JARVIS.

Covers volume, brightness, power, processes, network, clipboard,
environment variables, notifications, and arbitrary shell commands.
"""

import logging
import os
import platform
import socket
import subprocess
from typing import Optional

import psutil

logger = logging.getLogger("jarvis.system")

SYSTEM = platform.system()  # "Windows", "Darwin", "Linux"


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------

def get_volume() -> str:
    if SYSTEM == "Windows":
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            level = int(volume.GetMasterVolumeLevelScalar() * 100)
            return f"Volume: {level}%"
        except Exception:
            # Fallback — use PowerShell
            result = subprocess.run(
                ["powershell", "-Command", "(Get-AudioDevice -Playback).Volume"],
                capture_output=True, text=True
            )
            return f"Volume: {result.stdout.strip()}%"
    elif SYSTEM == "Darwin":
        result = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"], capture_output=True, text=True)
        return f"Volume: {result.stdout.strip()}%"
    else:
        result = subprocess.run(["amixer", "get", "Master"], capture_output=True, text=True)
        return result.stdout.strip()


def set_volume(level: str) -> str:
    lvl = int(float(str(level).strip()))
    lvl = max(0, min(100, lvl))
    if SYSTEM == "Windows":
        subprocess.run(
            ["powershell", "-Command", f"(New-Object -ComObject WScript.Shell).SendKeys([char]173)"],
            capture_output=True
        )
        # Use nircmd if available, otherwise PowerShell audio API
        result = subprocess.run(
            ["powershell", "-Command",
             f"$vol = New-Object -ComObject WScript.Shell; "
             f"Add-Type -TypeDefinition 'using System.Runtime.InteropServices; "
             f"[Guid(\"5CDF2C82-841E-4546-9722-0CF74078229A\"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] "
             f"interface IAudioEndpointVolume {{ void a(); void b(); void c(); void d(); int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext); }}'"],
            capture_output=True, text=True
        )
        # Simple fallback via nircmd
        subprocess.run(f"nircmd.exe setsysvolume {int(lvl * 655.35)}", shell=True, capture_output=True)
        return f"Volume set to {lvl}%"
    elif SYSTEM == "Darwin":
        subprocess.run(["osascript", "-e", f"set volume output volume {lvl}"])
        return f"Volume set to {lvl}%"
    else:
        subprocess.run(["amixer", "set", "Master", f"{lvl}%"])
        return f"Volume set to {lvl}%"


def mute() -> str:
    if SYSTEM == "Windows":
        subprocess.run(["powershell", "-Command",
                        "[System.Runtime.InteropServices.Marshal]::GetActiveObject('WScript.Shell').SendKeys([char]173)"],
                       capture_output=True)
        return "Audio muted."
    elif SYSTEM == "Darwin":
        subprocess.run(["osascript", "-e", "set volume with output muted"])
        return "Audio muted."
    else:
        subprocess.run(["amixer", "set", "Master", "mute"])
        return "Audio muted."


def unmute() -> str:
    if SYSTEM == "Windows":
        mute()  # toggle
        return "Audio unmuted."
    elif SYSTEM == "Darwin":
        subprocess.run(["osascript", "-e", "set volume without output muted"])
        return "Audio unmuted."
    else:
        subprocess.run(["amixer", "set", "Master", "unmute"])
        return "Audio unmuted."


# ---------------------------------------------------------------------------
# Brightness
# ---------------------------------------------------------------------------

def get_brightness() -> str:
    if SYSTEM == "Windows":
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"],
            capture_output=True, text=True
        )
        return f"Brightness: {result.stdout.strip()}%"
    elif SYSTEM == "Darwin":
        result = subprocess.run(["brightness", "-l"], capture_output=True, text=True)
        return result.stdout.strip()
    else:
        try:
            result = subprocess.run(["xrandr", "--verbose"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if "Brightness" in line:
                    return f"Brightness: {line.strip()}"
        except Exception:
            pass
    return "Brightness query not supported on this system."


def set_brightness(level: str) -> str:
    lvl = int(float(str(level).strip()))
    lvl = max(0, min(100, lvl))
    if SYSTEM == "Windows":
        subprocess.run(
            ["powershell", "-Command",
             f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{lvl})"],
            capture_output=True
        )
        return f"Brightness set to {lvl}%"
    elif SYSTEM == "Darwin":
        subprocess.run(["brightness", str(lvl / 100)], capture_output=True)
        return f"Brightness set to {lvl}%"
    else:
        subprocess.run(["xrandr", "--output", "eDP-1", "--brightness", str(lvl / 100)])
        return f"Brightness set to {lvl}%"


# ---------------------------------------------------------------------------
# Power controls (require confirmation — agent handles that)
# ---------------------------------------------------------------------------

def shutdown() -> str:
    if SYSTEM == "Windows":
        subprocess.run(["shutdown", "/s", "/t", "5"])
    elif SYSTEM == "Darwin":
        subprocess.run(["sudo", "shutdown", "-h", "now"])
    else:
        subprocess.run(["sudo", "shutdown", "-h", "now"])
    return "Shutting down in 5 seconds..."


def restart() -> str:
    if SYSTEM == "Windows":
        subprocess.run(["shutdown", "/r", "/t", "5"])
    elif SYSTEM == "Darwin":
        subprocess.run(["sudo", "shutdown", "-r", "now"])
    else:
        subprocess.run(["sudo", "reboot"])
    return "Restarting in 5 seconds..."


def sleep() -> str:
    if SYSTEM == "Windows":
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])
    elif SYSTEM == "Darwin":
        subprocess.run(["pmset", "sleepnow"])
    else:
        subprocess.run(["systemctl", "suspend"])
    return "Going to sleep..."


def lock_screen() -> str:
    if SYSTEM == "Windows":
        import ctypes
        ctypes.windll.user32.LockWorkStation()
    elif SYSTEM == "Darwin":
        subprocess.run(["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"])
    else:
        subprocess.run(["gnome-screensaver-command", "--lock"])
    return "Screen locked."


# ---------------------------------------------------------------------------
# Processes
# ---------------------------------------------------------------------------

def list_processes() -> str:
    procs = []
    for proc in sorted(psutil.process_iter(["name", "pid", "cpu_percent", "memory_percent"]),
                       key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:20]:
        info = proc.info
        procs.append(
            f"[PID {info['pid']}] {info['name']:<30} CPU: {info['cpu_percent']:>5.1f}%  RAM: {info['memory_percent']:>5.1f}%"
        )
    return "\n".join(procs) if procs else "No processes found."


def kill_process(name_or_pid: str) -> str:
    killed = []
    try:
        pid = int(name_or_pid)
        proc = psutil.Process(pid)
        proc.terminate()
        killed.append(f"PID {pid}")
    except ValueError:
        for proc in psutil.process_iter(["name", "pid"]):
            if name_or_pid.lower() in proc.info["name"].lower():
                try:
                    proc.terminate()
                    killed.append(proc.info["name"])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    return f"Terminated: {', '.join(killed)}" if killed else f"No process found: {name_or_pid}"


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def get_ip() -> str:
    local = socket.gethostbyname(socket.gethostname())
    try:
        import urllib.request
        public = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode()
    except Exception:
        public = "unavailable"
    return f"Local IP: {local}\nPublic IP: {public}"


def check_internet() -> str:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return "Internet connection: ✅ Online"
    except OSError:
        return "Internet connection: ❌ Offline"


def list_wifi() -> str:
    if SYSTEM == "Windows":
        result = subprocess.run(["netsh", "wlan", "show", "networks"], capture_output=True, text=True)
        return result.stdout[:2000]
    elif SYSTEM == "Darwin":
        result = subprocess.run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-s"],
            capture_output=True, text=True
        )
        return result.stdout[:2000]
    else:
        result = subprocess.run(["nmcli", "device", "wifi", "list"], capture_output=True, text=True)
        return result.stdout[:2000]


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------

def get_clipboard() -> str:
    import pyperclip
    return pyperclip.paste() or "(clipboard is empty)"


def set_clipboard(text: str) -> str:
    import pyperclip
    pyperclip.copy(text)
    return f"Clipboard updated ({len(text)} chars)."


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def send_notification(title: str, body: str = "") -> str:
    if SYSTEM == "Windows":
        try:
            from plyer import notification
            notification.notify(title=title, message=body, timeout=5)
            return f"Notification sent: {title}"
        except ImportError:
            subprocess.run(
                ["powershell", "-Command",
                 f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
                 f"$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                 f"$xml.GetElementsByTagName('text')[0].InnerText = '{title}';"
                 f"$xml.GetElementsByTagName('text')[1].InnerText = '{body}';"
                 f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);"
                 f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS').Show($toast)"],
                capture_output=True
            )
        return f"Notification sent: {title}"
    elif SYSTEM == "Darwin":
        subprocess.run(["osascript", "-e", f'display notification "{body}" with title "{title}"'])
        return f"Notification sent: {title}"
    else:
        subprocess.run(["notify-send", title, body])
        return f"Notification sent: {title}"


# ---------------------------------------------------------------------------
# Shell command
# ---------------------------------------------------------------------------

def run_command(cmd: str, timeout: int = 30) -> str:
    """Run any shell command and return stdout + stderr."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return output[:4000] if output else f"Command completed (exit code {result.returncode})"
    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {timeout}s."
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

def get_env(var: str) -> str:
    val = os.environ.get(var)
    return f"{var}={val}" if val else f"Environment variable '{var}' not set."


def set_env(var: str, value: str) -> str:
    os.environ[var] = value
    return f"Set {var} for this session."
