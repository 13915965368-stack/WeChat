from __future__ import annotations

from app.llm.adapters.base import BaseLLMAdapter
from app.llm.schemas import ChatMessage, ChatRequest, ChatResponse, ValidationRequest, ValidationResult
from app.llm.validator import validate_chat_request, validate_validation_request


class AnthropicAdapter(BaseLLMAdapter):
    adapter_name = "anthropic"

    def _build_headers(self) -> dict[str, str]:
        headers = self._build_default_headers()
        headers["x-api-key"] = self._require_api_key()
        headers["anthropic-version"] = "2023-06-01"
        return headers

    def _build_payload(self, request: ChatRequest, *, max_tokens: int) -> dict[str, object]:
        system_prompt, messages = self._split_system_and_messages(request)
        payload: dict[str, object] = {
            "model": request.config.model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": message["role"],
                    "content": [{"type": "text", "text": message["content"]}],
                }
                for message in messages
            ],
        }
        if system_prompt:
            payload["system"] = system_prompt
        return payload

    def _extract_response_text(self, data: dict[str, object]) -> str:
        content = data.get("content")
        if not isinstance(content, list) or not content:
            raise ValueError("anthropic response missing content blocks")

        text = self._extract_text_content(content)
        if not text:
            raise ValueError("anthropic response missing assistant content")
        return text

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
        data = self._post_json(
            self._resolve_url("/messages"),
            self._build_payload(validated, max_tokens=256),
            self._build_headers(),
        )
        return ChatResponse(
            content=self._extract_response_text(data),
            provider=validated.config.provider,
            model=validated.config.model,
            raw={"adapter": self.adapter_name, "mode": "remote"},
        )
