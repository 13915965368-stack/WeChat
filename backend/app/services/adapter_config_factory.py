from __future__ import annotations

from typing import Literal

from app.config import get_settings
from app.llm.schemas import AdapterCapabilities, AdapterConfig
from app.models import ModelConfig
from app.security import decrypt_secret

AdapterConfigSource = Literal["model_config", "model_config_validation"]


def build_adapter_config_from_model(
    model_config: ModelConfig,
    *,
    source: AdapterConfigSource,
) -> AdapterConfig:
    metadata: dict[str, object] = {
        "model_config_id": model_config.id,
        "source": source,
    }
    if source == "model_config":
        metadata["status"] = model_config.status

    return AdapterConfig(
        provider=model_config.provider,
        model=model_config.model,
        api_key=decrypt_secret(model_config.api_key_encrypted or "", get_settings()),
        api_format=model_config.api_format,
        base_url=model_config.base_url,
        use_full_url=model_config.use_full_url,
        capabilities=AdapterCapabilities.from_mapping(model_config.capabilities or {}),
        metadata=metadata,
    )
