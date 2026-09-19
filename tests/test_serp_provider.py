"""Tests for the serpbase.dev Google SERP provider (#527).

All HTTP calls are mocked — zero real network calls, zero real API credits.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

import geo_optimizer.core.serp_provider as serp_provider
from geo_optimizer.core.serp_provider import SerpResponse, SerpResult, query_serpbase


@pytest.fixture(autouse=True)
def _no_real_rate_limit_sleep(monkeypatch):
    """The rate limiter uses module-global state + a real time.sleep — fine in
    production, but would make every test in this file pay up to 1s of real
    sleep depending on test order. Neutralize it by default; the dedicated
    rate-limit test below overrides this to actually observe the behavior."""
    monkeypatch.setattr(serp_provider, "_last_call_at", 0.0)
    monkeypatch.setattr(serp_provider.time, "sleep", lambda _seconds: None)


def _fake_post_factory(json_body: dict):
    def _fake_post(url, headers, json, timeout):
        assert url == serp_provider.SERPBASE_API_URL
        assert headers["X-API-Key"] == "sb-test"
        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json = Mock(return_value=json_body)
        return resp

    return _fake_post


class TestQuerySerpbase:
    def test_organic_only_response(self, monkeypatch):
        """No ai_overview key at all — organic results parsed, ai_overview absent."""
        monkeypatch.setattr(
            "requests.post",
            _fake_post_factory(
                {
                    "organic": [
                        {"rank": 1, "title": "Acme", "link": "https://acme.com/", "snippet": "Acme home"},
                        {"rank": 2, "title": "Other", "link": "https://other.com/post", "snippet": "unrelated"},
                    ]
                }
            ),
        )
        result = query_serpbase("best CRM", api_key="sb-test")

        assert result.error is None
        assert result.ai_overview_present is False
        assert len(result.organic) == 2
        assert result.organic[0] == SerpResult(title="Acme", url="https://acme.com/", snippet="Acme home")

    def test_organic_falls_back_to_url_field_when_link_missing(self, monkeypatch):
        monkeypatch.setattr(
            "requests.post",
            _fake_post_factory({"organic": [{"title": "Acme", "url": "https://acme.com/", "snippet": "x"}]}),
        )
        result = query_serpbase("q", api_key="sb-test")
        assert result.organic[0].url == "https://acme.com/"

    def test_ai_overview_with_text_and_sources_key(self, monkeypatch):
        monkeypatch.setattr(
            "requests.post",
            _fake_post_factory(
                {
                    "organic": [],
                    "ai_overview": {
                        "text": "Acme is a leading CRM.",
                        "sources": [{"url": "https://acme.com/"}, {"link": "https://review.com/acme"}],
                    },
                }
            ),
        )
        result = query_serpbase("best CRM", api_key="sb-test")

        assert result.ai_overview_present is True
        assert result.ai_overview_text == "Acme is a leading CRM."
        assert result.ai_overview_sources == ["https://acme.com/", "https://review.com/acme"]

    def test_ai_overview_with_string_sources(self, monkeypatch):
        """Defensive parse: sources as a bare list of URL strings, not dicts."""
        monkeypatch.setattr(
            "requests.post",
            _fake_post_factory(
                {"organic": [], "ai_overview": {"content": "Overview text", "references": ["https://acme.com/"]}}
            ),
        )
        result = query_serpbase("q", api_key="sb-test")

        assert result.ai_overview_present is True
        assert result.ai_overview_text == "Overview text"
        assert result.ai_overview_sources == ["https://acme.com/"]

    def test_ai_overview_present_but_unparseable_shape_does_not_crash(self, monkeypatch):
        """An ai_overview block with none of the expected keys must not raise —
        it's credited as present with empty text/sources rather than failing
        the whole query."""
        monkeypatch.setattr(
            "requests.post",
            _fake_post_factory({"organic": [], "ai_overview": {"totally_unexpected_key": 123}}),
        )
        result = query_serpbase("q", api_key="sb-test")

        assert result.ai_overview_present is True
        assert result.ai_overview_text == ""
        assert result.ai_overview_sources == []

    def test_network_error_returns_error_response(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise ConnectionError("down")

        monkeypatch.setattr("requests.post", _boom)
        result = query_serpbase("q", api_key="sb-test")

        assert isinstance(result, SerpResponse)
        assert result.error is not None
        assert "ConnectionError" in result.error

    def test_rate_limit_sleeps_between_consecutive_calls(self, monkeypatch):
        """Two calls in quick succession must be spaced out (#527 rate-limit guard)."""
        monkeypatch.setattr("requests.post", _fake_post_factory({"organic": []}))
        sleep_calls = []
        monkeypatch.setattr(serp_provider.time, "sleep", lambda s: sleep_calls.append(s))

        query_serpbase("q1", api_key="sb-test")
        query_serpbase("q2", api_key="sb-test")

        # First call has no prior _last_call_at within the window, second should sleep.
        assert len(sleep_calls) >= 1
