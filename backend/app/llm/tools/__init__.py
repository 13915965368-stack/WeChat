from app.llm.tools.knowledge import KNOWLEDGE_SEARCH_TOOL_SPEC
from app.llm.tools.registry import register_tool_spec
from app.llm.tools.web_search import WEB_SEARCH_TOOL_SPEC


def register_all_tools() -> None:
    for spec in [WEB_SEARCH_TOOL_SPEC, KNOWLEDGE_SEARCH_TOOL_SPEC]:
        register_tool_spec(spec)
