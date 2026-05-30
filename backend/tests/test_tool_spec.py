from app.llm.tools.registry import clear_tools, get_global_tool_definitions, register_tool_spec
from app.llm.tools.spec import ToolParameterSpec, ToolSpec


def test_register_tool_spec_registers_definition():
    clear_tools()
    spec = ToolSpec(
        name="typed_echo",
        description="typed echo",
        parameters=[
            ToolParameterSpec(
                name="text",
                type="string",
                description="text to echo",
                required=True,
            )
        ],
        executor=lambda text: f"echo: {text}",
    )
    register_tool_spec(spec)
    defs = get_global_tool_definitions()
    assert len(defs) == 1
    assert defs[0].name == "typed_echo"
    assert defs[0].parameters.required == ["text"]
    assert defs[0].parameters.properties["text"].type == "string"
