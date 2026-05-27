from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LLMSettings, ModelConfig
from app.security import encrypt_secret, needs_secret_migration


def migrate_plaintext_api_keys(db: Session, settings) -> None:
    mutated = False

    model_configs = db.scalars(select(ModelConfig)).all()
    for model_config in model_configs:
        if needs_secret_migration(model_config.api_key_encrypted):
            model_config.api_key_encrypted = encrypt_secret(model_config.api_key_encrypted, settings)
            mutated = True

    runtime_settings = db.scalars(select(LLMSettings)).all()
    for runtime_setting in runtime_settings:
        if needs_secret_migration(runtime_setting.api_key):
            runtime_setting.api_key = encrypt_secret(runtime_setting.api_key, settings)
            mutated = True

    if mutated:
        db.commit()
