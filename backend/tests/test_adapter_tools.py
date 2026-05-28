"""Tests for adapter function calling (tools) support."""
from __future__ import annotations

import json

import pytest

from app.llm.schemas import (
    AdapterConfig,
    ChatMessage,
    ChatRequest,
    ToolCall,
    ToolDefinition,
    ToolParameterProperty,
    ToolParameters,
)
from app.llm.adapters.openai_compatible import OpenAICompatibleAdapter
from app.llm.adapters.anthropic import AnthropicAdapter
from app.llm.adapters.gemini import GeminiAdapter
from app.llm.validator import validate_chat_request


def _make_config(provider: str = "openai") -> AdapterConfig:
    return AdapterConfig(
        provider=provider,
        model="test-model",
        api_key="test-key",
        base_url="https://api.example.com",
    )


def _make_tool() -> ToolDefinition:
    return ToolDefinition(
        name="web_search",
        description="Search the web",
        parameters=ToolParameters(
            properties={
                "query": ToolParameterProperty(type="string", description="Search query"),
            },
            required=["query"],
        ),
    )


def _make_request(tools: list[ToolDefinition] | None = None, extra_messages: list[ChatMessage] | None = None) -> ChatRequest:
    messages = [ChatMessage(role="user", content="hello")]
    if extra_messages:
        messages.extend(extra_messages)
    return ChatRequest(
        config=_make_config(),
        messages=messages,
        agent_id="test",
        agent_name="Test",
        user_text="hello",
        tools=tools or [],
    )


# --- OpenAI Compatible Adapter ---


class TestOpenAICompatibleTools:
    def test_build_payload_without_tools(self):
        adapter = OpenAICompatibleAdapter(_make_config())
        request = _make_request()
        payload = adapter._build_payload(request)
        assert "tools" not in payload

    def test_build_payload_with_tools(self):
        adapter = OpenAICompatibleAdapter(_make_config())
        request = _make_request(tools=[_make_tool()])
        payload = adapter._build_payload(request)
        assert "tools" in payload
        assert len(payload["tools"]) == 1
        tool = payload["tools"][0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "web_search"
        assert tool["function"]["parameters"]["required"] == ["query"]

    def test_extract_tool_calls_empty(self):
        adapter = OpenAICompatibleAdapter(_make_config())
        data = {
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!"},
            }],
        }
        assert adapter._extract_tool_calls(data) == []

    def test_extract_tool_calls_present(self):
        adapter = OpenAICompatibleAdapter(_make_config())
        data = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query": "test"}',
                        },
                    }],
                },
            }],
        }
        tool_calls = adapter._extract_tool_calls(data)
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "call_123"
        assert tool_calls[0].name == "web_search"
        assert tool_calls[0].arguments == {"query": "test"}

    def test_extract_tool_calls_invalid_json_args(self):
        adapter = OpenAICompatibleAdapter(_make_config())
        data = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": "not-valid-json",
                        },
                    }],
                },
            }],
        }
        tool_calls = adapter._extract_tool_calls(data)
        assert len(tool_calls) == 1
        assert tool_calls[0].arguments == {"raw": "not-valid-json"}

    def test_serialize_messages_with_tools(self):
        adapter = OpenAICompatibleAdapter(_make_config())
        tc = ToolCall(id="tc_1", name="web_search", arguments={"query": "test"})
        request = _make_request(extra_messages=[
            ChatMessage(role="assistant", content="", tool_calls=[tc], reasoning_content="先检索再回答"),
            ChatMessage(role="tool", content="result text", tool_call_id="tc_1"),
        ])
        base_messages = [{"role": "user", "content": "hello"}]
        result = adapter._serialize_messages_with_tools(request, base_messages)
        assert len(result) == 3
        assert result[1]["role"] == "assistant"
        assert result[1]["tool_calls"][0]["id"] == "tc_1"
        assert result[1]["reasoning_content"] == "先检索再回答"
        assert result[2]["role"] == "tool"
        assert result[2]["tool_call_id"] == "tc_1"

    def test_validate_chat_request_preserves_tool_metadata(self):
        tc = ToolCall(id="tc_1", name="web_search", arguments={"query": "test"})
        request = _make_request(extra_messages=[
            ChatMessage(role="assistant", content="", tool_calls=[tc], reasoning_content="先检索再回答"),
            ChatMessage(role="tool", content="result text", tool_call_id="tc_1"),
        ])
        validated = validate_chat_request(request)
        assert len(validated.messages) == 3
        assert validated.messages[1].tool_calls[0].id == "tc_1"
        assert validated.messages[1].reasoning_content == "先检索再回答"
        assert validated.messages[2].tool_call_id == "tc_1"

    def test_no_tools_behavior_unchanged(self):
        """Without tools, payload should be identical to before."""
        adapter = OpenAICompatibleAdapter(_make_config())
        request = _make_request()
        payload = adapter._build_payload(request)
        assert payload["model"] == "test-model"
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"

    def test_finalize_stream_tool_calls_merges_argument_fragments(self):
        adapter = OpenAICompatibleAdapter(_make_config())
        tool_calls = adapter._finalize_stream_tool_calls(
            {
                0: {
                    "id": "call_123",
                    "name": "web_search",
                    "arguments": '{"query":"hello"}',
                }
            }
        )
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "call_123"
        assert tool_calls[0].name == "web_search"
        assert tool_calls[0].arguments == {"query": "hello"}


# --- Anthropic Adapter ---


