"""005.902 — web-access plugin: search (Tavily+Google), fetch, http_request.

Uses httpx.MockTransport (built-in) — no real network, no extra deps.
"""

from __future__ import annotations

import httpx
import pytest

from plugin_web_access.fetch import extract_readable, run_fetch
from plugin_web_access.http_client import run_request
from plugin_web_access.safety import blocked_reason
from plugin_web_access.search import run_search


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------------- web_search ----------------
@pytest.mark.asyncio
class TestSearch:
    async def test_tavily_success(self, monkeypatch) -> None:
        monkeypatch.setenv("LUNA_WEB_SEARCH_PROVIDER", "tavily")
        monkeypatch.setenv("LUNA_TAVILY_API_KEY", "tvly-test")

        def handler(req: httpx.Request) -> httpx.Response:
            assert "tavily.com" in str(req.url)
            return httpx.Response(200, json={
                "answer": "Python 3.14 is the latest.",
                "results": [{"title": "Python", "url": "https://python.org", "content": "downloads"}],
            })

        out = await run_search("latest python", client=_client(handler))
        assert out["provider"] == "tavily"
        assert out["answer"].startswith("Python 3.14")
        assert out["result_count"] == 1
        assert out["results"][0]["url"] == "https://python.org"

    async def test_google_success(self, monkeypatch) -> None:
        monkeypatch.setenv("LUNA_WEB_SEARCH_PROVIDER", "google")
        monkeypatch.setenv("LUNA_GOOGLE_SEARCH_API_KEY", "g-key")
        monkeypatch.setenv("LUNA_GOOGLE_SEARCH_CX", "cx-123")

        def handler(req: httpx.Request) -> httpx.Response:
            assert "googleapis.com" in str(req.url)
            return httpx.Response(200, json={
                "items": [{"title": "Result", "link": "https://ex.com", "snippet": "snip"}],
            })

        out = await run_search("anything", client=_client(handler))
        assert out["provider"] == "google"
        assert out["results"][0]["url"] == "https://ex.com"
        assert out["result_count"] == 1

    async def test_missing_tavily_key_returns_error(self, monkeypatch) -> None:
        monkeypatch.setenv("LUNA_WEB_SEARCH_PROVIDER", "tavily")
        monkeypatch.delenv("LUNA_TAVILY_API_KEY", raising=False)
        out = await run_search("q", client=_client(lambda r: httpx.Response(200, json={})))
        assert "error" in out and "LUNA_TAVILY_API_KEY" in out["detail"]

    async def test_missing_google_config_returns_error(self, monkeypatch) -> None:
        monkeypatch.setenv("LUNA_WEB_SEARCH_PROVIDER", "google")
        monkeypatch.delenv("LUNA_GOOGLE_SEARCH_API_KEY", raising=False)
        monkeypatch.delenv("LUNA_GOOGLE_SEARCH_CX", raising=False)
        out = await run_search("q", client=_client(lambda r: httpx.Response(200, json={})))
        assert "error" in out and "GOOGLE" in out["detail"].upper()

    async def test_empty_query(self) -> None:
        out = await run_search("   ")
        assert out["error"] == "empty query"

    async def test_http_error_is_caught(self, monkeypatch) -> None:
        monkeypatch.setenv("LUNA_WEB_SEARCH_PROVIDER", "tavily")
        monkeypatch.setenv("LUNA_TAVILY_API_KEY", "x")
        out = await run_search("q", client=_client(lambda r: httpx.Response(500, json={})))
        assert out["error"] == "search request failed" and "500" in out["detail"]


# ---------------- web_fetch ----------------
def test_extract_readable_strips_chrome() -> None:
    html = (
        "<html><head><title>My Page</title><style>.x{}</style></head>"
        "<body><nav>menu</nav><script>evil()</script>"
        "<h1>Hello</h1><p>World of content.</p><footer>foot</footer></body></html>"
    )
    title, text = extract_readable(html)
    assert title == "My Page"
    assert "Hello" in text and "World of content." in text
    assert "evil()" not in text and "menu" not in text and "foot" not in text


