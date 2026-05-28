from __future__ import annotations
from types import SimpleNamespace

from app.config import Settings
from app.llm.schemas import SearchRuntimeConfigSnapshot
from app.services.search_service import clear_search_cache, is_web_search_available, search_web
from app.services.search_providers import BochaSearchProvider
from app.services.search_types import SearchAttempt, SearchItem, SearchResponse


class _Provider:
    def __init__(self, name: str, *, available: bool = True, error: str | None = None) -> None:
        self.name = name
        self.available = available
        self.error = error
        self.calls = 0

    def is_available(self, config: SearchRuntimeConfigSnapshot) -> bool:  # noqa: ARG002
        return self.available

    def search(self, query: str, *, config: SearchRuntimeConfigSnapshot) -> SearchResponse:  # noqa: ARG002
        self.calls += 1
        return SearchResponse(
            provider=self.name,
            query=query,
            items=[] if self.error else [SearchItem(title=f"{self.name} title", url="https://example.com", snippet="summary")],
            error=self.error,
            attempts=[SearchAttempt(provider=self.name, success=self.error is None, error=self.error)],
        )


def _config(**overrides) -> SearchRuntimeConfigSnapshot:
    base = SearchRuntimeConfigSnapshot(
        web_search_enabled=True,
        fallback_enabled=True,
        primary_provider="searxng",
        fallback_providers=["tavily", "duckduckgo"],
        cache_ttl_seconds=3600,
        cache_max_size=2,
        max_results=5,
        request_timeout_seconds=10,
        searxng_base_url="http://searx.local",
        bocha_api_key="",
        bocha_base_url=None,
        tavily_api_key="secret",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_is_web_search_available_respects_runtime_config(monkeypatch):
    from app.services import search_service

    searxng = _Provider("searxng", available=True)
    monkeypatch.setattr(search_service, "SEARCH_PROVIDERS", {"searxng": searxng})
    assert is_web_search_available(_config()) is True
    assert is_web_search_available(_config(web_search_enabled=False)) is False


def test_build_search_runtime_config_includes_bocha_settings():
    from app.services.search_service import build_search_runtime_config

    runtime_config = build_search_runtime_config(
        Settings(
            search_primary_provider="bocha",
            search_fallback_providers="tavily,duckduckgo",
            bocha_api_key="bocha-secret",
            bocha_base_url="https://api.bocha.cn/v1/web-search",
        )
    )

    assert runtime_config.primary_provider == "bocha"
    assert runtime_config.bocha_api_key == "bocha-secret"
    assert runtime_config.bocha_base_url == "https://api.bocha.cn/v1/web-search"
    assert runtime_config.fallback_providers == ["tavily", "duckduckgo"]


def test_search_web_uses_primary_provider(monkeypatch):
    from app.services import search_service

    clear_search_cache()
    searxng = _Provider("searxng")
    tavily = _Provider("tavily")
    monkeypatch.setattr(search_service, "SEARCH_PROVIDERS", {"searxng": searxng, "tavily": tavily})

    response = search_web("最新消息", config=_config(fallback_providers=["tavily"]))
    assert response.provider == "searxng"
    assert searxng.calls == 1
    assert tavily.calls == 0


def test_search_web_uses_bocha_primary_provider(monkeypatch):
    from app.services import search_service

    clear_search_cache()
    bocha = _Provider("bocha")
    tavily = _Provider("tavily")
    monkeypatch.setattr(search_service, "SEARCH_PROVIDERS", {"bocha": bocha, "tavily": tavily})

    response = search_web(
        "最新消息",
        config=_config(
            primary_provider="bocha",
            fallback_providers=["tavily"],
            bocha_api_key="bocha-secret",
        ),
    )
    assert response.provider == "bocha"
    assert bocha.calls == 1
    assert tavily.calls == 0


def test_search_web_falls_back_when_primary_fails(monkeypatch):
    from app.services import search_service

    clear_search_cache()
    searxng = _Provider("searxng", error="down")
    tavily = _Provider("tavily")
    monkeypatch.setattr(search_service, "SEARCH_PROVIDERS", {"searxng": searxng, "tavily": tavily})

    response = search_web("最新消息", config=_config(fallback_providers=["tavily"]))
    assert response.provider == "tavily"
    assert searxng.calls == 1
    assert tavily.calls == 1


def test_search_web_respects_fallback_disabled(monkeypatch):
    from app.services import search_service

    clear_search_cache()
    searxng = _Provider("searxng", error="down")
    tavily = _Provider("tavily")
    monkeypatch.setattr(search_service, "SEARCH_PROVIDERS", {"searxng": searxng, "tavily": tavily})

    response = search_web("最新消息", config=_config(fallback_enabled=False, fallback_providers=["tavily"]))
    assert response.error == "down"
    assert searxng.calls == 1
    assert tavily.calls == 0


def test_search_web_prefers_actionable_error_over_provider_unavailable(monkeypatch):
    from app.services import search_service

    clear_search_cache()
    bocha = _Provider("bocha", error="401 unauthorized")
    tavily = _Provider("tavily", available=False)
    monkeypatch.setattr(search_service, "SEARCH_PROVIDERS", {"bocha": bocha, "tavily": tavily})

    response = search_web(
        "最新消息",
        config=_config(
            primary_provider="bocha",
            fallback_providers=["tavily"],
            bocha_api_key="bocha-secret",
        ),
    )
    assert response.error == "401 unauthorized"
    assert response.attempts[-1].error == "provider unavailable"


def test_search_web_returns_generic_error_when_all_providers_are_unavailable(monkeypatch):
    from app.services import search_service

    clear_search_cache()
    bocha = _Provider("bocha", available=False)
    tavily = _Provider("tavily", available=False)
    monkeypatch.setattr(search_service, "SEARCH_PROVIDERS", {"bocha": bocha, "tavily": tavily})

    response = search_web(
        "最新消息",
        config=_config(
            primary_provider="bocha",
            fallback_providers=["tavily"],
            bocha_api_key="",
            tavily_api_key="",
        ),
    )
    assert response.error == "all search providers are unavailable"


def test_search_web_uses_normalized_cache_keys(monkeypatch):
    from app.services import search_service

    clear_search_cache()
    searxng = _Provider("searxng")
    monkeypatch.setattr(search_service, "SEARCH_PROVIDERS", {"searxng": searxng})

    search_web("  Latest   News ", config=_config(fallback_providers=[]))
    cached = search_web("latest news", config=_config(fallback_providers=[]))
    assert cached.cached is True
    assert searxng.calls == 1


def test_search_cache_evicts_oldest_entry(monkeypatch):
    from app.services import search_service

    clear_search_cache()
    searxng = _Provider("searxng")
    monkeypatch.setattr(search_service, "SEARCH_PROVIDERS", {"searxng": searxng})

    config = _config(cache_max_size=2, fallback_providers=[])
    search_web("a", config=config)
    search_web("b", config=config)
    search_web("c", config=config)
    search_web("a", config=config)
    assert searxng.calls == 4


def test_bocha_provider_maps_response_payload(monkeypatch):
    from app.services import search_providers

    provider = BochaSearchProvider()

    def fake_post(url, *, headers, json, timeout):  # noqa: ANN001
        assert url == "https://api.bocha.cn/v1/web-search"
        assert headers["Authorization"] == "Bearer bocha-secret"
        assert json == {"query": "测试", "summary": True, "count": 3}
        assert timeout == 10
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "data": {
                    "webPages": {
                        "value": [
                            {
                                "name": "标题",
                                "url": "https://example.com",
                                "summary": "摘要",
                                "snippet": "片段",
                            }
                        ]
                    }
                }
            },
        )

    monkeypatch.setattr(search_providers.httpx, "post", fake_post)

    response = provider.search(
        "测试",
        config=_config(
            primary_provider="bocha",
            max_results=3,
            bocha_api_key="bocha-secret",
        ),
    )

    assert response.provider == "bocha"
    assert response.error is None
    assert response.items == [SearchItem(title="标题", url="https://example.com", snippet="摘要")]