class TestAnthropicTools:
    def test_build_payload_without_tools(self):
        adapter = AnthropicAdapter(_make_config("anthropic"))
        request = _make_request()
        payload = adapter._build_payload(request, max_tokens=256)
        assert "tools" not in payload

    def test_build_payload_with_tools(self):
        adapter = AnthropicAdapter(_make_config("anthropic"))
        request = _make_request(tools=[_make_tool()])
        payload = adapter._build_payload(request, max_tokens=256)
        assert "tools" in payload
        assert len(payload["tools"]) == 1
        tool = payload["tools"][0]
        assert tool["name"] == "web_search"
        assert "input_schema" in tool
        assert tool["input_schema"]["required"] == ["query"]

    def test_extract_tool_calls_empty(self):
        adapter = AnthropicAdapter(_make_config("anthropic"))
        data = {
            "content": [{"type": "text", "text": "Hello!"}],
        }
        assert adapter._extract_tool_calls(data) == []

    def test_extract_tool_calls_present(self):
        adapter = AnthropicAdapter(_make_config("anthropic"))
        data = {
            "content": [
                {"type": "text", "text": "Let me search for that."},
                {"type": "tool_use", "id": "tu_123", "name": "web_search", "input": {"query": "test"}},
            ],
        }
        tool_calls = adapter._extract_tool_calls(data)
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "tu_123"
        assert tool_calls[0].name == "web_search"
        assert tool_calls[0].arguments == {"query": "test"}

    def test_serialize_messages_with_tools(self):
        adapter = AnthropicAdapter(_make_config("anthropic"))
        tc = ToolCall(id="tu_1", name="web_search", arguments={"query": "test"})
        request = _make_request(extra_messages=[
            ChatMessage(role="assistant", content="thinking", tool_calls=[tc]),
            ChatMessage(role="tool", content="search result", tool_call_id="tu_1"),
        ])
        base_messages = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
        result = adapter._serialize_messages_with_tools(request, base_messages)
        assert len(result) == 3
        # assistant with tool_use
        assert result[1]["role"] == "assistant"
        content_blocks = result[1]["content"]
        assert any(b["type"] == "tool_use" for b in content_blocks)
        # tool result as user message
        assert result[2]["role"] == "user"
        tool_result_blocks = result[2]["content"]
        assert any(b["type"] == "tool_result" for b in tool_result_blocks)

    def test_finalize_stream_tool_calls_merges_input_json_fragments(self):
        adapter = AnthropicAdapter(_make_config("anthropic"))
        tool_calls = adapter._finalize_stream_tool_calls(
            {
                0: {
                    "id": "tu_123",
                    "name": "web_search",
                    "input": '{"query":"hello"}',
                }
            }
        )
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "tu_123"
        assert tool_calls[0].name == "web_search"
        assert tool_calls[0].arguments == {"query": "hello"}


# --- Gemini Adapter ---


class TestGeminiTools:
    def test_build_payload_without_tools(self):
        adapter = GeminiAdapter(_make_config("gemini"))
        request = _make_request()
        payload = adapter._build_payload(request)
        assert "tools" not in payload

    def test_build_payload_with_tools(self):
        adapter = GeminiAdapter(_make_config("gemini"))
        request = _make_request(tools=[_make_tool()])
        payload = adapter._build_payload(request)
        assert "tools" in payload
        assert len(payload["tools"]) == 1
        func_decls = payload["tools"][0]["function_declarations"]
        assert len(func_decls) == 1
        assert func_decls[0]["name"] == "web_search"
        assert func_decls[0]["parameters"]["type"] == "OBJECT"

    def test_extract_tool_calls_empty(self):
        adapter = GeminiAdapter(_make_config("gemini"))
        data = {
            "candidates": [{
                "content": {"parts": [{"text": "Hello!"}]},
            }],
        }
        assert adapter._extract_tool_calls(data) == []

    def test_extract_tool_calls_present(self):
        adapter = GeminiAdapter(_make_config("gemini"))
        data = {
            "candidates": [{
                "content": {"parts": [
                    {"functionCall": {"name": "web_search", "args": {"query": "test"}}},
                ]},
            }],
        }
        tool_calls = adapter._extract_tool_calls(data)
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "web_search"
        assert tool_calls[0].arguments == {"query": "test"}
        assert tool_calls[0].id.startswith("gemini-")

    def test_serialize_messages_with_tools(self):
        adapter = GeminiAdapter(_make_config("gemini"))
        tc = ToolCall(id="fc_1", name="web_search", arguments={"query": "test"})
        request = _make_request(extra_messages=[
            ChatMessage(role="assistant", content="", tool_calls=[tc]),
            ChatMessage(role="tool", content="search result", tool_call_id="fc_1"),
        ])
        base_contents = [{"role": "user", "parts": [{"text": "hello"}]}]
        result = adapter._serialize_messages_with_tools(request, base_contents)
        assert len(result) == 3
        # assistant with functionCall
        assert result[1]["role"] == "model"
        assert any("functionCall" in p for p in result[1]["parts"])
        # tool result as function role
        assert result[2]["role"] == "function"
        assert any("functionResponse" in p for p in result[2]["parts"])

    def test_chat_with_images_delegates_to_chat(self, monkeypatch: pytest.MonkeyPatch):
        adapter = OpenAICompatibleAdapter(
            AdapterConfig(
                provider="openai",
                model="test-model",
                api_key="test-key",
                base_url="https://api.example.com",
                capabilities=type(_make_config().capabilities)(supports_image_input=True),
            )
        )
        request = ChatRequest(
            config=adapter.config,
            messages=[ChatMessage(role="user", content="hello")],
            agent_id="test",
            agent_name="Test",
            user_text="hello",
        )
        captured: dict[str, object] = {}

        def fake_chat(validated_request: ChatRequest):
            captured["request"] = validated_request
            return type("Resp", (), {"content": "ok"})()

        monkeypatch.setattr(adapter, "chat", fake_chat)
        response = adapter.chat_with_images(request)
        assert captured["request"].user_text == "hello"
        assert response.content == "ok"
