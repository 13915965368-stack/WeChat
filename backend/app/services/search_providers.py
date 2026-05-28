from __future__ import annotations

from abc import ABC, abstractmethod
import time

import httpx

from app.llm.schemas import SearchRuntimeConfigSnapshot
from app.services.search_types import SearchAttempt, SearchItem, SearchResponse


class BaseSearchProvider(ABC):
    name = "base"

    @abstractmethod
    def is_available(self, config: SearchRuntimeConfigSnapshot) -> bool:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, *, config: SearchRuntimeConfigSnapshot) -> SearchResponse:
        raise NotImplementedError

    def validate(self, config: SearchRuntimeConfigSnapshot) -> tuple[bool, str]:
        return self.is_available(config), "available" if self.is_available(config) else "missing configuration"


class SearxngSearchProvider(BaseSearchProvider):
    name = "searxng"

    def is_available(self, config: SearchRuntimeConfigSnapshot) -> bool:
        return bool((config.searxng_base_url or "").strip())

    def search(self, query: str, *, config: SearchRuntimeConfigSnapshot) -> SearchResponse:
        started = time.perf_counter()
        base_url = (config.searxng_base_url or "").rstrip("/")
        try:
            response = httpx.get(
                f"{base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "language": "zh-CN",
                },
                timeout=config.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            items = [
                SearchItem(
                    title=str(item.get("title", "")),
                    url=str(item.get("url", "")),
                    snippet=str(item.get("content", item.get("snippet", ""))),
                )
                for item in payload.get("results", [])[: config.max_results]
            ]
            return SearchResponse(
                provider=self.name,
                query=query,
                items=items,
                attempts=[SearchAttempt(provider=self.name, success=True, duration_ms=int((time.perf_counter() - started) * 1000))],
            )
        except Exception as exc:
            return SearchResponse(
                provider=self.name,
                query=query,
                error=str(exc),
                attempts=[SearchAttempt(provider=self.name, success=False, duration_ms=int((time.perf_counter() - started) * 1000), error=str(exc))],
            )


class BochaSearchProvider(BaseSearchProvider):
    name = "bocha"

    def is_available(self, config: SearchRuntimeConfigSnapshot) -> bool:
        return bool(config.bocha_api_key.strip())

    def search(self, query: str, *, config: SearchRuntimeConfigSnapshot) -> SearchResponse:
        started = time.perf_counter()
        url = (config.bocha_base_url or "https://api.bocha.cn/v1/web-search").strip()
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {config.bocha_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "summary": True,
                    "count": config.max_results,
                },
                timeout=config.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            web_pages = payload.get("data", payload).get("webPages", {}).get("value", [])
            items = [
                SearchItem(
                    title=str(item.get("name", "")),
                    url=str(item.get("url", "")),
                    snippet=str(item.get("summary", item.get("snippet", ""))),
                )
                for item in web_pages[: config.max_results]
            ]
            return SearchResponse(
                provider=self.name,
                query=query,
                items=items,
                attempts=[SearchAttempt(provider=self.name, success=True, duration_ms=int((time.perf_counter() - started) * 1000))],
            )
        except Exception as exc:
            return SearchResponse(
                provider=self.name,
                query=query,
                error=str(exc),
                attempts=[SearchAttempt(provider=self.name, success=False, duration_ms=int((time.perf_counter() - started) * 1000), error=str(exc))],
            )


class TavilySearchProvider(BaseSearchProvider):
    name = "tavily"

    def is_available(self, config: SearchRuntimeConfigSnapshot) -> bool:
        return bool(config.tavily_api_key.strip())

    def search(self, query: str, *, config: SearchRuntimeConfigSnapshot) -> SearchResponse:
        started = time.perf_counter()
        url = (config.tavily_base_url or "https://api.tavily.com/search").strip()
        try:
            response = httpx.post(
                url,
                json={
                    "api_key": config.tavily_api_key,
                    "query": query,
                    "max_results": config.max_results,
                },
                timeout=config.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            items = [
                SearchItem(
                    title=str(item.get("title", "")),
                    url=str(item.get("url", "")),
                    snippet=str(item.get("content", "")),
                )
                for item in payload.get("results", [])[: config.max_results]
            ]
            return SearchResponse(
                provider=self.name,
                query=query,
                items=items,
                attempts=[SearchAttempt(provider=self.name, success=True, duration_ms=int((time.perf_counter() - started) * 1000))],
            )
        except Exception as exc:
            return SearchResponse(
                provider=self.name,
                query=query,
                error=str(exc),
                attempts=[SearchAttempt(provider=self.name, success=False, duration_ms=int((time.perf_counter() - started) * 1000), error=str(exc))],
            )


class DuckDuckGoSearchProvider(BaseSearchProvider):
    name = "duckduckgo"

    def is_available(self, config: SearchRuntimeConfigSnapshot) -> bool:  # noqa: ARG002
        return True

    def search(self, query: str, *, config: SearchRuntimeConfigSnapshot) -> SearchResponse:
        started = time.perf_counter()
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=config.max_results))
            items = [
                SearchItem(
                    title=str(item.get("title", "")),
                    url=str(item.get("href", "")),
                    snippet=str(item.get("body", "")),
                )
                for item in results[: config.max_results]
            ]
            return SearchResponse(
                provider=self.name,
                query=query,
                items=items,
                attempts=[SearchAttempt(provider=self.name, success=True, duration_ms=int((time.perf_counter() - started) * 1000))],
            )
        except ImportError:
            message = "duckduckgo-search is not installed"
            return SearchResponse(
                provider=self.name,
                query=query,
                error=message,
                attempts=[SearchAttempt(provider=self.name, success=False, duration_ms=int((time.perf_counter() - started) * 1000), error=message)],
            )
        except Exception as exc:
            return SearchResponse(
                provider=self.name,
                query=query,
                error=str(exc),
                attempts=[SearchAttempt(provider=self.name, success=False, duration_ms=int((time.perf_counter() - started) * 1000), error=str(exc))],
            )


SEARCH_PROVIDERS: dict[str, BaseSearchProvider] = {
    SearxngSearchProvider.name: SearxngSearchProvider(),
    BochaSearchProvider.name: BochaSearchProvider(),
    TavilySearchProvider.name: TavilySearchProvider(),
    DuckDuckGoSearchProvider.name: DuckDuckGoSearchProvider(),
}
