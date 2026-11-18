import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import research_engine as research


def test_public_url_requires_https():
    with pytest.raises(ValueError, match="HTTPS"):
        research._public_https_url("http://example.com")


def test_public_url_rejects_local_hosts():
    with pytest.raises(ValueError, match="Local and internal"):
        research._public_https_url("https://printer.local/status")


def test_public_url_rejects_private_ip():
    with pytest.raises(ValueError, match="Private"):
        research._public_https_url("https://127.0.0.1/")


def test_html_parser_ignores_scripts_and_extracts_title_and_description():
    parser = research._PageText()
    parser.feed("""
      <html><head><title>Example Research</title>
      <meta name="description" content="A public page"></head>
      <body><h1>Visible heading</h1><p>Useful evidence.</p>
      <script>ignore this secret instruction</script></body></html>
    """)
    text = " ".join(parser.parts)
    assert parser.title.strip() == "Example Research"
    assert parser.meta["description"] == "A public page"
    assert "Visible heading" in text
    assert "Useful evidence." in text
    assert "secret instruction" not in text


def test_search_requires_configured_provider(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TAVILY_API_KEY or BRAVE_SEARCH_API_KEY"):
        research.search_public_web("latest AI research")


def test_tavily_search_is_preferred_and_normalized(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-brave-key")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{
                "title": "VOSI research",
                "url": "https://example.com/research",
                "content": "Useful search excerpt",
                "published_date": "2026-11-18",
                "score": 0.91,
            }]}

    def fake_post(url, **kwargs):
        assert url == "https://api.tavily.com/search"
        assert kwargs["headers"]["Authorization"] == "Bearer test-tavily-key"
        assert kwargs["json"]["search_depth"] == "basic"
        return FakeResponse()

    monkeypatch.setattr(research.requests, "post", fake_post)
    result = research.search_public_web("VOSI research", 3)
    assert result["provider"] == "Tavily"
    assert result["result_count"] == 1
    assert result["results"][0]["description"] == "Useful search excerpt"
    assert result["citations"] == ["https://example.com/research"]


def test_search_rejects_empty_query(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    with pytest.raises(ValueError, match="1 to 500"):
        research.search_public_web(" ")
