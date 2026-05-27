from __future__ import annotations

from sqlalchemy.orm import Session

from app.common import utc_now_iso
from app.config import get_settings
from app.models import LLMSettings
from app.security import encrypt_secret


def get_llm_runtime_config() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "hasApiKey": bool(settings.llm_api_key),
    }


def get_llm_status(db: Session) -> dict[str, str | bool]:
    saved_settings = db.get(LLMSettings, 1)
    if saved_settings is None:
        return get_llm_runtime_config()

    return {
        "provider": saved_settings.provider,
        "model": saved_settings.model,
        "hasApiKey": bool(saved_settings.api_key),
    }


def save_llm_settings(db: Session, *, provider: str, model: str, api_key: str) -> LLMSettings:
    now = utc_now_iso()
    settings = get_settings()
    encrypted_api_key = encrypt_secret(api_key, settings)
    saved_settings = db.get(LLMSettings, 1)
    if saved_settings is None:
        saved_settings = LLMSettings(
            id=1,
            provider=provider,
            model=model,
            api_key=encrypted_api_key,
            updated_at=now,
        )
        db.add(saved_settings)
    else:
        saved_settings.provider = provider
        saved_settings.model = model
        saved_settings.api_key = encrypted_api_key
        saved_settings.updated_at = now

    db.commit()
    db.refresh(saved_settings)
    return saved_settings
