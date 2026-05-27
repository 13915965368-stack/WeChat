from __future__ import annotations

from app.llm.adapters import (
    AnthropicAdapter,
    CustomCompatibleAdapter,
    GeminiAdapter,
    OpenAICompatibleAdapter,
)
from app.llm.adapters.base import BaseLLMAdapter
from app.llm.provider_aliases import (
    ANTHROPIC_API_FORMATS,
    ANTHROPIC_PROVIDERS,
    CUSTOM_OPENAI_PROVIDERS,
    GEMINI_API_FORMATS,
    GEMINI_PROVIDERS,
    OPENAI_COMPATIBLE_API_FORMATS,
    OPENAI_COMPATIBLE_PROVIDERS,
    normalize_api_format_alias,
    normalize_provider_alias,
)

PROVIDER_REGISTRY: dict[str, type[BaseLLMAdapter]] = {
    **{provider: OpenAICompatibleAdapter for provider in OPENAI_COMPATIBLE_PROVIDERS},
    **{provider: CustomCompatibleAdapter for provider in CUSTOM_OPENAI_PROVIDERS},
    **{provider: AnthropicAdapter for provider in ANTHROPIC_PROVIDERS},
    **{provider: GeminiAdapter for provider in GEMINI_PROVIDERS},
}

API_FORMAT_REGISTRY: dict[str, type[BaseLLMAdapter]] = {
    **{api_format: OpenAICompatibleAdapter for api_format in OPENAI_COMPATIBLE_API_FORMATS},
    **{api_format: AnthropicAdapter for api_format in ANTHROPIC_API_FORMATS},
    **{api_format: GeminiAdapter for api_format in GEMINI_API_FORMATS},
}


def get_adapter_class(provider: str, api_format: str | None = None) -> type[BaseLLMAdapter]:
    normalized_provider = normalize_provider_alias(provider)
    normalized_format = normalize_api_format_alias(api_format)

    if normalized_format and normalized_format in API_FORMAT_REGISTRY:
        return API_FORMAT_REGISTRY[normalized_format]
    if normalized_provider in PROVIDER_REGISTRY:
        return PROVIDER_REGISTRY[normalized_provider]
    return OpenAICompatibleAdapter


def list_registered_adapters() -> dict[str, str]:
    return {
        key: adapter_class.__name__
        for key, adapter_class in sorted(PROVIDER_REGISTRY.items())
    }
