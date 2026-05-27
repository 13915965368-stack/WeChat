from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.common import utc_now_iso
from app.config import get_settings
from app.llm.client_factory import create_client
from app.llm.endpoint_fallback import run_with_endpoint_fallback
from app.llm.schemas import AdapterCapabilities, AdapterConfig
from app.models import Agent, ModelConfig
from app.security import decrypt_secret, encrypt_secret
from app.schemas import (
    ModelConfigCapabilities,
    ModelConfigCreateRequest,
    ModelConfigResponse,
    ModelConfigUpdateRequest,
)


def list_model_configs(db: Session) -> list[ModelConfig]:
    return db.scalars(
        select(ModelConfig).order_by(desc(ModelConfig.updated_at), ModelConfig.id.asc())
    ).all()


def create_model_config(db: Session, payload: ModelConfigCreateRequest) -> ModelConfig:
    now = utc_now_iso()
    settings = get_settings()
    model_config = ModelConfig(
        id=f"modelcfg-{uuid4().hex}",
        provider=payload.provider.strip(),
        model=payload.model.strip(),
        display_name=payload.display_name.strip(),
        api_format=payload.api_format.strip().lower(),
        base_url=_normalize_optional(payload.base_url),
        use_full_url=payload.use_full_url,
        api_key_encrypted=encrypt_secret(payload.api_key.strip(), settings),
        status="validating",
        status_message="Validating model config",
        capabilities=_capabilities_to_mapping(payload.capabilities),
        last_validated_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(model_config)
    db.flush()
    return run_model_config_validation(db, model_config)


def update_model_config(
    db: Session, model_config: ModelConfig, payload: ModelConfigUpdateRequest
) -> ModelConfig:
    settings = get_settings()
    if payload.provider is not None:
        model_config.provider = payload.provider.strip()
    if payload.model is not None:
        model_config.model = payload.model.strip()
    if payload.display_name is not None:
        model_config.display_name = payload.display_name.strip()
    if payload.api_format is not None:
        model_config.api_format = payload.api_format.strip().lower()
    if payload.base_url is not None:
        model_config.base_url = _normalize_optional(payload.base_url)
    if payload.use_full_url is not None:
        model_config.use_full_url = payload.use_full_url
    if payload.api_key is not None:
        model_config.api_key_encrypted = encrypt_secret(payload.api_key, settings)
    if payload.capabilities is not None:
        model_config.capabilities = _capabilities_to_mapping(payload.capabilities)

    return run_model_config_validation(db, model_config)


def delete_model_config(db: Session, model_config: ModelConfig) -> None:
    _sync_bound_agents(db, model_config.id, is_available=False)
    db.delete(model_config)
    db.commit()


def run_model_config_validation(db: Session, model_config: ModelConfig) -> ModelConfig:
    validation_started_at = utc_now_iso()
    model_config.status = "validating"
    model_config.status_message = "Validating model config"
    model_config.updated_at = validation_started_at
    db.flush()

    try:
        validation_error = _prevalidate_model_config(model_config)
        if validation_error is not None:
            raise ValueError(validation_error)

        adapter_config = _build_adapter_config(model_config)
        result = run_with_endpoint_fallback(
            adapter_config,
            lambda candidate_config: create_client(candidate_config).validate(),
        )

        model_config.status = "available" if result.ok else "failed"
        model_config.status_message = result.status_message
        model_config.capabilities = _capabilities_to_mapping(result.capabilities)
    except Exception as exc:
        model_config.status = "failed"
        model_config.status_message = str(exc) or "Model validation failed"

    completed_at = utc_now_iso()
    model_config.last_validated_at = completed_at
    model_config.updated_at = completed_at
    _sync_bound_agents(db, model_config.id, is_available=model_config.status == "available")
    db.commit()
    db.refresh(model_config)
    return model_config


def serialize_model_config(model_config: ModelConfig) -> ModelConfigResponse:
    return ModelConfigResponse.model_validate(
        {
            "id": model_config.id,
            "provider": model_config.provider,
            "model": model_config.model,
            "displayName": model_config.display_name,
            "apiFormat": model_config.api_format,
            "baseUrl": model_config.base_url,
            "useFullUrl": model_config.use_full_url,
            "status": model_config.status,
            "statusMessage": model_config.status_message,
            "capabilities": _capabilities_to_mapping(model_config.capabilities),
            "apiKeyConfigured": bool(model_config.api_key_encrypted),
            "lastValidatedAt": model_config.last_validated_at,
            "createdAt": model_config.created_at,
            "updatedAt": model_config.updated_at,
        }
    )


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _prevalidate_model_config(model_config: ModelConfig) -> str | None:
    if not model_config.provider.strip():
        return "provider cannot be empty"
    if not model_config.model.strip():
        return "model cannot be empty"
    if not model_config.display_name.strip():
        return "displayName cannot be empty"
    if not model_config.api_format.strip():
        return "apiFormat cannot be empty"
    if not model_config.api_key_encrypted.strip():
        return "apiKey cannot be empty"
    if not (model_config.base_url or "").strip():
        return "baseUrl cannot be empty"
    return None


def _build_adapter_config(model_config: ModelConfig) -> AdapterConfig:
    settings = get_settings()
    return AdapterConfig(
        provider=model_config.provider,
        model=model_config.model,
        api_key=decrypt_secret(model_config.api_key_encrypted, settings),
        api_format=model_config.api_format,
        base_url=model_config.base_url,
        use_full_url=model_config.use_full_url,
        capabilities=AdapterCapabilities.from_mapping(model_config.capabilities),
        metadata={
            "model_config_id": model_config.id,
            "source": "model_config_validation",
        },
    )


def _sync_bound_agents(db: Session, model_config_id: str, *, is_available: bool) -> None:
    agents = db.scalars(select(Agent).where(Agent.model_config_id == model_config_id)).all()
    for agent in agents:
        agent.model_unavailable = not is_available


def _capabilities_to_mapping(
    capabilities: ModelConfigCapabilities | AdapterCapabilities | dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(capabilities, AdapterCapabilities):
        return {
            "supports_image_input": capabilities.supports_image_input,
            "supports_file_input": capabilities.supports_file_input,
            "supports_streaming": capabilities.supports_streaming,
            "context_window": capabilities.context_window,
        }

    if isinstance(capabilities, ModelConfigCapabilities):
        return {
            "supports_image_input": capabilities.supports_image_input,
            "supports_file_input": capabilities.supports_file_input,
            "supports_streaming": capabilities.supports_streaming,
            "context_window": capabilities.context_window,
        }

    source = capabilities or {}
    return {
        "supports_image_input": bool(
            source.get("supports_image_input", source.get("supportsImageInput", False))
        ),
        "supports_file_input": bool(
            source.get("supports_file_input", source.get("supportsFileInput", False))
        ),
        "supports_streaming": bool(
            source.get("supports_streaming", source.get("supportsStreaming", False))
        ),
        "context_window": source.get("context_window", source.get("contextWindow")),
    }
