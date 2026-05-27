from __future__ import annotations

OPENAI_COMPATIBLE_PROVIDERS = {
    "mock",
    "openai",
    "openai-compatible",
    "deepseek",
    "glm",
    "zhipu",
    "qwen",
    "dashscope",
    "minimax",
    "moonshot",
    "kimi",
    "openrouter",
}

CUSTOM_OPENAI_PROVIDERS = {
    "custom",
    "custom-compatible",
    "custom_openai_compatible",
}

ANTHROPIC_PROVIDERS = {"anthropic"}
GEMINI_PROVIDERS = {"gemini"}

OPENAI_COMPATIBLE_API_FORMATS = {"openai", "openai_chat"}
ANTHROPIC_API_FORMATS = {"anthropic", "anthropic_messages"}
GEMINI_API_FORMATS = {"gemini", "gemini_generate_content"}

PROVIDER_CANONICAL_MAP = {
    "openai-compatible": "openai",
    "zhipu": "glm",
    "dashscope": "qwen",
    "kimi": "moonshot",
    "custom": "custom_openai_compatible",
    "custom-compatible": "custom_openai_compatible",
}

API_FORMAT_CANONICAL_MAP = {
    "openai": "openai_chat",
    "anthropic": "anthropic_messages",
    "gemini": "gemini_generate_content",
}


def normalize_provider_alias(provider: str) -> str:
    normalized = provider.strip().lower()
    return PROVIDER_CANONICAL_MAP.get(normalized, normalized)


def normalize_api_format_alias(api_format: str | None) -> str | None:
    if api_format is None:
        return None
    normalized = api_format.strip().lower()
    if not normalized:
        return None
    return API_FORMAT_CANONICAL_MAP.get(normalized, normalized)
