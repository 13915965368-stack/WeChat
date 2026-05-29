from __future__ import annotations

import json
from uuid import uuid4

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


class GeminiAdapter(BaseLLMAdapter):
    adapter_name = "gemini"

    def _build_headers(self) -> dict[str, str]:
        return self._build_default_headers()

    def _build_payload(self, request: ChatRequest) -> dict[str, object]:
        system_prompt, messages = self._split_system_and_messages(request)
        contents = [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in messages
        ]

        contents = self._serialize_messages_with_tools(request, contents)

        payload: dict[str, object] = {"contents": contents}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        generation_config = build_thinking_provider_overrides(request)
        if generation_config:
            payload["generationConfig"] = generation_config

        if request.tools:
            payload["tools"] = [{
                "function_declarations": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": tool.parameters.type.upper(),
                            "properties": {
                                k: {"type": v.type.upper(), "description": v.description}
                                for k, v in tool.parameters.properties.items()
                            },
                            "required": tool.parameters.required,
                        },
                    }
                    for tool in request.tools
                ]
            }]

        return payload

    def _serialize_messages_with_tools(self, request: ChatRequest, base_contents: list[dict]) -> list[dict]:
        result = list(base_contents)
        for msg in request.messages:
            if msg.role == "assistant" and msg.tool_calls:
                parts = []
                if msg.content:
                    parts.append({"text": msg.content})
                for tc in msg.tool_calls:
                    parts.append({
                        "functionCall": {
                            "name": tc.name,
                            "args": tc.arguments,
                        }
                    })
                result.append({"role": "model", "parts": parts})
            elif msg.role == "tool":
                result.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.tool_call_id,
                            "response": {"result": msg.content},
                        }
                    }],
                })
        return result

    def _extract_tool_calls(self, data: dict[str, object]) -> list[ToolCall]:
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return []
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        result = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            func_call = part.get("functionCall")
            if not isinstance(func_call, dict):
                continue
            result.append(ToolCall(
                id=f"gemini-{uuid4().hex[:8]}",
                name=str(func_call.get("name", "")),
                arguments=func_call.get("args", {}),
            ))
        return result

    def _extract_response_text(self, data: dict[str, object]) -> str:
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("gemini response missing candidates")

        first_candidate = candidates[0]
        if not isinstance(first_candidate, dict):
            raise ValueError("gemini response has invalid candidate shape")

        content = first_candidate.get("content")
        if not isinstance(content, dict):
            raise ValueError("gemini response missing content payload")

        parts = content.get("parts")
        text = self._extract_text_content(parts)
        if not text:
            raise ValueError("gemini response missing assistant content")
        return text

    def _build_chat_response(self, validated: ChatRequest, data: dict[str, object]) -> ChatResponse:
        tool_calls = self._extract_tool_calls(data)
        usage = normalize_usage(data.get("usageMetadata"))
        raw: dict[str, object] = {"adapter": self.adapter_name, "mode": "remote"}
        if data.get("usageMetadata") is not None:
            raw["usage"] = data.get("usageMetadata")
        if tool_calls:
            content = self._extract_text_content(
                data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            )
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

    def _resolve_generate_url(self) -> str:
        api_key = self._require_api_key()
        base_url = self._resolve_url(f"/models/{self.config.model}:generateContent")
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}key={api_key}"

    def _resolve_stream_generate_url(self) -> str:
        api_key = self._require_api_key()
        base_url = self._resolve_url(f"/models/{self.config.model}:streamGenerateContent")
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}alt=sse&key={api_key}"

    def _chat_stream(self, validated: ChatRequest) -> ChatResponse:
        text_parts: list[str] = []
        tool_buffers: list[dict[str, str]] = []
        finish_reason = "stop"
        had_effective_increment = False
        usage_payload: dict[str, object] | None = None

        try:
            for event in self._stream_sse_events(
                self._resolve_stream_generate_url(),
                self._build_payload(validated),
                self._build_headers(),
            ):
                candidates = event.get("candidates")
                if not isinstance(candidates, list) or not candidates:
                    continue
                first_candidate = candidates[0]
                if not isinstance(first_candidate, dict):
                    continue
                content = first_candidate.get("content", {})
                if not isinstance(content, dict):
                    content = {}
                parts = content.get("parts", [])
                if isinstance(parts, list):
                    tool_position = 0
                    for part in parts:
                        if not isinstance(part, dict):
                            continue
                        text = str(part.get("text", ""))
                        if text != "":
                            text_parts.append(text)
                            had_effective_increment = True
                        function_call = part.get("functionCall")
                        if not isinstance(function_call, dict):
                            continue
                        while len(tool_buffers) <= tool_position:
                            tool_buffers.append({"name": "", "args": ""})
                        buffer = tool_buffers[tool_position]
                        tool_position += 1
                        function_name = function_call.get("name")
                        if isinstance(function_name, str) and function_name:
                            buffer["name"] = function_name
                            had_effective_increment = True
                        args = function_call.get("args")
                        if isinstance(args, dict):
                            serialized_args = json.dumps(args, ensure_ascii=False)
                            if serialized_args not in ("{}", ""):
                                buffer["args"] = serialized_args
                                had_effective_increment = True
                        elif isinstance(args, str) and args:
                            buffer["args"] += args
                            had_effective_increment = True
                current_finish_reason = first_candidate.get("finishReason")
                if isinstance(current_finish_reason, str) and current_finish_reason:
                    finish_reason = current_finish_reason.lower()
                usage_metadata = event.get("usageMetadata")
                if isinstance(usage_metadata, dict) and usage_metadata:
                    usage_payload = usage_metadata
        except (LLMStreamProtocolError, ValueError) as exc:
            if had_effective_increment:
                raise LLMStreamInterruptedError(f"{self.adapter_name} stream interrupted: {exc}") from exc
            raise

        tool_calls: list[ToolCall] = []
        for buffer in tool_buffers:
            raw_args = buffer.get("args", "")
            if raw_args:
                try:
                    parsed_args = json.loads(raw_args)
                except (json.JSONDecodeError, ValueError):
                    parsed_args = {"raw": raw_args}
            else:
                parsed_args = {}
            tool_calls.append(
                ToolCall(
                    id=f"gemini-{uuid4().hex[:8]}",
                    name=buffer.get("name", ""),
                    arguments=parsed_args,
                )
            )

        content = "".join(text_parts).strip()
        if not content and not tool_calls:
            raise ValueError("gemini response missing assistant content")

        return ChatResponse(
            content=content,
            provider=validated.config.provider,
            model=validated.config.model,
            finish_reason=finish_reason,
            raw={
                "adapter": self.adapter_name,
                "mode": "remote",
                **({"usage": usage_payload} if usage_payload is not None else {}),
            },
            tool_calls=tool_calls,
            usage=normalize_usage(usage_payload),
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
            self._resolve_generate_url(),
            self._build_payload(ping_request),
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
                self._resolve_generate_url(),
                self._build_payload(validated),
                self._build_headers(),
            )
            return self._build_chat_response(validated, data)
