from __future__ import annotations

import json

from app.llm.adapters.base import BaseLLMAdapter
from app.llm.protocols.common import (
    build_response_format_provider_overrides,
    build_thinking_provider_overrides,
)
from app.llm.schemas import ChatRequest, ChatResponse, ToolCall, ValidationRequest, ValidationResult
from app.llm.usage import normalize_usage
from app.llm.validator import (
    LLMStreamInterruptedError,
    LLMStreamProtocolError,
    validate_chat_request,
    validate_validation_request,
)


class OpenAICompatibleAdapter(BaseLLMAdapter):
    adapter_name = "openai-compatible"

    def _build_headers(self) -> dict[str, str]:
        headers = self._build_default_headers()
        headers["Authorization"] = f"Bearer {self._require_api_key()}"
        return headers

    def _build_payload(
        self,
        request: ChatRequest,
        *,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> dict[str, object]:
        system_prompt, messages = self._split_system_and_messages(request)
        serialized_messages = []
        if system_prompt:
            serialized_messages.append({"role": "system", "content": system_prompt})
        serialized_messages.extend(messages)

        serialized_messages = self._serialize_messages_with_tools(request, serialized_messages)

        payload: dict[str, object] = {
            "model": request.config.model,
            "messages": serialized_messages,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if stream:
            payload["stream"] = True
            if request.config.provider.strip().lower() in {"qwen", "dashscope", "minimax", "moonshot", "kimi"}:
                payload["stream_options"] = {"include_usage": True}
        payload.update(build_thinking_provider_overrides(request))
        payload.update(build_response_format_provider_overrides(request))

        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": tool.parameters.type,
                            "properties": {
                                k: {"type": v.type, "description": v.description}
                                for k, v in tool.parameters.properties.items()
                            },
                            "required": tool.parameters.required,
                        },
                    },
                }
                for tool in request.tools
            ]

        return payload

    def _serialize_messages_with_tools(self, request: ChatRequest, base_messages: list[dict]) -> list[dict]:
        result = list(base_messages)
        for msg in request.messages:
            if msg.role == "assistant" and msg.tool_calls:
                assistant_message = {
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
                if msg.reasoning_content.strip():
                    assistant_message["reasoning_content"] = msg.reasoning_content.strip()
                result.append(assistant_message)
            elif msg.role == "tool":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })
        return result

    def _extract_tool_calls(self, data: dict[str, object]) -> list[ToolCall]:
        first_choice = self._extract_first_choice(data)
        message = self._extract_message_payload(first_choice)
        raw_tool_calls = message.get("tool_calls")
        if not isinstance(raw_tool_calls, list) or not raw_tool_calls:
            return []
        result = []
        for tc in raw_tool_calls:
            if not isinstance(tc, dict):
                continue
            func = tc.get("function", {})
            if not isinstance(func, dict):
                continue
            raw_args = func.get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except (json.JSONDecodeError, ValueError):
                    parsed_args = {"raw": raw_args}
            elif isinstance(raw_args, dict):
                parsed_args = raw_args
            else:
                parsed_args = {}
            result.append(ToolCall(
                id=str(tc.get("id", "")),
                name=str(func.get("name", "")),
                arguments=parsed_args,
            ))
        return result

    def _extract_response_text(self, data: dict[str, object]) -> str:
        first_choice = self._extract_first_choice(data)
        message = self._extract_message_payload(first_choice)
        content = self._extract_text_content(message.get("content", ""))
        if not content:
            raise ValueError("openai-compatible response missing assistant content")
        return content

    def _extract_reasoning_content(self, payload: dict[str, object]) -> str:
        for key in ("reasoning_content", "reasoning", "reasoning_details"):
            reasoning = self._extract_text_content(payload.get(key, ""))
            if reasoning:
                return reasoning
        return ""

    def _build_chat_response(self, validated: ChatRequest, data: dict[str, object]) -> ChatResponse:
        tool_calls = self._extract_tool_calls(data)
        raw: dict[str, object] = {"adapter": self.adapter_name, "mode": "remote"}
        reasoning_content = self._extract_reasoning_content(
            self._extract_message_payload(self._extract_first_choice(data))
        )
        if reasoning_content:
            raw["reasoning_content"] = reasoning_content
        usage = normalize_usage(data.get("usage"))
        if usage is not None:
            raw["usage"] = data.get("usage")
        if tool_calls:
            content = self._extract_text_content(
                self._extract_message_payload(self._extract_first_choice(data)).get("content", "")
            )
            return ChatResponse(
                content=content,
                provider=validated.config.provider,
                model=validated.config.model,
                tool_calls=tool_calls,
                finish_reason=str(self._extract_first_choice(data).get("finish_reason", "stop") or "stop"),
                raw=raw,
                usage=usage,
            )

        return ChatResponse(
            content=self._extract_response_text(data),
            provider=validated.config.provider,
            model=validated.config.model,
            finish_reason=str(self._extract_first_choice(data).get("finish_reason", "stop") or "stop"),
            raw=raw,
            usage=usage,
        )

    def _finalize_stream_tool_calls(self, tool_buffers: dict[int, dict[str, str]]) -> list[ToolCall]:
        result: list[ToolCall] = []
        for index in sorted(tool_buffers):
            buffer = tool_buffers[index]
            raw_arguments = buffer.get("arguments", "")
            if raw_arguments:
                try:
                    parsed_arguments = json.loads(raw_arguments)
                except (json.JSONDecodeError, ValueError):
                    parsed_arguments = {"raw": raw_arguments}
            else:
                parsed_arguments = {}
            result.append(
                ToolCall(
                    id=buffer.get("id", ""),
                    name=buffer.get("name", ""),
                    arguments=parsed_arguments,
                )
            )
        return result

    def _extract_stream_usage(self, event: dict[str, object]) -> dict[str, object] | None:
        usage_candidates: list[object] = [event.get("usage")]
        choices = event.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                usage_candidates.append(first_choice.get("usage"))
                delta = first_choice.get("delta")
                if isinstance(delta, dict):
                    usage_candidates.append(delta.get("usage"))
        for usage in usage_candidates:
            if isinstance(usage, dict) and usage:
                return usage
        return None

    def _chat_stream(self, validated: ChatRequest) -> ChatResponse:
        payload = self._build_payload(validated, stream=True)
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_buffers: dict[int, dict[str, str]] = {}
        finish_reason = "stop"
        had_effective_increment = False
        usage_payload: dict[str, object] | None = None

        try:
            for event in self._stream_sse_events(
                self._resolve_url("/chat/completions"),
                payload,
                self._build_headers(),
            ):
                usage = self._extract_stream_usage(event)
                if usage is not None:
                    usage_payload = usage
                choices = event.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                first_choice = choices[0]
                if not isinstance(first_choice, dict):
                    continue
                delta = first_choice.get("delta", {})
                if not isinstance(delta, dict):
                    delta = {}
                content = self._extract_text_content(delta.get("content", ""), strip=False)
                if content != "":
                    text_parts.append(content)
                    had_effective_increment = True
                reasoning = self._extract_reasoning_content(delta)
                if reasoning:
                    reasoning_parts.append(reasoning)
                    had_effective_increment = True

                raw_tool_calls = delta.get("tool_calls")
                if isinstance(raw_tool_calls, list):
                    for offset, raw_tool_call in enumerate(raw_tool_calls):
                        if not isinstance(raw_tool_call, dict):
                            continue
                        index = raw_tool_call.get("index", offset)
                        if not isinstance(index, int):
                            continue
                        buffer = tool_buffers.setdefault(index, {"id": "", "name": "", "arguments": ""})
                        call_id = raw_tool_call.get("id")
                        if isinstance(call_id, str) and call_id:
                            buffer["id"] = call_id
                        function_payload = raw_tool_call.get("function", {})
                        if not isinstance(function_payload, dict):
                            function_payload = {}
                        function_name = function_payload.get("name")
                        if isinstance(function_name, str) and function_name:
                            buffer["name"] = function_name
                            had_effective_increment = True
                        function_arguments = function_payload.get("arguments")
                        if isinstance(function_arguments, str) and function_arguments:
                            buffer["arguments"] += function_arguments
                            had_effective_increment = True

                current_finish_reason = first_choice.get("finish_reason")
                if isinstance(current_finish_reason, str) and current_finish_reason:
                    finish_reason = current_finish_reason
        except (LLMStreamProtocolError, ValueError) as exc:
            if had_effective_increment:
                raise LLMStreamInterruptedError(f"{self.adapter_name} stream interrupted: {exc}") from exc
            raise

        tool_calls = self._finalize_stream_tool_calls(tool_buffers)
        content = "".join(text_parts).strip()
        if not content and not tool_calls:
            raise ValueError("openai-compatible response missing assistant content")

        raw: dict[str, object] = {"adapter": self.adapter_name, "mode": "remote"}
        if reasoning_parts:
            raw["reasoning_content"] = "".join(reasoning_parts).strip()
        usage = normalize_usage(usage_payload)
        if usage_payload is not None:
            raw["usage"] = usage_payload

        return ChatResponse(
            content=content,
            provider=validated.config.provider,
            model=validated.config.model,
            finish_reason=finish_reason,
            raw=raw,
            tool_calls=tool_calls,
            usage=usage,
        )

    def _extract_first_choice(self, data: dict[str, object]) -> dict[str, object]:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("openai-compatible response missing choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("openai-compatible response has invalid choice shape")
        return first_choice

    def _extract_message_payload(self, first_choice: dict[str, object]) -> dict[str, object]:
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("openai-compatible response missing message payload")
        return message

    def _is_validation_response_usable(self, data: dict[str, object]) -> bool:
        first_choice = self._extract_first_choice(data)
        message = self._extract_message_payload(first_choice)

        if self._extract_text_content(message.get("content", "")):
            return True
        if self._extract_reasoning_content(message):
            return True
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and len(tool_calls) > 0:
            return True
        refusal = self._extract_text_content(message.get("refusal", ""))
        if refusal:
            return True
        return False

    def validate(self, request: ValidationRequest | None = None) -> ValidationResult:
        if self.config.provider == "mock":
            return super().validate(request)

        target_request = request or ValidationRequest(config=self.config)
        validated = validate_validation_request(target_request)
        payload = {
            "model": validated.config.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
        }
        data = self._post_json(
            self._resolve_url("/chat/completions"),
            payload,
            self._build_headers(),
        )
        if not self._is_validation_response_usable(data):
            raise ValueError("openai-compatible validation response missing usable assistant output")
        return ValidationResult(
            ok=True,
            provider=validated.config.provider,
            model=validated.config.model,
            status_message="Model config validated successfully",
            capabilities=validated.config.capabilities,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        if self.config.provider == "mock":
            return super().chat(request)

        validated = validate_chat_request(request)
        try:
            return self._chat_stream(validated)
        except LLMStreamInterruptedError:
            raise
        except LLMStreamProtocolError:
            data = self._post_json(
                self._resolve_url("/chat/completions"),
                self._build_payload(validated),
                self._build_headers(),
            )
            return self._build_chat_response(validated, data)
