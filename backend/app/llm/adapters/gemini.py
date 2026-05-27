from __future__ import annotations

from app.llm.adapters.base import BaseLLMAdapter
from app.llm.schemas import ChatMessage, ChatRequest, ChatResponse, ValidationRequest, ValidationResult
from app.llm.validator import validate_chat_request, validate_validation_request


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
        payload: dict[str, object] = {"contents": contents}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        return payload

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

    def _resolve_generate_url(self) -> str:
        api_key = self._require_api_key()
        base_url = self._resolve_url(f"/models/{self.config.model}:generateContent")
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}key={api_key}"

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
        data = self._post_json(
            self._resolve_generate_url(),
            self._build_payload(validated),
            self._build_headers(),
        )
        return ChatResponse(
            content=self._extract_response_text(data),
            provider=validated.config.provider,
            model=validated.config.model,
            raw={"adapter": self.adapter_name, "mode": "remote"},
        )
