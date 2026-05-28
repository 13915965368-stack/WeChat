from __future__ import annotations

from app.llm.schemas import ToolRuntimeContext
from app.services.search_service import is_web_search_available, search_web


def web_search_availability(context: ToolRuntimeContext) -> bool:
    return is_web_search_available(context.search_config)


def web_search_executor(query: str, *, context: ToolRuntimeContext | None = None) -> str:
    if context is None:
        return "搜索功能当前不可用。"
    response = search_web(query, config=context.search_config)
    if response.error:
        return f"搜索失败: {response.error}"
    if not response.items:
        return "未找到相关搜索结果。"
    lines = []
    for item in response.items[: context.search_config.max_results]:
        lines.append(f"- {item.title}: {item.snippet} ({item.url})")
    return "\n".join(lines)


WEB_SEARCH_TOOL_CONFIG = {
    "name": "web_search",
    "description": "搜索互联网获取最新信息。当用户询问实时信息、最新新闻、或你不确定的事实时使用此工具。",
    "parameters": {
        "query": {"type": "string", "description": "搜索关键词"},
    },
    "required": ["query"],
    "executor": web_search_executor,
    "availability_resolver": web_search_availability,
}
