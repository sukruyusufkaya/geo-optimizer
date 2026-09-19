"""
SerpBase Google SERP provider — optional, opt-in source for `geo citations`
(#527).

`geo citations` observes what AI answer engines actually say by asking them
questions as an LLM. Google AI Overviews can't be observed that way — it's a
SERP feature, not a model you can prompt — so this queries the real SERP via
serpbase.dev (https://serpbase.dev/docs) instead: organic results plus an
`ai_overview` block whenever Google renders one for the query.

Bring-your-own-key, pay-as-you-go (100 free searches, then $0.30/1k) — opt-in
only via `--provider serpbase` / SERPBASE_API_KEY, never part of the default
auto-detection chain in `citations.resolve_provider()`. Kept in its own
module so the default LLM citation path never imports it.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SERPBASE_API_URL = "https://api.serpbase.dev/google/search"
_SERPBASE_TIMEOUT = 30

# serpbase's free tier is 100 searches total; a small fixed delay between
# consecutive calls keeps a multi-query citation run from bursting through
# it. Not a full backoff/retry strategy — just enough spacing for the
# request volumes `geo citations` actually makes (a handful of queries per
# run), per the rate-limiting guard requested in #527.
_SERPBASE_RATE_LIMIT_DELAY = 1.0

# serpbase's docs (as of this writing) confirm ai_overview *can* appear
# ("...ai_overview... when those modules appear in the SERP") but do not
# publish its internal field schema. Live testing against ~20 queries found
# it near-never populated, so this parses defensively across the plausible
# key names rather than asserting one shape — the organic-results check
# still runs unaffected if none match (#527, see the issue's own findings).
_AI_OVERVIEW_TEXT_KEYS = ("text", "content", "summary", "answer")
_AI_OVERVIEW_SOURCES_KEYS = ("sources", "references", "citations", "links", "source_links")
_SOURCE_URL_KEYS = ("url", "link", "href")


@dataclass
class SerpResult:
    """One organic result from a serpbase.dev Google search."""

    title: str = ""
    url: str = ""
    snippet: str = ""


@dataclass
class SerpResponse:
    """Response from a serpbase.dev Google search: organic results, plus an
    optional AI Overview when Google renders one for the query."""

    organic: list[SerpResult] = field(default_factory=list)
    ai_overview_present: bool = False
    ai_overview_text: str = ""
    ai_overview_sources: list[str] = field(default_factory=list)  # URLs cited inside the AI Overview
    error: str | None = None


def _extract_ai_overview(block: dict) -> tuple[str, list[str]]:
    """Best-effort parse of the undocumented ai_overview shape.

    Returns (text, source_urls) — either can be empty if none of the
    plausible keys are present. Never raises on an unexpected shape.
    """
    text = ""
    for key in _AI_OVERVIEW_TEXT_KEYS:
        value = block.get(key)
        if isinstance(value, str) and value:
            text = value
            break

    sources: list[str] = []
    for key in _AI_OVERVIEW_SOURCES_KEYS:
        items = block.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str):
                    sources.append(item)
                elif isinstance(item, dict):
                    for url_key in _SOURCE_URL_KEYS:
                        if item.get(url_key):
                            sources.append(item[url_key])
                            break
            break

    return text, sources


_last_call_at = 0.0


def _rate_limit() -> None:
    global _last_call_at
    elapsed = time.monotonic() - _last_call_at
    if elapsed < _SERPBASE_RATE_LIMIT_DELAY:
        time.sleep(_SERPBASE_RATE_LIMIT_DELAY - elapsed)
    _last_call_at = time.monotonic()


def query_serpbase(query: str, *, api_key: str, hl: str = "en", gl: str = "us") -> SerpResponse:
    """Run a Google search via serpbase.dev.

    Args:
        query: Search query text.
        api_key: serpbase.dev API key (SERPBASE_API_KEY).
        hl: Language code (default "en").
        gl: Country code (default "us").

    Returns:
        SerpResponse with organic results and, when present, the AI Overview.
    """
    import requests

    _rate_limit()
    try:
        resp = requests.post(
            SERPBASE_API_URL,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={"q": query, "hl": hl, "gl": gl},
            timeout=_SERPBASE_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("serpbase query failed: %s: %s", type(exc).__name__, exc)
        return SerpResponse(error=f"{type(exc).__name__}: {exc}")

    # Documented organic shape: rank, title, link (primary URL), url
    # (canonical), snippet, display_url — link is preferred over url since
    # it's the field the docs mark required.
    organic = [
        SerpResult(
            title=r.get("title", ""),
            url=r.get("link") or r.get("url", ""),
            snippet=r.get("snippet", ""),
        )
        for r in (data.get("organic") or [])
        if isinstance(r, dict)
    ]

    ai_overview = data.get("ai_overview")
    if isinstance(ai_overview, dict):
        text, sources = _extract_ai_overview(ai_overview)
        return SerpResponse(
            organic=organic, ai_overview_present=True, ai_overview_text=text, ai_overview_sources=sources
        )

    return SerpResponse(organic=organic)
