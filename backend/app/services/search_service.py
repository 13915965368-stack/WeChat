from __future__ import annotations

from dataclasses import replace

from app.config import Settings
from app.services.search_cache import SearchCache
from app.services.search_providers import SEARCH_PROVIDERS
from app.services.search_types import SearchAttempt, SearchResponse, SearchRuntimeConfigSnapshot

_SEARCH_CACHE: SearchCache | None = None
_SEARCH_CACHE_SIZE: int | None = None


def build_search_runtime_config(settings: Settings) -> SearchRuntimeConfigSnapshot:
    fallback_providers = [
        item.strip().lower()
        for item in settings.search_fallback_providers.split(",")
        if item.strip()
    ]
    return SearchRuntimeConfigSnapshot(
        web_search_enabled=settings.web_search_enabled,
        fallback_enabled=settings.search_fallback_enabled,
        primary_provider=settings.search_primary_provider.strip().lower() or "searxng",
        fallback_providers=fallback_providers,
        cache_ttl_seconds=settings.search_cache_ttl_seconds,
        cache_max_size=settings.search_cache_max_size,
        max_results=settings.search_max_results,
        request_timeout_seconds=settings.search_timeout_seconds,
        searxng_base_url=settings.searxng_base_url.strip() or None,
        bocha_api_key=settings.bocha_api_key,
        bocha_base_url=settings.bocha_base_url.strip() or None,
        tavily_api_key=settings.tavily_api_key,
        tavily_base_url=settings.tavily_base_url.strip() or None,
    )


def _get_cache(config: SearchRuntimeConfigSnapshot) -> SearchCache:
    global _SEARCH_CACHE, _SEARCH_CACHE_SIZE
    max_size = max(1, config.cache_max_size)
    if _SEARCH_CACHE is None or _SEARCH_CACHE_SIZE != max_size:
        _SEARCH_CACHE = SearchCache(max_size=max_size)
        _SEARCH_CACHE_SIZE = max_size
    return _SEARCH_CACHE


def clear_search_cache() -> None:
    global _SEARCH_CACHE, _SEARCH_CACHE_SIZE
    if _SEARCH_CACHE is not None:
        _SEARCH_CACHE.clear()
    _SEARCH_CACHE = None
    _SEARCH_CACHE_SIZE = None


def _iter_provider_names(config: SearchRuntimeConfigSnapshot) -> list[str]:
    ordered: list[str] = []
    for name in [config.primary_provider, *config.fallback_providers]:
        normalized = name.strip().lower()
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    if not config.fallback_enabled and ordered:
        return ordered[:1]
    return ordered


def is_web_search_available(config: SearchRuntimeConfigSnapshot) -> bool:
    if not config.web_search_enabled:
        return False
    for provider_name in _iter_provider_names(config):
        provider = SEARCH_PROVIDERS.get(provider_name)
        if provider and provider.is_available(config):
            return True
    return False


def _select_final_error(attempts: list[SearchAttempt]) -> str:
    actionable_error = next(
        (
            attempt.error
            for attempt in reversed(attempts)
            if attempt.error and attempt.error != "provider unavailable"
        ),
        None,
    )
    if actionable_error:
        return actionable_error

    if attempts and all(attempt.error == "provider unavailable" for attempt in attempts):
        return "all search providers are unavailable"

    fallback_error = next((attempt.error for attempt in reversed(attempts) if attempt.error), None)
    return fallback_error or "all search providers failed"


def search_web(query: str, *, config: SearchRuntimeConfigSnapshot) -> SearchResponse:
    if not config.web_search_enabled:
        return SearchResponse(provider="", query=query, error="web search is disabled")

    cache = _get_cache(config)
    cached = cache.get(query)
    if cached is not None:
        return replace(cached, cached=True)

    attempts: list[SearchAttempt] = []
    for provider_name in _iter_provider_names(config):
        provider = SEARCH_PROVIDERS.get(provider_name)
        if provider is None or not provider.is_available(config):
            attempts.append(SearchAttempt(provider=provider_name, success=False, error="provider unavailable"))
            continue
        response = provider.search(query, config=config)
        attempts.extend(response.attempts)
        if not response.error:
            final_response = replace(response, attempts=list(attempts))
            cache.set(query, final_response, config.cache_ttl_seconds)
            return final_response

    return SearchResponse(
        provider="",
        query=query,
        error=_select_final_error(attempts),
        attempts=attempts,
    )
