"""Tests for the tool calling loop."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.llm.schemas import (
    AdapterConfig,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    SearchRuntimeConfigSnapshot,
    ToolCall,
    ToolDefinition,
    ToolParameterProperty,
    ToolParameters,
    ToolRuntimeContext,
)
from app.llm.tool_loop import MAX_TOOL_ROUNDS, run_tool_loop
from app.llm.tools.registry import clear_tools, execute_tool, register_tool


def _make_config() -> AdapterConfig:
    return AdapterConfig(provider="mock", model="test", api_key="test")


def _make_tool() -> ToolDefinition:
    return ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters=ToolParameters(
            properties={"query": ToolParameterProperty(type="string", description="test")},
            required=["query"],
        ),
    )


def _make_request(tools: list[ToolDefinition] | None = None) -> ChatRequest:
    return ChatRequest(
        config=_make_config(),
        messages=[ChatMessage(role="user", content="hello")],
        agent_id="test",
        agent_name="Test",
        user_text="hello",
        tools=tools or [],
    )


@dataclass
class FakeClient:
    """A fake LLM client that simulates tool calling behavior."""
    responses: list[ChatResponse]
    call_count: int = 0

    def chat(self, request: ChatRequest) -> ChatResponse:
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return ChatResponse(content="default response", provider="mock", model="test")


@pytest.fixture(autouse=True)
def _clean_tools():
    clear_tools()
    register_tool(
        name="test_tool",
        description="A test tool",
        parameters={"query": {"type": "string", "description": "test"}},
        required=["query"],
        executor=lambda query: f"result for {query}",
    )
    yield
    clear_tools()


class TestToolLoopNoTools:
    def test_no_tools_passes_through(self):
        """Without tools, run_tool_loop directly calls client.chat."""
        client = FakeClient([ChatResponse(content="hello back", provider="mock", model="test")])
        request = _make_request(tools=[])
        result = run_tool_loop(client, request)
        assert result.content == "hello back"
        assert client.call_count == 1


class TestToolLoopSingleRound:
    def test_single_tool_call_then_final_response(self):
        """Model calls one tool, gets result, then gives final response."""
        tool_call = ToolCall(id="tc_1", name="test_tool", arguments={"query": "hello"})
        client = FakeClient([
            ChatResponse(content="", provider="mock", model="test", tool_calls=[tool_call]),
            ChatResponse(content="Final answer based on tool result", provider="mock", model="test"),
        ])
        request = _make_request(tools=[_make_tool()])
        result = run_tool_loop(client, request)
        assert result.content == "Final answer based on tool result"
        assert client.call_count == 2
        # Verify tool result was appended to messages
        second_call_messages = request.messages  # original unchanged (deepcopy)
        assert len(second_call_messages) == 1  # original request not mutated

    def test_tool_replay_preserves_reasoning_content(self):
        tool_call = ToolCall(id="tc_1", name="test_tool", arguments={"query": "hello"})
        captured_requests = []

        class InspectClient:
            def __init__(self):
                self.call_count = 0

            def chat(self, request: ChatRequest) -> ChatResponse:
                captured_requests.append(request)
                self.call_count += 1
                if self.call_count == 1:
                    return ChatResponse(
                        content="",
                        provider="mock",
                        model="test",
                        tool_calls=[tool_call],
                        raw={"reasoning_content": "先调用工具再回答"},
                    )
                return ChatResponse(content="done", provider="mock", model="test")

        client = InspectClient()
        result = run_tool_loop(client, _make_request(tools=[_make_tool()]))
        assert result.content == "done"
        assert len(captured_requests) == 2
        assert captured_requests[1].messages[1].reasoning_content == "先调用工具再回答"


class TestToolLoopCallbacks:
    def test_on_tool_call_callback(self):
        """on_tool_call callback is invoked for each tool call."""
        tool_call = ToolCall(id="tc_1", name="test_tool", arguments={"query": "test"})
        client = FakeClient([
            ChatResponse(content="", provider="mock", model="test", tool_calls=[tool_call]),
            ChatResponse(content="done", provider="mock", model="test"),
        ])
        called = []
        run_tool_loop(
            client,
            _make_request(tools=[_make_tool()]),
            on_tool_call=lambda tc: called.append(("call", tc.name)),
        )
        assert called == [("call", "test_tool")]

    def test_on_tool_result_callback(self):
        """on_tool_result callback is invoked with tool call and result."""
        tool_call = ToolCall(id="tc_1", name="test_tool", arguments={"query": "test"})
        client = FakeClient([
            ChatResponse(content="", provider="mock", model="test", tool_calls=[tool_call]),
            ChatResponse(content="done", provider="mock", model="test"),
        ])
        results = []
        run_tool_loop(
            client,
            _make_request(tools=[_make_tool()]),
            on_tool_result=lambda tc, r: results.append(("result", tc.name, r)),
        )
        assert len(results) == 1
        assert results[0][0] == "result"
        assert results[0][1] == "test_tool"
        assert "test" in results[0][2]

    def test_tool_context_is_forwarded_to_executor(self):
        clear_tools()
        captured = {}

        def context_tool(query: str, *, context: ToolRuntimeContext | None = None) -> str:
            captured["conversation_id"] = context.conversation_id if context else ""
            return f"ctx for {query}"

        register_tool(
            name="test_tool",
            description="A test tool",
            parameters={"query": {"type": "string", "description": "test"}},
            required=["query"],
            executor=context_tool,
        )
        tool_call = ToolCall(id="tc_1", name="test_tool", arguments={"query": "test"})
        client = FakeClient([
            ChatResponse(content="", provider="mock", model="test", tool_calls=[tool_call]),
            ChatResponse(content="done", provider="mock", model="test"),
        ])
        run_tool_loop(
            client,
            _make_request(tools=[_make_tool()]),
            tool_context=ToolRuntimeContext(
                conversation_id="conv-1",
                agent_id="agent-1",
                agent_name="Test",
                is_group=False,
                search_config=SearchRuntimeConfigSnapshot(),
            ),
        )
        assert captured["conversation_id"] == "conv-1"


class TestToolLoopMaxRounds:
    def test_max_rounds_forces_final_response(self):
        """After MAX_TOOL_ROUNDS, tools are cleared to force a text response."""
        tool_call = ToolCall(id="tc_loop", name="test_tool", arguments={"query": "loop"})
        call_count = 0

        class LoopClient:
            def chat(self, request):
                nonlocal call_count
                call_count += 1
                if not request.tools:
                    return ChatResponse(content="forced final", provider="mock", model="test")
                return ChatResponse(content="", provider="mock", model="test", tool_calls=[tool_call])

        client = LoopClient()
        result = run_tool_loop(client, _make_request(tools=[_make_tool()]))
        assert result.content == "forced final"
        assert call_count == MAX_TOOL_ROUNDS + 1


class TestToolLoopErrorHandling:
    def test_unknown_tool_returns_error_string(self):
        """Unknown tool name returns an error string, doesn't crash."""
        clear_tools()  # Remove all tools
        tool_call = ToolCall(id="tc_1", name="nonexistent", arguments={"query": "test"})
        client = FakeClient([
            ChatResponse(content="", provider="mock", model="test", tool_calls=[tool_call]),
            ChatResponse(content="got error", provider="mock", model="test"),
        ])
        # Register a tool definition but not the executor to test the error path
        from app.llm.tools.registry import _TOOL_EXECUTORS
        request = _make_request(tools=[_make_tool()])
        result = run_tool_loop(client, request)
        assert result.content == "got error"