@pytest.mark.asyncio
class TestFetch:
    async def test_fetch_html_extracts_text(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<html><head><title>T</title></head><body><p>Readable body.</p></body></html>",
            )

        out = await run_fetch("https://example.com", client=_client(handler))
        assert out["title"] == "T"
        assert "Readable body." in out["content"]
        assert out["status"] == 200

    async def test_fetch_invalid_url(self) -> None:
        out = await run_fetch("ftp://nope")
        assert out["error"] == "invalid url"

    async def test_fetch_404(self) -> None:
        out = await run_fetch(
            "https://example.com/missing",
            client=_client(lambda r: httpx.Response(404, text="nope")),
        )
        assert out["error"] == "fetch failed" and "404" in out["detail"]


# ---------------- http_request ----------------
@pytest.mark.asyncio
class TestHttpRequest:
    async def test_get_json(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            assert req.method == "GET"
            return httpx.Response(200, json={"ok": True, "n": 7}, headers={"content-type": "application/json"})

        out = await run_request("GET", "https://api.example.com/x", client=_client(handler))
        assert out["status"] == 200
        assert out["json"] == {"ok": True, "n": 7}

    async def test_post_body(self) -> None:
        seen = {}

        def handler(req: httpx.Request) -> httpx.Response:
            seen["method"] = req.method
            seen["body"] = req.content.decode()
            return httpx.Response(201, json={"created": True}, headers={"content-type": "application/json"})

        out = await run_request(
            "POST", "https://api.example.com/x", body={"a": 1}, client=_client(handler)
        )
        assert seen["method"] == "POST" and '"a"' in seen["body"]
        assert out["status"] == 201 and out["json"]["created"] is True

    async def test_invalid_method(self) -> None:
        out = await run_request("FLY", "https://x.com")
        assert out["error"] == "invalid method"

    async def test_invalid_url(self) -> None:
        out = await run_request("GET", "file:///etc/passwd")
        assert out["error"] == "invalid url"

    async def test_network_error_caught(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom")

        out = await run_request("GET", "https://x.com", client=_client(handler))
        assert out["error"] == "request failed"


# ---------------- SSRF guard (literal IPs → no DNS/network) ----------------
class TestSsrfGuard:
    def test_blocks_loopback_private_linklocal(self, monkeypatch) -> None:
        monkeypatch.delenv("LUNA_WEB_ALLOW_PRIVATE", raising=False)
        assert blocked_reason("http://127.0.0.1/x")          # loopback
        assert blocked_reason("http://10.0.0.5/")            # private
        assert blocked_reason("http://192.168.1.1/")         # private
        assert blocked_reason("http://169.254.169.254/meta") # cloud metadata
        assert blocked_reason("http://[::1]/")               # ipv6 loopback

    def test_allows_public(self, monkeypatch) -> None:
        monkeypatch.delenv("LUNA_WEB_ALLOW_PRIVATE", raising=False)
        assert blocked_reason("http://8.8.8.8/") is None
        assert blocked_reason("https://1.1.1.1/") is None

    def test_opt_out_env(self, monkeypatch) -> None:
        monkeypatch.setenv("LUNA_WEB_ALLOW_PRIVATE", "1")
        assert blocked_reason("http://127.0.0.1/x") is None

    @pytest.mark.asyncio
    async def test_fetch_blocks_metadata_ip(self, monkeypatch) -> None:
        monkeypatch.delenv("LUNA_WEB_ALLOW_PRIVATE", raising=False)
        out = await run_fetch("http://169.254.169.254/latest/meta-data/")
        assert out["error"] == "blocked"

    @pytest.mark.asyncio
    async def test_http_request_blocks_loopback(self, monkeypatch) -> None:
        monkeypatch.delenv("LUNA_WEB_ALLOW_PRIVATE", raising=False)
        out = await run_request("GET", "http://127.0.0.1:8765/api/health")
        assert out["error"] == "blocked"
