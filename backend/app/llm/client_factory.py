from __future__ import annotations

from app.llm.registry import get_adapter_class
from app.llm.schemas import AdapterConfig
from app.llm.validator import normalize_adapter_config


def create_client(config: AdapterConfig):
    normalized_config = normalize_adapter_config(config)
    adapter_class = get_adapter_class(
        provider=normalized_config.provider,
        api_format=normalized_config.api_format,
    )
    return adapter_class(normalized_config)
