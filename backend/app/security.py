from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

SECRET_PREFIX = "enc:v1:"


@lru_cache(maxsize=4)
def _build_fernet(raw_key: str) -> Fernet:
    return Fernet(raw_key.encode("utf-8"))


def validate_encryption_key(settings) -> None:
    raw_key = settings.model_config_encryption_key.strip()
    if not raw_key:
        raise RuntimeError("MODEL_CONFIG_ENCRYPTION_KEY is required")
    try:
        _build_fernet(raw_key)
    except Exception as exc:  # pragma: no cover - cryptography error types vary
        raise RuntimeError("MODEL_CONFIG_ENCRYPTION_KEY is invalid") from exc


def is_encrypted_secret(value: str) -> bool:
    return value.startswith(SECRET_PREFIX)


def needs_secret_migration(value: str) -> bool:
    return bool(value.strip()) and not is_encrypted_secret(value)


def encrypt_secret(raw_value: str, settings) -> str:
    trimmed = raw_value.strip()
    if not trimmed:
        return ""

    validate_encryption_key(settings)
    token = _build_fernet(settings.model_config_encryption_key.strip()).encrypt(
        trimmed.encode("utf-8")
    )
    return f"{SECRET_PREFIX}{token.decode('utf-8')}"


def decrypt_secret(stored_value: str, settings) -> str:
    trimmed = stored_value.strip()
    if not trimmed:
        return ""
    if not is_encrypted_secret(trimmed):
        raise RuntimeError("Stored API key is not encrypted")

    validate_encryption_key(settings)
    token = trimmed.removeprefix(SECRET_PREFIX).encode("utf-8")
    try:
        return _build_fernet(settings.model_config_encryption_key.strip()).decrypt(token).decode(
            "utf-8"
        )
    except InvalidToken as exc:
        raise RuntimeError("Stored API key cannot be decrypted") from exc
