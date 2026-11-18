"""Source-backed public-web research for VOSI.

Search uses the Brave Search API when configured. Page reading is restricted to
public HTTPS URLs and rejects private/local network destinations and unsafe redirects.
Website text is untrusted evidence, never executable instructions.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/research", tags=["VOSI Research"])
MAX_HTML_BYTES = 1_500_000
MAX_TEXT_CHARS = 18_000
MAX_RESULTS = 10
TIMEOUT = (5, 15)
USER_AGENT = "VOSIResearch/1.0 (+public-page-reading; contact: operator)"


def _authorize(authorization: str | None) -> None:
    import hmac
    expected = os.getenv("VOSI_AGENT_TOKEN", "").strip()
    scheme, _, supplied = (authorization or "").partition(" ")
    if not expected:
        raise HTTPException(status_code=503, detail="Research API is disabled until VOSI_AGENT_TOKEN is configured.")
    if scheme.lower() != "bearer" or not supplied:
        raise HTTPException(status_code=401, detail="Invalid VOSI research token.")
    if expected and hmac.compare_digest(supplied.strip(), expected):
        return
    # Paired browser/Android/desktop devices may use their own scoped device token.
    try:
        from agent_api import devices
        devices.authenticate(supplied.strip())
        return
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid VOSI research token.")


def _public_https_url(value: str) -> str:
    raw = (value or "").strip()
    if len(raw) > 2048:
        raise ValueError("URL exceeds 2048 characters.")
    parsed = urlsplit(raw)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("Only absolute HTTPS public website URLs are supported.")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Embedded credentials and non-standard ports are not allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("Local and internal network hosts are not allowed.")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise ValueError("Website host could not be resolved.") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private, loopback, link-local and reserved network addresses are not allowed.")
    return raw


class _PageText(HTMLParser):
    BLOCKED = {"script", "style", "noscript", "svg", "canvas", "template"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "section", "article"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.title = ""
        self.in_title = False
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in self.BLOCKED:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = (values.get("name") or values.get("property") or "").lower()
            if key in {"description", "og:description", "og:title"} and values.get("content"):
                self.meta[key] = values["content"][:500]
        if tag in self.BLOCK and not self.skip:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BLOCKED and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False
        if tag in self.BLOCK and not self.skip:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        clean = re.sub(r"\\s+", " ", data).strip()
        if clean:
            if self.in_title:
                self.title += clean + " "
            self.parts.append(clean)


def read_public_page(url: str) -> dict[str, Any]:
    current = _public_https_url(url)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    response = None
    try:
        for _ in range(4):
            # Revalidate each redirect destination; never follow redirects blindly.
            response = session.get(current, timeout=TIMEOUT, allow_redirects=False, stream=True)
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise ValueError("Website returned an invalid redirect.")
                current = _public_https_url(urljoin(current, location))
                continue
            break
        else:
            raise ValueError("Website redirected too many times.")
        if response is None:
            raise ValueError("Website did not return a response.")
        if response.status_code >= 400:
            raise ValueError(f"Website returned HTTP {response.status_code}.")
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            raise ValueError("Only HTML pages can be read by this research endpoint.")
        chunks, total = [], 0
        for chunk in response.iter_content(16384):
            total += len(chunk)
            if total > MAX_HTML_BYTES:
                raise ValueError("Website page exceeds the 1.5 MB reading limit.")
            chunks.append(chunk)
        parser = _PageText()
        parser.feed(b"".join(chunks).decode(response.encoding or "utf-8", errors="replace"))
        text = re.sub(r"[ \\t]+", " ", " ".join(parser.parts))
        text = re.sub(r"\\n\\s*\\n+", "\\n", text).strip()[:MAX_TEXT_CHARS]
        if not text:
            raise ValueError("No readable text was found on this page.")
        return {
            "title": parser.title.strip()[:300] or parser.meta.get("og:title", ""),
            "url": current,
            "description": parser.meta.get("description") or parser.meta.get("og:description", ""),
            "text": text,
            "character_count": len(text),
            "source_type": "public_webpage",
            "read_only": True,
        }
    finally:
        if response is not None:
            response.close()
        session.close()


def search_public_web(query: str, count: int = 5) -> dict[str, Any]:
    query = (query or "").strip()
    if not query or len(query) > 500:
        raise ValueError("Research query must contain 1 to 500 characters.")
    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Web search is not configured. Set BRAVE_SEARCH_API_KEY to enable source-backed internet research.")
    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": max(1, min(int(count), MAX_RESULTS)), "safesearch": "moderate"},
        headers={"X-Subscription-Token": api_key, "Accept": "application/json", "User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    results = []
    for item in (payload.get("web") or {}).get("results", [])[:MAX_RESULTS]:
        url = item.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        results.append({
            "title": str(item.get("title") or "")[:300],
            "url": url[:2048],
            "description": str(item.get("description") or "")[:1000],
            "published": item.get("age") or item.get("page_age"),
            "source": urlsplit(url).hostname,
        })
    return {"query": query, "results": results, "result_count": len(results), "provider": "Brave Search", "citations": [item["url"] for item in results]}


class ResearchSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    count: int = Field(default=5, ge=1, le=10)


class ResearchReadRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


@router.post("/search")
def research_search(request: ResearchSearchRequest, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    try:
        return {"success": True, **search_public_web(request.query, request.count)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Web search provider is temporarily unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/read")
def research_read(request: ResearchReadRequest, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    try:
        return {"success": True, **read_public_page(request.url)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="The website could not be read right now.") from exc
