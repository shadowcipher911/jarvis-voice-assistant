"""
tools/browser.py — Full browser automation via Playwright.

Manages a single shared browser + page instance. Playwright must be
installed and `playwright install chromium` must have been run.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("jarvis.browser")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    try:
        with open(cfg_path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


# ---------------------------------------------------------------------------
# Browser singleton
# ---------------------------------------------------------------------------

_playwright = None
_browser = None
_page = None


def _get_page():
    """Lazily initialise Playwright and return the active page."""
    global _playwright, _browser, _page

    if _page is not None and not _page.is_closed():
        return _page

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    cfg = _config().get("browser", {})
    engine = cfg.get("engine", "chromium")
    headless = cfg.get("headless", False)

    _playwright = sync_playwright().start()
    launcher = getattr(_playwright, engine)
    _browser = launcher.launch(headless=headless)
    context = _browser.new_context()
    _page = context.new_page()
    logger.info("Browser started: %s (headless=%s)", engine, headless)
    return _page


def _timeout() -> int:
    return _config().get("browser", {}).get("timeout_seconds", 30) * 1000  # ms


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def open_url(url: str) -> str:
    """Navigate to a URL."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    page = _get_page()
    page.goto(url, timeout=_timeout())
    logger.info("Navigated to: %s", url)
    return f"Opened: {url} — Title: {page.title()}"


def new_tab(url: str) -> str:
    """Open a URL in a new tab and switch to it."""
    global _page
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    page = _get_page()
    _page = page.context.new_page()
    _page.goto(url, timeout=_timeout())
    return f"New tab opened: {url}"


def close_tab() -> str:
    global _page
    if _page:
        _page.close()
        pages = _page.context.pages
        _page = pages[-1] if pages else None
        return "Tab closed."
    return "No active tab."


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------

def click(selector_or_text: str) -> str:
    """Click an element by CSS selector or visible text."""
    page = _get_page()
    try:
        # Try as CSS selector first
        page.click(selector_or_text, timeout=5000)
    except Exception:
        # Fall back to text search
        page.get_by_text(selector_or_text).first.click(timeout=_timeout())
    return f"Clicked: {selector_or_text}"


def type_text(selector: str, text: str) -> str:
    """Fill a form field."""
    page = _get_page()
    page.fill(selector, text, timeout=_timeout())
    return f"Typed into {selector}"


def select_dropdown(selector: str, value: str) -> str:
    page = _get_page()
    page.select_option(selector, value, timeout=_timeout())
    return f"Selected '{value}' in {selector}"


def wait_for(selector: str) -> str:
    page = _get_page()
    page.wait_for_selector(selector, timeout=_timeout())
    return f"Element found: {selector}"


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def get_text(selector: str) -> str:
    page = _get_page()
    el = page.query_selector(selector)
    return el.inner_text() if el else "Element not found."


def get_page_text() -> str:
    """Return all visible text from the current page (truncated to 8 KB)."""
    page = _get_page()
    text = page.inner_text("body")
    if len(text) > 8192:
        text = text[:8192] + "\n... [truncated]"
    return text


def get_links() -> str:
    """Return all anchor links on the current page."""
    page = _get_page()
    links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href + ' | ' + e.innerText.trim())")
    return "\n".join(links[:100]) if links else "No links found."


def scroll(direction: str = "down", amount: int = 500) -> str:
    page = _get_page()
    delta = amount if direction == "down" else -amount
    page.evaluate(f"window.scrollBy(0, {delta})")
    return f"Scrolled {direction} by {amount}px."


def run_js(script: str) -> str:
    """Execute JavaScript in the current page and return the result."""
    page = _get_page()
    result = page.evaluate(script)
    return str(result)


# ---------------------------------------------------------------------------
# Screenshot & download
# ---------------------------------------------------------------------------

def screenshot(path: str = "screenshot.png") -> str:
    page = _get_page()
    page.screenshot(path=path, full_page=True)
    return f"Screenshot saved: {path}"


def download_file(url: str, dest: str) -> str:
    """Download a file using the browser's download mechanism."""
    page = _get_page()
    with page.expect_download() as dl_info:
        page.goto(url, timeout=_timeout())
    download = dl_info.value
    download.save_as(dest)
    return f"Downloaded to: {dest}"


# ---------------------------------------------------------------------------
# Login helper
# ---------------------------------------------------------------------------

def login(url: str, username: str, password: str) -> str:
    """
    Attempt an automated login. Looks for common username/password field patterns.
    Credentials should be passed from .env — never hardcoded.
    """
    open_url(url)
    page = _get_page()

    username_selectors = ["input[type='email']", "input[name='username']", "input[name='email']", "#username", "#email"]
    password_selectors = ["input[type='password']", "input[name='password']", "#password"]

    username_filled = False
    for sel in username_selectors:
        if page.query_selector(sel):
            page.fill(sel, username)
            username_filled = True
            break

    password_filled = False
    for sel in password_selectors:
        if page.query_selector(sel):
            page.fill(sel, password)
            password_filled = True
            break

    if username_filled and password_filled:
        # Submit the form
        page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle", timeout=_timeout())
        return f"Login attempted at {url}."
    return "Could not locate login fields automatically."


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def close_browser() -> str:
    global _playwright, _browser, _page
    if _browser:
        _browser.close()
    if _playwright:
        _playwright.stop()
    _browser = _page = _playwright = None
    return "Browser closed."
