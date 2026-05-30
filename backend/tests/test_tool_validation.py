from pydantic import BaseModel, ConfigDict

from app.llm.tools.registry import clear_tools, execute_tool_full, register_tool_spec
from app.llm.tools.spec import ToolParameterSpec, ToolSpec


class EchoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    count: int = 1


def test_execute_tool_full_rejects_missing_required_argument():
    clear_tools()
    register_tool_spec(
        ToolSpec(
            name="typed_echo",
            description="typed echo",
            parameters=[
                ToolParameterSpec(name="text", type="string", required=True),
                ToolParameterSpec(name="count", type="integer", required=False, default=1),
            ],
            args_model=EchoArgs,
            executor=lambda text, count=1: f"{text}:{count}",
        )
    )
    result = execute_tool_full("typed_echo", {})
    assert result.is_error is True
    assert "text" in result.text


def test_execute_tool_full_rejects_unknown_argument():
    clear_tools()
    register_tool_spec(
        ToolSpec(
            name="typed_echo",
            description="typed echo",
            parameters=[ToolParameterSpec(name="text", type="string", required=True)],
            args_model=EchoArgs,
            executor=lambda text, count=1: f"{text}:{count}",
        )
    )
    result = execute_tool_full("typed_echo", {"text": "ok", "unknown": "x"})
    assert result.is_error is True
    assert "unknown" in result.text.lower() or "extra" in result.text.lower()


def test_execute_tool_full_validates_and_normalizes_arguments():
    clear_tools()
    register_tool_spec(
        ToolSpec(
            name="typed_echo",
            description="typed echo",
            parameters=[
                ToolParameterSpec(name="text", type="string", required=True),
                ToolParameterSpec(name="count", type="integer", required=False, default=1),
            ],
            args_model=EchoArgs,
            executor=lambda text, count=1: f"{text}:{count}",
        )
    )
    result = execute_tool_full("typed_echo", {"text": "ok", "count": "2"})
    assert result.is_error is False
    assert result.text == "ok:2"
