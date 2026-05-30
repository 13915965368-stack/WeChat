from __future__ import annotations

from app.llm.schemas import ToolRuntimeContext
from app.llm.tools.spec import ToolParameterSpec, ToolSpec
from app.services.search_service import is_web_search_available, search_web


def _resolve_search_config(context: ToolRuntimeContext):
    if context.capabilities and context.capabilities.search is not None:
        return context.capabilities.search.config
    return context.search_config


def web_search_availability(context: ToolRuntimeContext) -> bool:
    return is_web_search_available(_resolve_search_config(context))


def web_search_executor(query: str, *, context: ToolRuntimeContext | None = None) -> str:
    if context is None:
        return "搜索功能当前不可用。"
    config = _resolve_search_config(context)
    response = search_web(query, config=config)
    if response.error:
        return f"搜索失败: {response.error}"
    if not response.items:
        return "未找到相关搜索结果。"
    lines = []
    for item in response.items[: config.max_results]:
        lines.append(f"- {item.title}: {item.snippet} ({item.url})")
    return "\n".join(lines)


WEB_SEARCH_TOOL_SPEC = ToolSpec(
    name="web_search",
    description="搜索互联网获取最新信息。当用户询问实时信息、最新新闻、或你不确定的事实时使用此工具。",
    parameters=[
        ToolParameterSpec(
            name="query",
            type="string",
            description="搜索关键词",
            required=True,
        )
    ],
    executor=web_search_executor,
    availability_resolver=web_search_availability,
)

WEB_SEARCH_TOOL_CONFIG = WEB_SEARCH_TOOL_SPEC.to_legacy_config()
