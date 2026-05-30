from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SearchItem:
    title: str
    url: str
    snippet: str = ""


@dataclass(slots=True)
class SearchAttempt:
    provider: str
    success: bool
    duration_ms: int = 0
    error: str | None = None


@dataclass(slots=True)
class SearchResponse:
    provider: str
    query: str
    items: list[SearchItem] = field(default_factory=list)
    cached: bool = False
    error: str | None = None
    attempts: list[SearchAttempt] = field(default_factory=list)


@dataclass(slots=True)
class SearchRuntimeConfigSnapshot:
    web_search_enabled: bool = True
    fallback_enabled: bool = True
    primary_provider: str = "searxng"
    fallback_providers: list[str] = field(default_factory=list)
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 1000
    max_results: int = 5
    request_timeout_seconds: int = 10
    searxng_base_url: str | None = None
    bocha_api_key: str = ""
    bocha_base_url: str | None = None
    tavily_api_key: str = ""
    tavily_base_url: str | None = None
