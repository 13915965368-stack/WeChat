from __future__ import annotations


def knowledge_search_executor(query: str) -> str:
    return "知识检索功能尚未配置知识库。请先在设置中添加知识源。"


KNOWLEDGE_SEARCH_TOOL_CONFIG = {
    "name": "knowledge_search",
    "description": "从本地知识库中检索相关信息。当用户询问特定领域知识、项目文档、或需要精确引用时使用此工具。",
    "parameters": {
        "query": {"type": "string", "description": "检索关键词或问题"},
    },
    "required": ["query"],
    "executor": knowledge_search_executor,
}
