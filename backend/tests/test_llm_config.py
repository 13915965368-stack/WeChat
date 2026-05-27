import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Base, LLMSettings
from app.config import get_settings
from app.services.llm_service import get_llm_runtime_config
from app.security import SECRET_PREFIX


def test_settings_expose_database_and_llm_defaults(test_db_path):
    settings = get_settings()

    assert settings.database_url == f"sqlite:///{test_db_path.as_posix()}"
    assert settings.llm_provider == "mock"
    assert settings.llm_model == "mock-model"
    assert settings.llm_api_key == ""
    assert settings.model_config_encryption_key


def test_get_llm_runtime_config_reads_env_values(monkeypatch, test_db_path):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_API_KEY", "secret-key")

    runtime_config = get_llm_runtime_config()

    assert runtime_config == {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "hasApiKey": True,
    }


def test_get_llm_settings_returns_runtime_status(client):
    response = client.get("/api/v1/settings/llm")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "mock",
        "model": "mock-model",
        "hasApiKey": False,
    }


def test_put_llm_settings_updates_runtime_status(client):
    put_response = client.put(
        "/api/v1/settings/llm",
        json={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "apiKey": "secret-key",
        },
    )

    assert put_response.status_code == 200
    assert put_response.json() == {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "hasApiKey": True,
    }
    assert "apiKey" not in put_response.json()

    get_response = client.get("/api/v1/settings/llm")

    assert get_response.status_code == 200
    assert get_response.json() == {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "hasApiKey": True,
    }
    assert "apiKey" not in get_response.json()

    with client.app.state.session_factory() as db:
        saved_settings = db.get(LLMSettings, 1)
        assert saved_settings is not None
        assert saved_settings.api_key != "secret-key"
        assert saved_settings.api_key.startswith(SECRET_PREFIX)


def test_put_llm_settings_uses_business_error_codes(client):
    empty_provider = client.put(
        "/api/v1/settings/llm",
        json={"provider": "   ", "model": "gpt-4o-mini", "apiKey": "secret-key"},
    )
    assert empty_provider.status_code == 422
    assert empty_provider.json() == {
        "error": {"code": "llm_provider_required", "message": "provider cannot be empty"}
    }

    empty_model = client.put(
        "/api/v1/settings/llm",
        json={"provider": "openai", "model": "   ", "apiKey": "secret-key"},
    )
    assert empty_model.status_code == 422
    assert empty_model.json() == {
        "error": {"code": "llm_model_required", "message": "model cannot be empty"}
    }


def test_llm_settings_openapi_marked_as_compatibility_api(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    get_operation = paths["/api/v1/settings/llm"]["get"]
    put_operation = paths["/api/v1/settings/llm"]["put"]

    for operation in (get_operation, put_operation):
        assert operation["deprecated"] is True
        assert "兼容旧数据" in operation["description"]
        assert "/api/v1/model-configs" in operation["description"]

    put_examples = put_operation["responses"]["422"]["content"]["application/json"]["examples"]
    assert put_examples["provider_required"]["value"]["error"]["code"] == "llm_provider_required"
    assert put_examples["model_required"]["value"]["error"]["code"] == "llm_model_required"


def test_plaintext_llm_settings_are_migrated_to_ciphertext_on_startup(test_db_path):
    app = create_app()
    Base.metadata.create_all(bind=app.state.engine)

    try:
        with app.state.session_factory() as db:
            db.add(
                LLMSettings(
                    id=1,
                    provider="openai",
                    model="gpt-4o-mini",
                    api_key="legacy-secret",
                    updated_at="2026-05-26T00:00:00.000Z",
                )
            )
            db.commit()

        with TestClient(app):
            pass

        with app.state.session_factory() as db:
            migrated = db.get(LLMSettings, 1)
            assert migrated is not None
            assert migrated.api_key != "legacy-secret"
            assert migrated.api_key.startswith(SECRET_PREFIX)
    finally:
        app.state.engine.dispose()


def test_missing_encryption_key_fails_app_startup(monkeypatch, test_db_path):
    monkeypatch.delenv("MODEL_CONFIG_ENCRYPTION_KEY", raising=False)
    app = create_app()

    with pytest.raises(RuntimeError, match="MODEL_CONFIG_ENCRYPTION_KEY is required"):
        with TestClient(app):
            pass
