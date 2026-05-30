from __future__ import annotations

import json

from app.llm.adapters.base import BaseLLMAdapter
from app.llm.protocols.common import build_thinking_provider_overrides
from app.llm.schemas import ChatMessage, ChatRequest, ChatResponse, ToolCall, ValidationRequest, ValidationResult
from app.llm.usage import normalize_usage
from app.llm.validator import (
    LLMStreamInterruptedError,
    LLMStreamProtocolError,
    validate_chat_request,
    validate_validation_request,
)


class AnthropicAdapter(BaseLLMAdapter):
    adapter_name = "anthropic"

    def _serialize_tool_property(self, prop) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": prop.type,
            "description": prop.description,
        }
        if prop.enum is not None:
            payload["enum"] = prop.enum
        if prop.items is not None:
            payload["items"] = prop.items
        if prop.default is not None:
            payload["default"] = prop.default
        return payload

    def _build_headers(self) -> dict[str, str]:
        headers = self._build_default_headers()
        headers["x-api-key"] = self._require_api_key()
        headers["anthropic-version"] = "2023-06-01"
        return headers

    def _build_payload(self, request: ChatRequest, *, max_tokens: int, stream: bool = False) -> dict[str, object]:
        system_text, messages = self._split_system_and_messages(request)
        serialized_messages = [
            {
                "role": message["role"],
                "content": [{"type": "text", "text": message["content"]}],
            }
            for message in messages
        ]

        serialized_messages = self._serialize_messages_with_tools(request, serialized_messages)

        payload: dict[str, object] = {
            "model": request.config.model,
            "max_tokens": max_tokens,
            "messages": serialized_messages,
        }
        if system_text:
            payload["system"] = system_text
        if stream:
            payload["stream"] = True
        payload.update(build_thinking_provider_overrides(request))

        if request.tools:
            payload["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": {
                        "type": tool.parameters.type,
                        "properties": {
                            k: self._serialize_tool_property(v)
                            for k, v in tool.parameters.properties.items()
                        },
                        "required": tool.parameters.required,
                    },
                }
                for tool in request.tools
            ]

        return payload

    def _serialize_messages_with_tools(self, request: ChatRequest, base_messages: list[dict]) -> list[dict]:
        result = list(base_messages)
        for msg in request.messages:
            if msg.role == "assistant" and msg.tool_calls:
                content_blocks = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                result.append({"role": "assistant", "content": content_blocks})
            elif msg.role == "tool":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }],
                })
        return result

    def _extract_tool_calls(self, data: dict[str, object]) -> list[ToolCall]:
        content = data.get("content")
        if not isinstance(content, list):
            return []
        result = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            result.append(ToolCall(
                id=str(block.get("id", "")),
                name=str(block.get("name", "")),
                arguments=block.get("input", {}),
            ))
        return result

    def _extract_response_text(self, data: dict[str, object]) -> str:
        content = data.get("content")
        if not isinstance(content, list) or not content:
            raise ValueError("anthropic response missing content blocks")

        text = self._extract_text_content(content)
        if not text:
            raise ValueError("anthropic response missing assistant content")
        return text

    def _build_chat_response(self, validated: ChatRequest, data: dict[str, object]) -> ChatResponse:
        tool_calls = self._extract_tool_calls(data)
        usage = normalize_usage(data.get("usage"))
        raw: dict[str, object] = {"adapter": self.adapter_name, "mode": "remote"}
        if usage is not None:
            raw["usage"] = data.get("usage")
        if tool_calls:
            content = self._extract_text_content(data.get("content", ""))
            return ChatResponse(
                content=content,
                provider=validated.config.provider,
                model=validated.config.model,
                tool_calls=tool_calls,
                raw=raw,
                usage=usage,
            )

        return ChatResponse(
            content=self._extract_response_text(data),
            provider=validated.config.provider,
            model=validated.config.model,
            raw=raw,
            usage=usage,
        )

    def _finalize_stream_tool_calls(self, tool_buffers: dict[int, dict[str, str]]) -> list[ToolCall]:
        result: list[ToolCall] = []
        for index in sorted(tool_buffers):
            buffer = tool_buffers[index]
            raw_input = buffer.get("input", "")
            if raw_input:
                try:
                    parsed_input = json.loads(raw_input)
                except (json.JSONDecodeError, ValueError):
                    parsed_input = {"raw": raw_input}
            else:
                parsed_input = {}
            result.append(
                ToolCall(
                    id=buffer.get("id", ""),
                    name=buffer.get("name", ""),
                    arguments=parsed_input,
                )
            )
        return result

    def _chat_stream(self, validated: ChatRequest) -> ChatResponse:
        payload = self._build_payload(validated, max_tokens=256, stream=True)
        text_parts: list[str] = []
        tool_buffers: dict[int, dict[str, str]] = {}
        finish_reason = "stop"
        raw: dict[str, object] = {"adapter": self.adapter_name, "mode": "remote"}
        had_effective_increment = False
        message_stopped = False

        try:
            for event in self._stream_sse_events(
                self._resolve_url("/messages"),
                payload,
                self._build_headers(),
            ):
                event_type = event.get("type")
                if not isinstance(event_type, str):
                    continue
                if message_stopped and event_type.startswith(("content_block_", "message_")):
                    raise ValueError("anthropic stream emitted content after message_stop")
                if event_type == "message_start":
                    message = event.get("message", {})
                    if isinstance(message, dict):
                        message_id = message.get("id")
                        if isinstance(message_id, str) and message_id:
                            raw["message_id"] = message_id
                    continue
                if event_type == "content_block_start":
                    index = event.get("index")
                    if not isinstance(index, int):
                        continue
                    content_block = event.get("content_block", {})
                    if not isinstance(content_block, dict):
                        continue
                    block_type = content_block.get("type")
                    if block_type == "tool_use":
                        buffer = tool_buffers.setdefault(index, {"id": "", "name": "", "input": ""})
                        tool_id = content_block.get("id")
                        if isinstance(tool_id, str) and tool_id:
                            buffer["id"] = tool_id
                        tool_name = content_block.get("name")
                        if isinstance(tool_name, str) and tool_name:
                            buffer["name"] = tool_name
                            had_effective_increment = True
                        initial_input = content_block.get("input")
                        if isinstance(initial_input, dict) and initial_input:
                            buffer["input"] += json.dumps(initial_input, ensure_ascii=False)
                            had_effective_increment = True
                    continue
                if event_type == "content_block_delta":
                    index = event.get("index")
                    delta = event.get("delta", {})
                    if not isinstance(index, int) or not isinstance(delta, dict):
                        continue
                    delta_type = delta.get("type")
                    if delta_type == "text_delta":
                        text = str(delta.get("text", ""))
                        if text != "":
                            text_parts.append(text)
                            had_effective_increment = True
                    elif delta_type == "input_json_delta":
                        partial_json = str(delta.get("partial_json", ""))
                        if partial_json:
                            buffer = tool_buffers.setdefault(index, {"id": "", "name": "", "input": ""})
                            buffer["input"] += partial_json
                            had_effective_increment = True
                    continue
                if event_type == "message_delta":
                    delta = event.get("delta", {})
                    if isinstance(delta, dict):
                        stop_reason = delta.get("stop_reason")
                        if isinstance(stop_reason, str) and stop_reason:
                            finish_reason = stop_reason
                    usage = event.get("usage")
                    if not isinstance(usage, dict):
                        usage = delta.get("usage") if isinstance(delta, dict) else None
                    if isinstance(usage, dict) and usage:
                        raw["usage"] = usage
                    continue
                if event_type == "message_stop":
                    message_stopped = True
        except (LLMStreamProtocolError, ValueError) as exc:
            if had_effective_increment:
                raise LLMStreamInterruptedError(f"{self.adapter_name} stream interrupted: {exc}") from exc
            raise

        tool_calls = self._finalize_stream_tool_calls(tool_buffers)
        content = "".join(text_parts).strip()
        if not content and not tool_calls:
            raise ValueError("anthropic response missing assistant content")

        return ChatResponse(
            content=content,
            provider=validated.config.provider,
            model=validated.config.model,
            finish_reason=finish_reason,
            raw=raw,
            tool_calls=tool_calls,
            usage=normalize_usage(raw.get("usage")),
        )

    def validate(self, request: ValidationRequest | None = None) -> ValidationResult:
        target_request = request or ValidationRequest(config=self.config)
        validated = validate_validation_request(target_request)
        ping_request = ChatRequest(
            config=validated.config,
            messages=[ChatMessage(role="user", content="ping")],
            agent_id="validator",
            agent_name="Validator",
            user_text="ping",
        )
        data = self._post_json(
            self._resolve_url("/messages"),
            self._build_payload(ping_request, max_tokens=1),
            self._build_headers(),
        )
        self._extract_response_text(data)
        return ValidationResult(
            ok=True,
            provider=validated.config.provider,
            model=validated.config.model,
            status_message="Model config validated successfully",
            capabilities=validated.config.capabilities,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        validated = validate_chat_request(request)
        try:
            return self._chat_stream(validated)
        except LLMStreamInterruptedError:
            raise
        except LLMStreamProtocolError:
            data = self._post_json(
                self._resolve_url("/messages"),
                self._build_payload(validated, max_tokens=256),
                self._build_headers(),
            )
            return self._build_chat_response(validated, data)
