"""
tools/web_search.py — Internet search and page summarisation.

Primary: DuckDuckGo (no API key required).
Optional: SerpAPI for richer results (requires SERPAPI_KEY in .env).
"""

import logging
import os
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("jarvis.web_search")

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")


# ---------------------------------------------------------------------------
# Core search
# ---------------------------------------------------------------------------

def search(query: str, max_results: int = 5) -> str:
    """Search the internet and return top results with title, URL, snippet."""
    if SERPAPI_KEY:
        return _serpapi_search(query, max_results)
    return _ddg_search(query, max_results)


def _ddg_search(query: str, max_results: int = 5) -> str:
    """DuckDuckGo search — no API key required."""
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    f"Title: {r.get('title', '')}\n"
                    f"URL:   {r.get('href', '')}\n"
                    f"Snip:  {r.get('body', '')[:200]}\n"
                )
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        logger.error("DuckDuckGo search error: %s", e)
        return f"Search failed: {e}"


def _serpapi_search(query: str, max_results: int = 5) -> str:
    """SerpAPI search — richer results, requires API key."""
    try:
        params = {
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": max_results,
            "engine": "google",
        }
        response = requests.get("https://serpapi.com/search", params=params, timeout=10)
        data = response.json()
        results = []
        for r in data.get("organic_results", [])[:max_results]:
            results.append(
                f"Title: {r.get('title', '')}\n"
                f"URL:   {r.get('link', '')}\n"
                f"Snip:  {r.get('snippet', '')[:200]}\n"
            )
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        logger.error("SerpAPI search error: %s", e)
        return _ddg_search(query, max_results)  # fallback


# ---------------------------------------------------------------------------
# Page fetch + summarise
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> str:
    """Fetch a URL and return clean extracted text (max 6 KB)."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; JARVIS/1.0)"}
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script, style, nav noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Truncate to 6 KB
        if len(text) > 6144:
            text = text[:6144] + "\n... [page truncated]"

        return text
    except Exception as e:
        logger.error("fetch_page error (%s): %s", url, e)
        return f"Failed to fetch {url}: {e}"


def search_and_summarise(query: str) -> str:
    """
    Search for a query, fetch the top result's content, and return a
    combined summary of search snippets + page content.
    """
    raw_results = _ddg_search(query, max_results=3)

    # Extract first URL from results
    first_url = None
    for line in raw_results.splitlines():
        if line.startswith("URL:"):
            first_url = line.replace("URL:", "").strip()
            break

    page_content = ""
    if first_url:
        page_content = fetch_page(first_url)

    summary = f"=== Search Results for: {query} ===\n{raw_results}"
    if page_content:
        summary += f"\n\n=== Top Page Content ({first_url}) ===\n{page_content[:3000]}"

    return summary
