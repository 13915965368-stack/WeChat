from __future__ import annotations

from app.llm.schemas import SearchRuntimeConfigSnapshot, ToolRuntimeContext
from app.llm.tools.registry import clear_tools, execute_tool, get_tool_definitions
from app.llm.tools.web_search import WEB_SEARCH_TOOL_CONFIG
from app.llm.tools.registry import register_tool
from app.services.search_types import SearchItem, SearchResponse


def _context(**overrides) -> ToolRuntimeContext:
    config = SearchRuntimeConfigSnapshot(
        web_search_enabled=True,
        fallback_enabled=True,
        primary_provider="searxng",
        fallback_providers=["duckduckgo"],
        cache_ttl_seconds=3600,
        cache_max_size=1000,
        max_results=5,
        request_timeout_seconds=10,
        searxng_base_url="http://searx.local",
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return ToolRuntimeContext(
        conversation_id="conv-1",
        agent_id="agent-1",
        agent_name="Tester",
        is_group=False,
        search_config=config,
    )


def setup_function():
    clear_tools()
    register_tool(
        name=WEB_SEARCH_TOOL_CONFIG["name"],
        description=WEB_SEARCH_TOOL_CONFIG["description"],
        parameters=WEB_SEARCH_TOOL_CONFIG["parameters"],
        required=WEB_SEARCH_TOOL_CONFIG["required"],
        executor=WEB_SEARCH_TOOL_CONFIG["executor"],
        availability_resolver=WEB_SEARCH_TOOL_CONFIG["availability_resolver"],
    )


def teardown_function():
    clear_tools()


def test_web_search_visibility_depends_on_runtime_context():
    visible = get_tool_definitions(_context())
    hidden = get_tool_definitions(_context(web_search_enabled=False, searxng_base_url=None, fallback_providers=[]))
    assert any(tool.name == "web_search" for tool in visible)
    assert all(tool.name != "web_search" for tool in hidden)


def test_web_search_visibility_supports_bocha_provider():
    visible = get_tool_definitions(
        _context(
            primary_provider="bocha",
            searxng_base_url=None,
            fallback_providers=[],
            bocha_api_key="bocha-secret",
        )
    )
    assert any(tool.name == "web_search" for tool in visible)


def test_web_search_executor_formats_results(monkeypatch):
    from app.llm.tools import web_search

    monkeypatch.setattr(
        web_search,
        "search_web",
        lambda query, config: SearchResponse(
            provider="searxng",
            query=query,
            items=[SearchItem(title="标题", url="https://example.com", snippet="摘要")],
        ),
    )
    result = execute_tool("web_search", {"query": "测试"}, context=_context())
    assert "标题" in result
    assert "https://example.com" in result


def test_web_search_executor_returns_error_text(monkeypatch):
    from app.llm.tools import web_search

    monkeypatch.setattr(
        web_search,
        "search_web",
        lambda query, config: SearchResponse(provider="", query=query, error="provider down"),
    )
    result = execute_tool("web_search", {"query": "测试"}, context=_context())
    assert result == "搜索失败: provider down"
