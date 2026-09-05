#!/usr/bin/env python3
"""
rg/websearch — a keyless web search MCP server for LM Studio.

No API key required.

Backend: scrapes Bing's plain HTML search results page. DuckDuckGo's
html.duckduckgo.com / lite.duckduckgo.com endpoints were tried first and both
return an anti-bot CAPTCHA challenge page for a bare scripted request (no
cookies/JS) — verified empirically, not assumed — so they were dropped in
favor of Bing, which currently serves plain HTML results with no challenge
for a single low-frequency request.

Run directly for a local smoke test:
    python3 rg_websearch_mcp.py --self-test "python asyncio tutorial"

Run as an MCP stdio server (what LM Studio launches):
    uv run --with mcp python3 rg_websearch_mcp.py
"""
import base64
import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

SEARCH_URL = "https://www.bing.com/search"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
TIMEOUT = 15

RESULT_BLOCK_RE = re.compile(r'<li class="b_algo".*?</li>', re.S)
TITLE_RE = re.compile(r'<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h2>', re.S)
SNIPPET_RE = re.compile(r'<div class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>', re.S)
TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    return html.unescape(TAG_RE.sub("", s)).strip()


def _unwrap_bing_redirect(url: str) -> str:
    """Bing wraps result links as bing.com/ck/a?...&u=<2-char-version><base64url>&...
    Decode that back to the real URL; if the shape doesn't match, return as-is."""
    parsed = urllib.parse.urlparse(url)
    if "bing.com" not in parsed.netloc or parsed.path != "/ck/a":
        return url
    qs = urllib.parse.parse_qs(parsed.query)
    u = qs.get("u")
    if not u:
        return url
    payload = u[0][2:]  # drop the 2-char version prefix (e.g. "a1")
    payload += "=" * (-len(payload) % 4)  # restore base64 padding
    try:
        return base64.urlsafe_b64decode(payload).decode("utf-8", "replace")
    except Exception:
        return url


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return up to max_results {title, url, snippet} dicts.
    Returns [{"error": "..."}] on failure instead of raising, since MCP tool
    callers (an LLM) need a value to reason about, not an exception."""
    if not query or not query.strip():
        return [{"error": "query must not be empty"}]

    max_results = max(1, min(int(max_results), 20))

    params = urllib.parse.urlencode({"q": query, "setlang": "en-us"})
    req = urllib.request.Request(
        f"{SEARCH_URL}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as e:
        return [{"error": f"search request failed: {e}"}]

    results = []
    for block in RESULT_BLOCK_RE.findall(body):
        if len(results) >= max_results:
            break
        title_match = TITLE_RE.search(block)
        if not title_match:
            continue
        url = _unwrap_bing_redirect(html.unescape(title_match.group(1)))
        title = _strip_tags(title_match.group(2))
        snippet_match = SNIPPET_RE.search(block)
        snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})

    if not results:
        return [{
            "error": "no results parsed — Bing may have changed its HTML, "
                     "shown a CAPTCHA, or the query genuinely returned nothing"
        }]
    return results


def _self_test(query: str) -> None:
    import json
    results = web_search(query, max_results=5)
    print(json.dumps(results, indent=2))
    if results and "error" in results[0]:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--self-test":
        _self_test(" ".join(sys.argv[2:]))
        sys.exit(0)

    from mcp.server.mcpserver import MCPServer

    mcp = MCPServer("rg-websearch")
    mcp.tool()(web_search)
    mcp.run()
