from app.llm.tools.registry import register_tool
from app.llm.tools.web_search import WEB_SEARCH_TOOL_CONFIG
from app.llm.tools.knowledge import KNOWLEDGE_SEARCH_TOOL_CONFIG


def register_all_tools() -> None:
    for config in [WEB_SEARCH_TOOL_CONFIG, KNOWLEDGE_SEARCH_TOOL_CONFIG]:
        register_tool(
            name=config["name"],
            description=config["description"],
            parameters=config["parameters"],
            required=config["required"],
            executor=config["executor"],
            availability_resolver=config.get("availability_resolver"),
        )
