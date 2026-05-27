from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common import error_response
from app.db import get_db
from app.llm.provider_aliases import normalize_api_format_alias
from app.models import ModelConfig
from app.schemas import ModelConfigCreateRequest, ModelConfigResponse, ModelConfigUpdateRequest
from app.services.model_config_service import (
    create_model_config,
    delete_model_config,
    list_model_configs,
    run_model_config_validation,
    serialize_model_config,
    update_model_config,
)

router = APIRouter(tags=["model-configs"])
SUPPORTED_API_FORMATS = {
    "openai_chat",
    "anthropic_messages",
    "gemini_generate_content",
}


@router.get("/model-configs", response_model=list[ModelConfigResponse])
def get_model_configs(db: Session = Depends(get_db)) -> list[ModelConfigResponse]:
    return [serialize_model_config(model_config) for model_config in list_model_configs(db)]


@router.post("/model-configs", response_model=ModelConfigResponse, status_code=201)
def post_model_config(payload: ModelConfigCreateRequest, db: Session = Depends(get_db)):
    validation_error = _validate_create_payload(payload)
    if validation_error is not None:
        return error_response(422, "validation_error", validation_error)

    model_config = create_model_config(db, payload)
    return serialize_model_config(model_config)


@router.patch("/model-configs/{model_config_id}", response_model=ModelConfigResponse)
def patch_model_config(
    model_config_id: str,
    payload: ModelConfigUpdateRequest,
    db: Session = Depends(get_db),
):
    model_config = db.get(ModelConfig, model_config_id)
    if model_config is None:
        return error_response(404, "model_config_not_found", "Model config not found")

    validation_error = _validate_update_payload(payload)
    if validation_error is not None:
        return error_response(422, "validation_error", validation_error)

    updated = update_model_config(db, model_config, payload)
    return serialize_model_config(updated)


@router.post("/model-configs/{model_config_id}/validate", response_model=ModelConfigResponse)
def validate_model_config(model_config_id: str, db: Session = Depends(get_db)):
    model_config = db.get(ModelConfig, model_config_id)
    if model_config is None:
        return error_response(404, "model_config_not_found", "Model config not found")

    validated = run_model_config_validation(db, model_config)
    return serialize_model_config(validated)


@router.delete("/model-configs/{model_config_id}", status_code=204)
def remove_model_config(model_config_id: str, db: Session = Depends(get_db)):
    model_config = db.get(ModelConfig, model_config_id)
    if model_config is None:
        return error_response(404, "model_config_not_found", "Model config not found")

    delete_model_config(db, model_config)


def _validate_create_payload(payload: ModelConfigCreateRequest) -> str | None:
    if not payload.provider.strip():
        return "provider cannot be empty"
    if not payload.model.strip():
        return "model cannot be empty"
    if not payload.display_name.strip():
        return "displayName cannot be empty"
    if not payload.api_format.strip():
        return "apiFormat cannot be empty"
    normalized_api_format = normalize_api_format_alias(payload.api_format)
    if normalized_api_format not in SUPPORTED_API_FORMATS:
        return "apiFormat is not supported"
    if not payload.api_key.strip():
        return "apiKey cannot be empty"
    return None


def _validate_update_payload(payload: ModelConfigUpdateRequest) -> str | None:
    if payload.provider is not None and not payload.provider.strip():
        return "provider cannot be empty"
    if payload.model is not None and not payload.model.strip():
        return "model cannot be empty"
    if payload.display_name is not None and not payload.display_name.strip():
        return "displayName cannot be empty"
    if payload.api_format is not None and not payload.api_format.strip():
        return "apiFormat cannot be empty"
    if (
        payload.api_format is not None
        and normalize_api_format_alias(payload.api_format) not in SUPPORTED_API_FORMATS
    ):
        return "apiFormat is not supported"
    return None
