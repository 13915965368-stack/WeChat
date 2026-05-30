from pydantic import BaseModel, ConfigDict

from app.llm.schemas import ToolResult, ToolRuntimeContext
from app.llm.tools.capabilities import SearchCapability, ToolCapabilities
from app.llm.tools.middleware import ToolCallContext, ToolMiddleware
from app.llm.tools.registry import (
    clear_tools,
    execute_tool_full,
    get_tool_definitions,
    register_tool_middleware,
    register_tool_spec,
)
from app.llm.tools.spec import ToolParameterSpec, ToolSpec
from app.llm.tools.tool_services import ToolServices
from app.services.search_types import SearchRuntimeConfigSnapshot


class ProbeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: str


class AuditMiddleware(ToolMiddleware):
    def __init__(self):
        self.calls = []

    def before_call(self, ctx: ToolCallContext) -> ToolCallContext:
        self.calls.append(("before", ctx.spec.name, dict(ctx.arguments)))
        return ctx

    def after_call(self, ctx: ToolCallContext, result):
        self.calls.append(("after", ctx.spec.name, result.text))
        return result

    def on_error(self, ctx: ToolCallContext, error: Exception):
        self.calls.append(("error", ctx.spec.name, str(error)))
        return None


def test_governance_probe_tool_can_access_db_and_return_struct():
    clear_tools()
    captured: dict[str, object] = {}
    audit = AuditMiddleware()

    def probe(*, scope: str, context: ToolRuntimeContext) -> ToolResult:
        services = None
        if context.capabilities and context.capabilities.services is not None:
            services = context.capabilities.services
        elif context.services is not None:
            services = context.services
        db = services.db_session_factory() if services else None
        captured["db"] = db
        captured["scope"] = scope
        return ToolResult(text=f"applied {scope}", data={"scope": scope}, is_error=False)

    register_tool_middleware(audit)
    register_tool_spec(
        ToolSpec(
            name="set_context_rounds_probe",
            description="probe",
            parameters=[
                ToolParameterSpec(
                    name="scope",
                    type="string",
                    enum=["thread", "conversation"],
                    required=True,
                )
            ],
            executor=probe,
            args_model=ProbeArgs,
            availability_resolver=lambda ctx: ctx.is_group,
        )
    )

    hidden = get_tool_definitions(ToolRuntimeContext(is_group=False))
    assert all(definition.name != "set_context_rounds_probe" for definition in hidden)

    visible = get_tool_definitions(ToolRuntimeContext(is_group=True))
    assert any(definition.name == "set_context_rounds_probe" for definition in visible)

    probe_def = next(definition for definition in visible if definition.name == "set_context_rounds_probe")
    assert probe_def.parameters.properties["scope"].enum == ["thread", "conversation"]

    sentinel = object()
    ctx = ToolRuntimeContext(
        is_group=True,
        capabilities=ToolCapabilities(
            search=SearchCapability(config=SearchRuntimeConfigSnapshot()),
            services=ToolServices(db_session_factory=lambda: sentinel),
        ),
    )
    result = execute_tool_full("set_context_rounds_probe", {"scope": "thread"}, context=ctx)
    assert result.is_error is False
    assert result.data == {"scope": "thread"}
    assert captured["db"] is sentinel
    assert captured["scope"] == "thread"
    assert audit.calls[0] == ("before", "set_context_rounds_probe", {"scope": "thread"})
    assert audit.calls[-1] == ("after", "set_context_rounds_probe", "applied thread")
    clear_tools()
