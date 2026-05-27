from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common import error_response, error_responses
from app.db import get_db
from app.schemas import LLMRuntimeConfigResponse, LLMSettingsUpdateRequest
from app.services.llm_service import get_llm_status, save_llm_settings

router = APIRouter(tags=["settings"])

COMPATIBILITY_DESCRIPTION = (
    "兼容旧数据的 LLM 设置接口。该接口保留给旧设置页和历史调用方使用，"
    "不再作为模型管理主入口；新的主链路请使用 `/api/v1/model-configs`。"
)


@router.get(
    "/settings/llm",
    response_model=LLMRuntimeConfigResponse,
    summary="读取 LLM 兼容配置",
    description=COMPATIBILITY_DESCRIPTION,
    deprecated=True,
)
def get_llm_settings(db: Session = Depends(get_db)) -> LLMRuntimeConfigResponse:
    return LLMRuntimeConfigResponse.model_validate(get_llm_status(db))


@router.put(
    "/settings/llm",
    response_model=LLMRuntimeConfigResponse,
    summary="更新 LLM 兼容配置",
    description=COMPATIBILITY_DESCRIPTION,
    deprecated=True,
    responses={
        422: error_responses(
            "兼容接口参数校验失败",
            ("provider_required", "llm_provider_required", "provider cannot be empty"),
            ("model_required", "llm_model_required", "model cannot be empty"),
        ),
    },
)
def put_llm_settings(payload: LLMSettingsUpdateRequest, db: Session = Depends(get_db)):
    provider = payload.provider.strip()
    model = payload.model.strip()
    api_key = payload.api_key.strip()

    if not provider:
        return error_response(422, "llm_provider_required", "provider cannot be empty")
    if not model:
        return error_response(422, "llm_model_required", "model cannot be empty")

    saved_settings = save_llm_settings(db, provider=provider, model=model, api_key=api_key)
    return LLMRuntimeConfigResponse.model_validate(
        {
            "provider": saved_settings.provider,
            "model": saved_settings.model,
            "has_api_key": bool(saved_settings.api_key),
        }
    )
