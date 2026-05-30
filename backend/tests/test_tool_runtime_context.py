from app.llm.schemas import ToolRuntimeContext
from app.llm.tools.capabilities import SearchCapability, ToolCapabilities
from app.llm.tools.tool_services import ToolServices
from app.services.search_types import SearchRuntimeConfigSnapshot


def test_tool_runtime_context_defaults_have_no_services():
    ctx = ToolRuntimeContext()
    assert ctx.services is None


def test_tool_runtime_context_accepts_services():
    services = ToolServices(db_session_factory=lambda: None)
    ctx = ToolRuntimeContext(conversation_id="c1", services=services)
    assert ctx.services is services
    assert callable(ctx.services.db_session_factory)


def test_tool_runtime_context_accepts_capabilities():
    caps = ToolCapabilities(
        search=SearchCapability(config=SearchRuntimeConfigSnapshot(max_results=3)),
        services=ToolServices(db_session_factory=lambda: None),
    )
    ctx = ToolRuntimeContext(conversation_id="c1", capabilities=caps)
    assert ctx.capabilities is caps
    assert ctx.capabilities.search.config.max_results == 3


def test_tool_runtime_context_keeps_legacy_search_config_for_compat():
    ctx = ToolRuntimeContext(search_config=SearchRuntimeConfigSnapshot(max_results=7))
    assert ctx.search_config.max_results == 7
