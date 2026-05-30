"""Tests for the tool registry."""
from __future__ import annotations

import time

import pytest

from app.llm.schemas import ToolResult
from app.llm.tools import registry as tool_registry
from app.llm.tools.registry import clear_tools, execute_tool, execute_tool_full, get_global_tool_definitions, register_tool


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_tools()
    yield
    clear_tools()


class TestRegisterTool:
    def test_register_and_discover(self):
        register_tool(
            name="test_tool",
            description="A test tool",
            parameters={"query": {"type": "string", "description": "test query"}},
            required=["query"],
            executor=lambda query: f"result: {query}",
        )
        defs = get_global_tool_definitions()
        assert len(defs) == 1
        assert defs[0].name == "test_tool"
        assert defs[0].description == "A test tool"
        assert "query" in defs[0].parameters.properties

    def test_register_multiple_tools(self):
        register_tool(
            name="tool_a",
            description="Tool A",
            parameters={},
            required=[],
            executor=lambda: "a",
        )
        register_tool(
            name="tool_b",
            description="Tool B",
            parameters={},
            required=[],
            executor=lambda: "b",
        )
        defs = get_global_tool_definitions()
        assert len(defs) == 2
        names = {d.name for d in defs}
        assert names == {"tool_a", "tool_b"}


class TestExecuteTool:
    def test_execute_known_tool(self):
        register_tool(
            name="echo",
            description="Echo tool",
            parameters={"text": {"type": "string", "description": "text to echo"}},
            required=["text"],
            executor=lambda text: f"echo: {text}",
        )
        result = execute_tool("echo", {"text": "hello"})
        assert result == "echo: hello"

    def test_execute_unknown_tool(self):
        result = execute_tool("nonexistent", {})
        assert "Error" in result
        assert "nonexistent" in result

    def test_execute_tool_with_exception(self):
        def failing_executor():
            raise RuntimeError("something went wrong")

        register_tool(
            name="failing",
            description="Fails",
            parameters={},
            required=[],
            executor=failing_executor,
        )
        result = execute_tool("failing", {})
        assert "Error" in result
        assert "something went wrong" in result

    def test_execute_tool_supports_tool_result_return(self):
        register_tool(
            name="struct_tool",
            description="Structured tool",
            parameters={},
            required=[],
            executor=lambda: ToolResult(text="ok", data={"n": 1}, is_error=False),
        )
        result = execute_tool("struct_tool", {})
        assert result == "ok"

    def test_execute_tool_plain_str_still_works(self):
        register_tool(
            name="plain_tool",
            description="Plain tool",
            parameters={},
            required=[],
            executor=lambda: "hi",
        )
        assert execute_tool("plain_tool", {}) == "hi"

    def test_execute_tool_times_out(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(tool_registry, "TOOL_EXECUTION_TIMEOUT_SECONDS", 1, raising=False)

        def slow_tool():
            time.sleep(tool_registry.TOOL_EXECUTION_TIMEOUT_SECONDS + 1)
            return "done"

        register_tool(
            name="slow",
            description="Slow tool",
            parameters={},
            required=[],
            executor=slow_tool,
        )
        result = execute_tool_full("slow", {})
        assert result.is_error is True
        assert "timeout" in result.text.lower()


class TestClearTools:
    def test_clear_resets_registry(self):
        register_tool(
            name="temp",
            description="Temporary",
            parameters={},
            required=[],
            executor=lambda: "temp",
        )
        assert len(get_global_tool_definitions()) == 1
        clear_tools()
        assert len(get_global_tool_definitions()) == 0

    def test_execute_after_clear_returns_error(self):
        register_tool(
            name="temp",
            description="Temporary",
            parameters={},
            required=[],
            executor=lambda: "temp",
        )
        clear_tools()
        result = execute_tool("temp", {})
        assert "Error" in result
