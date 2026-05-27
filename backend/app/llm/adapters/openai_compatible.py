from __future__ import annotations

from app.llm.adapters.base import BaseLLMAdapter
from app.llm.schemas import ChatRequest, ChatResponse, ValidationRequest, ValidationResult
from app.llm.validator import validate_chat_request, validate_validation_request


class OpenAICompatibleAdapter(BaseLLMAdapter):
    adapter_name = "openai-compatible"

    def _build_headers(self) -> dict[str, str]:
        headers = self._build_default_headers()
        headers["Authorization"] = f"Bearer {self._require_api_key()}"
        return headers

    def _build_payload(self, request: ChatRequest, *, max_tokens: int | None = None) -> dict[str, object]:
        system_prompt, messages = self._split_system_and_messages(request)
        serialized_messages = []
        if system_prompt:
            serialized_messages.append({"role": "system", "content": system_prompt})
        serialized_messages.extend(messages)
        payload: dict[str, object] = {
            "model": request.config.model,
            "messages": serialized_messages,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    def _extract_response_text(self, data: dict[str, object]) -> str:
        first_choice = self._extract_first_choice(data)
        message = self._extract_message_payload(first_choice)
        content = self._extract_text_content(message.get("content", ""))
        if not content:
            raise ValueError("openai-compatible response missing assistant content")
        return content

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
        if self._extract_text_content(message.get("reasoning_content", "")):
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
        data = self._post_json(
            self._resolve_url("/chat/completions"),
            self._build_payload(validated),
            self._build_headers(),
        )
        return ChatResponse(
            content=self._extract_response_text(data),
            provider=validated.config.provider,
            model=validated.config.model,
            raw={"adapter": self.adapter_name, "mode": "remote"},
        )
