from __future__ import annotations

from app.models import Agent, ModelConfig
from app.security import SECRET_PREFIX


def build_payload(**overrides):
    payload = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "displayName": "OpenAI - GPT-4o Mini",
        "apiFormat": "openai",
        "baseUrl": "https://api.openai.com/v1",
        "useFullUrl": False,
        "apiKey": "secret-key",
        "capabilities": {
            "supportsImageInput": True,
            "supportsFileInput": False,
            "supportsStreaming": True,
            "contextWindow": 128000,
        },
    }
    payload.update(overrides)
    return payload


def test_get_model_configs_returns_empty_list_by_default(client):
    response = client.get("/api/v1/model-configs")

    assert response.status_code == 200
    assert response.json() == []


def test_post_model_config_creates_and_validates_record(client):
    response = client.post("/api/v1/model-configs", json=build_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o-mini"
    assert body["displayName"] == "OpenAI - GPT-4o Mini"
    assert body["status"] == "available"
    assert body["statusMessage"] == "Model config validated successfully"
    assert body["apiKeyConfigured"] is True
    assert "apiKey" not in body
    assert body["capabilities"] == {
        "supportsImageInput": True,
        "supportsFileInput": False,
        "supportsStreaming": True,
        "contextWindow": 128000,
    }

    list_response = client.get("/api/v1/model-configs")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    with client.app.state.session_factory() as db:
        model_config = db.get(ModelConfig, body["id"])
        assert model_config is not None
        assert model_config.api_key_encrypted != "secret-key"
        assert model_config.api_key_encrypted.startswith(SECRET_PREFIX)


def test_post_model_config_requires_api_key(client):
    response = client.post(
        "/api/v1/model-configs",
        json=build_payload(apiKey=""),
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "message": "apiKey cannot be empty"}
    }


def test_patch_model_config_revalidates_and_marks_bound_agent_unavailable(client):
    create_response = client.post("/api/v1/model-configs", json=build_payload())
    model_config_id = create_response.json()["id"]

    with client.app.state.session_factory() as db:
        agent = db.get(Agent, "architect")
        agent.model_config_id = model_config_id
        agent.model_unavailable = False
        db.commit()

    response = client.patch(
        f"/api/v1/model-configs/{model_config_id}",
        json={"baseUrl": "   "},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["statusMessage"] == "baseUrl cannot be empty"

    agents_response = client.get("/api/v1/agents")
    architect = next(agent for agent in agents_response.json() if agent["id"] == "architect")
    assert architect["modelConfigId"] == model_config_id
    assert architect["modelUnavailable"] is True


def test_patch_model_config_omitting_api_key_preserves_ciphertext_and_empty_string_clears_it(client):
    create_response = client.post("/api/v1/model-configs", json=build_payload())
    model_config_id = create_response.json()["id"]

    with client.app.state.session_factory() as db:
        original = db.get(ModelConfig, model_config_id)
        assert original is not None
        original_ciphertext = original.api_key_encrypted

    preserve_response = client.patch(
        f"/api/v1/model-configs/{model_config_id}",
        json={"displayName": "Renamed Config"},
    )
    assert preserve_response.status_code == 200
    assert preserve_response.json()["apiKeyConfigured"] is True

    with client.app.state.session_factory() as db:
        preserved = db.get(ModelConfig, model_config_id)
        assert preserved is not None
        assert preserved.display_name == "Renamed Config"
        assert preserved.api_key_encrypted == original_ciphertext

    clear_response = client.patch(
        f"/api/v1/model-configs/{model_config_id}",
        json={"apiKey": ""},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["apiKeyConfigured"] is False
    assert clear_response.json()["status"] == "failed"
    assert clear_response.json()["statusMessage"] == "apiKey cannot be empty"

    with client.app.state.session_factory() as db:
        cleared = db.get(ModelConfig, model_config_id)
        assert cleared is not None
        assert cleared.api_key_encrypted == ""


def test_validate_model_config_recovers_bound_agent_when_validation_succeeds(client):
    create_response = client.post("/api/v1/model-configs", json=build_payload())
    model_config_id = create_response.json()["id"]

    with client.app.state.session_factory() as db:
        agent = db.get(Agent, "architect")
        model_config = db.get(ModelConfig, model_config_id)
        agent.model_config_id = model_config_id
        agent.model_unavailable = True
        model_config.status = "failed"
        model_config.status_message = "baseUrl cannot be empty"
        model_config.base_url = "https://api.openai.com/v1"
        db.commit()

    response = client.post(f"/api/v1/model-configs/{model_config_id}/validate")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["statusMessage"] == "Model config validated successfully"

    agents_response = client.get("/api/v1/agents")
    architect = next(agent for agent in agents_response.json() if agent["id"] == "architect")
    assert architect["modelUnavailable"] is False


def test_delete_model_config_marks_bound_agents_unavailable_without_deleting_them(client):
    create_response = client.post("/api/v1/model-configs", json=build_payload())
    model_config_id = create_response.json()["id"]

    with client.app.state.session_factory() as db:
        agent = db.get(Agent, "architect")
        agent.model_config_id = model_config_id
        agent.model_unavailable = False
        db.commit()

    delete_response = client.delete(f"/api/v1/model-configs/{model_config_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/model-configs")
    assert list_response.status_code == 200
    assert list_response.json() == []

    agents_response = client.get("/api/v1/agents")
    architect = next(agent for agent in agents_response.json() if agent["id"] == "architect")
    assert architect["id"] == "architect"
    assert architect["modelConfigId"] == model_config_id
    assert architect["modelUnavailable"] is True


def test_model_config_endpoints_return_not_found_for_missing_record(client):
    patch_response = client.patch(
        "/api/v1/model-configs/missing-id",
        json={"displayName": "Updated"},
    )
    validate_response = client.post("/api/v1/model-configs/missing-id/validate")
    delete_response = client.delete("/api/v1/model-configs/missing-id")

    expected = {
        "error": {"code": "model_config_not_found", "message": "Model config not found"}
    }
    assert patch_response.status_code == 404
    assert patch_response.json() == expected
    assert validate_response.status_code == 404
    assert validate_response.json() == expected
    assert delete_response.status_code == 404
    assert delete_response.json() == expected
