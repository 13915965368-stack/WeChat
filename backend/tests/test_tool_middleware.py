from app.llm.schemas import ToolResult
from app.llm.tools.middleware import ToolCallContext, ToolMiddleware
from app.llm.tools.registry import clear_tools, execute_tool_full, register_tool_middleware, register_tool_spec
from app.llm.tools.spec import ToolParameterSpec, ToolSpec


class PrefixMiddleware(ToolMiddleware):
    def before_call(self, ctx: ToolCallContext) -> ToolCallContext:
        ctx.arguments["text"] = f"prefix-{ctx.arguments['text']}"
        return ctx

    def after_call(self, ctx: ToolCallContext, result: ToolResult) -> ToolResult:
        return ToolResult(text=f"{result.text}-done", data=result.data, is_error=result.is_error)

    def on_error(self, ctx: ToolCallContext, error: Exception) -> ToolResult | None:
        return None


def test_tool_middlewares_can_intercept_arguments_and_result():
    clear_tools()
    register_tool_middleware(PrefixMiddleware())
    register_tool_spec(
        ToolSpec(
            name="typed_echo",
            description="typed echo",
            parameters=[ToolParameterSpec(name="text", type="string", required=True)],
            executor=lambda text: text,
        )
    )
    result = execute_tool_full("typed_echo", {"text": "hello"})
    assert result.text == "prefix-hello-done"
