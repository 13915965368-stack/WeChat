from __future__ import annotations

from app.llm.tools.spec import ToolParameterSpec, ToolSpec


def knowledge_search_executor(query: str) -> str:
    return "知识检索功能尚未配置知识库。请先在设置中添加知识源。"


KNOWLEDGE_SEARCH_TOOL_SPEC = ToolSpec(
    name="knowledge_search",
    description="从本地知识库中检索相关信息。当用户询问特定领域知识、项目文档、或需要精确引用时使用此工具。",
    parameters=[
        ToolParameterSpec(
            name="query",
            type="string",
            description="检索关键词或问题",
            required=True,
        )
    ],
    executor=knowledge_search_executor,
)

KNOWLEDGE_SEARCH_TOOL_CONFIG = KNOWLEDGE_SEARCH_TOOL_SPEC.to_legacy_config()
