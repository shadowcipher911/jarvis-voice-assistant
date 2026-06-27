"""
tools/notifications.py — Cross-platform desktop notifications.

Wraps the system notification APIs for Windows (Toast), macOS (osascript),
and Linux (notify-send). Falls back to plyer if available.
"""

import logging
import platform
import subprocess

logger = logging.getLogger("jarvis.notifications")

SYSTEM = platform.system()


def notify(title: str, body: str = "", timeout: int = 5) -> str:
    """
    Send a desktop notification.

    Args:
        title:   Notification title / heading.
        body:    Optional longer description.
        timeout: Display duration in seconds (where supported).

    Returns:
        Confirmation string.
    """
    logger.info("Sending notification: [%s] %s", title, body[:60])

    # --- plyer (cross-platform, optional) ---
    try:
        from plyer import notification as plyer_notif
        plyer_notif.notify(title=title, message=body, timeout=timeout, app_name="JARVIS")
        return f"Notification sent: {title}"
    except ImportError:
        pass
    except Exception as e:
        logger.warning("plyer notification failed: %s — trying platform fallback", e)

    # --- Platform-specific fallbacks ---
    if SYSTEM == "Windows":
        return _windows_toast(title, body)
    elif SYSTEM == "Darwin":
        return _macos_notify(title, body)
    else:
        return _linux_notify(title, body)


def _windows_toast(title: str, body: str) -> str:
    """Windows toast notification via PowerShell."""
    ps_script = f"""
    [Windows.UI.Notifications.ToastNotificationManager,
     Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
    $xml.GetElementsByTagName('text')[0].InnerText = '{title.replace("'", "")}'
    $xml.GetElementsByTagName('text')[1].InnerText = '{body.replace("'", "")}'
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS').Show($toast)
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        logger.warning("Toast notification failed: %s", result.stderr[:200])
        return f"Notification attempted (may not have displayed): {title}"
    return f"Notification sent: {title}"


def _macos_notify(title: str, body: str) -> str:
    script = f'display notification "{body}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)
    return f"Notification sent: {title}"


def _linux_notify(title: str, body: str) -> str:
    result = subprocess.run(["notify-send", title, body], capture_output=True, text=True)
    if result.returncode != 0:
        return f"Notification failed (is notify-send installed?): {result.stderr}"
    return f"Notification sent: {title}"


# Convenience alias used by core/agent.py tool registration
def send_notification(title: str, body: str = "") -> str:
    return notify(title, body)
