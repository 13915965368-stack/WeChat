from __future__ import annotations

from dataclasses import replace

from app.llm.provider_aliases import normalize_api_format_alias, normalize_provider_alias
from app.llm.schemas import AdapterConfig, ChatMessage, ChatRequest, ValidationRequest


class LLMValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "validation_error",
        status_code: int = 422,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class LLMStreamInterruptedError(RuntimeError):
    pass


class LLMStreamProtocolError(ValueError):
    pass


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def normalize_adapter_config(config: AdapterConfig) -> AdapterConfig:
    provider = normalize_provider_alias(config.provider)
    model = config.model.strip()
    api_format = normalize_api_format_alias(_normalize_optional(config.api_format))

    if not provider:
        raise LLMValidationError("provider cannot be empty")
    if not model:
        raise LLMValidationError("model cannot be empty")

    return replace(
        config,
        provider=provider,
        model=model,
        api_format=api_format,
        base_url=_normalize_optional(config.base_url),
    )


def validate_validation_request(request: ValidationRequest) -> ValidationRequest:
    return replace(request, config=normalize_adapter_config(request.config))


def validate_chat_request(request: ChatRequest) -> ChatRequest:
    normalized_config = normalize_adapter_config(request.config)
    normalized_messages = [
        ChatMessage(
            role=message.role,
            content=message.content,
            tool_calls=list(message.tool_calls),
            tool_call_id=message.tool_call_id,
            reasoning_content=message.reasoning_content,
        )
        for message in request.messages
        if message.content.strip() or message.tool_calls or message.reasoning_content.strip()
    ]
    user_text = request.user_text.strip()

    if not request.agent_id.strip():
        raise LLMValidationError("agent_id cannot be empty")
    if not request.agent_name.strip():
        raise LLMValidationError("agent_name cannot be empty")
    if not user_text:
        raise LLMValidationError("user_text cannot be empty")
    if not normalized_messages:
        raise LLMValidationError("messages cannot be empty")
    if request.attachments and not normalized_config.capabilities.supports_image_input:
        raise LLMValidationError(
            "image attachments are not supported by the current model",
            code="IMAGE_NOT_SUPPORTED",
        )

    return replace(
        request,
        config=normalized_config,
        messages=normalized_messages,
        user_text=user_text,
        system_prompt=request.system_prompt.strip(),
        thinking=request.thinking,
    )
