"""Verify that error_response() + response_model do NOT interfere with each other.

BUG-1 hypothesis: route handlers declare response_model but also return
error_response() (a JSONResponse). If FastAPI tried to serialize a JSONResponse
through response_model, the error body would be corrupted or a 500 would occur.

FastAPI fact: when a handler returns a Response subclass (including JSONResponse),
FastAPI skips response_model serialization entirely and returns the Response as-is.

This test exercises EVERY error path in ALL route handlers to confirm:
  1. The correct HTTP status code is returned.
  2. The error body matches the expected {"error": {"code": ..., "message": ...}} shape.
  3. No response_model filtering corrupts the error payload.

Uses the project's conftest.py fixtures (test_db_path + client) which properly
set up an isolated SQLite database with seed data.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def assert_error_response(response, expected_status: int, expected_code: str):
    """Assert the response is a well-formed error_response()."""
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}. "
        f"Body: {response.json()}"
    )
    body = response.json()
    assert "error" in body, f"Missing 'error' key in body: {body}"
    assert "code" in body["error"], f"Missing 'code' in error: {body}"
    assert "message" in body["error"], f"Missing 'message' in error: {body}"
    assert body["error"]["code"] == expected_code, (
        f"Expected error code '{expected_code}', got '{body['error']['code']}'"
    )


# ===================================================================
# agents.py error paths
# ===================================================================

class TestAgentsErrorPaths:
    """PUT /agents/{agent_id} has 6 error paths."""

    def test_update_agent_not_found(self, client):
        """404 - agent_id does not exist in DB."""
        resp = client.put(
            "/api/v1/agents/nonexistent-id",
            json={
                "name": "X",
                "roleSummary": "X",
                "styleSummary": "X",
                "systemPrompt": "X",
                "avatar": "X",
            },
        )
        assert_error_response(resp, 404, "agent_not_found")

    def test_update_agent_empty_name(self, client):
        """422 - name is whitespace-only."""
        resp = client.put(
            "/api/v1/agents/architect",
            json={
                "name": "   ",
                "roleSummary": "valid",
                "styleSummary": "valid",
                "systemPrompt": "valid",
                "avatar": "valid",
            },
        )
        assert_error_response(resp, 422, "validation_error")
        assert "name" in resp.json()["error"]["message"].lower()

    def test_update_agent_empty_role_summary(self, client):
        """422 - roleSummary is whitespace-only."""
        resp = client.put(
            "/api/v1/agents/architect",
            json={
                "name": "valid",
                "roleSummary": "   ",
                "styleSummary": "valid",
                "systemPrompt": "valid",
                "avatar": "valid",
            },
        )
        assert_error_response(resp, 422, "validation_error")
        assert "rolesummary" in resp.json()["error"]["message"].lower()

    def test_update_agent_empty_style_summary(self, client):
        """422 - styleSummary is whitespace-only."""
        resp = client.put(
            "/api/v1/agents/architect",
            json={
                "name": "valid",
                "roleSummary": "valid",
                "styleSummary": "   ",
                "systemPrompt": "valid",
                "avatar": "valid",
            },
        )
        assert_error_response(resp, 422, "validation_error")
        assert "stylesummary" in resp.json()["error"]["message"].lower()

    def test_update_agent_empty_system_prompt(self, client):
        """422 - systemPrompt is whitespace-only."""
        resp = client.put(
            "/api/v1/agents/architect",
            json={
                "name": "valid",
                "roleSummary": "valid",
                "styleSummary": "valid",
                "systemPrompt": "   ",
                "avatar": "valid",
            },
        )
        assert_error_response(resp, 422, "validation_error")
        assert "systemprompt" in resp.json()["error"]["message"].lower()

    def test_update_agent_empty_avatar(self, client):
        """422 - avatar is whitespace-only."""
        resp = client.put(
            "/api/v1/agents/architect",
            json={
                "name": "valid",
                "roleSummary": "valid",
                "styleSummary": "valid",
                "systemPrompt": "valid",
                "avatar": "   ",
            },
        )
        assert_error_response(resp, 422, "validation_error")
        assert "avatar" in resp.json()["error"]["message"].lower()


# ===================================================================
# conversations.py error paths
# ===================================================================

class TestConversationsErrorPaths:
    """POST /conversations/direct has 3 error paths.
    POST /conversations/group has 3 error paths."""

    # --- direct conversation ---

    def test_create_direct_empty_agent_id(self, client):
        """422 - agentId is whitespace-only."""
        resp = client.post(
            "/api/v1/conversations/direct",
            json={"agentId": "   "},
        )
        assert_error_response(resp, 422, "validation_error")
        assert "agentid" in resp.json()["error"]["message"].lower()

    def test_create_direct_empty_title(self, client):
        """422 - title is whitespace-only (non-None)."""
        resp = client.post(
            "/api/v1/conversations/direct",
            json={"agentId": "critic", "title": "   "},
        )
        assert_error_response(resp, 422, "validation_error")
        assert "title" in resp.json()["error"]["message"].lower()

    def test_create_direct_agent_not_found(self, client):
        """404 - agentId references a non-existent agent."""
        resp = client.post(
            "/api/v1/conversations/direct",
            json={"agentId": "nonexistent-agent"},
        )
        assert_error_response(resp, 404, "agent_not_found")

    # --- group conversation ---

    def test_create_group_empty_title(self, client):
        """422 - title is whitespace-only."""
        resp = client.post(
            "/api/v1/conversations/group",
            json={"title": "   ", "memberIds": ["architect", "critic"]},
        )
        assert_error_response(resp, 422, "validation_error")
        assert "title" in resp.json()["error"]["message"].lower()

    def test_create_group_insufficient_member_ids(self, client):
        """422 - memberIds has fewer than 2 unique ids."""
        resp = client.post(
            "/api/v1/conversations/group",
            json={"title": "Group", "memberIds": ["architect"]},
        )
        assert_error_response(resp, 422, "validation_error")
        assert "memberids" in resp.json()["error"]["message"].lower()

    def test_create_group_duplicate_member_ids(self, client):
        """422 - memberIds has duplicates (not enough unique ids)."""
        resp = client.post(
            "/api/v1/conversations/group",
            json={"title": "Group", "memberIds": ["architect", "architect"]},
        )
        assert_error_response(resp, 422, "validation_error")

    def test_create_group_invalid_agent_ids(self, client):
        """422 - memberIds references non-existent agents."""
        resp = client.post(
            "/api/v1/conversations/group",
            json={"title": "Group", "memberIds": ["architect", "nonexistent-id"]},
        )
        assert_error_response(resp, 422, "validation_error")
        assert "invalid" in resp.json()["error"]["message"].lower()


# ===================================================================
# messages.py error paths
# ===================================================================

class TestMessagesErrorPaths:
    """GET /messages has 2 error paths.
    POST /messages has 5 error paths."""

    # --- get messages ---

    def test_get_messages_empty_conversation_id(self, client):
        """422 - conversationId is whitespace-only."""
        resp = client.get("/api/v1/messages", params={"conversationId": "   "})
        assert_error_response(resp, 422, "validation_error")
        assert "conversationid" in resp.json()["error"]["message"].lower()

    def test_get_messages_conversation_not_found(self, client):
        """404 - conversationId references a non-existent conversation."""
        resp = client.get("/api/v1/messages", params={"conversationId": "nonexistent-id"})
        assert_error_response(resp, 404, "conversation_not_found")

    # --- post message ---

    def test_post_message_empty_conversation_id(self, client):
        """422 - conversationId is whitespace-only."""
        resp = client.post(
            "/api/v1/messages",
            json={"conversationId": "   ", "content": "hello"},
        )
        assert_error_response(resp, 422, "validation_error")
        assert "conversationid" in resp.json()["error"]["message"].lower()

    def test_post_message_empty_content(self, client):
        """422 - content is whitespace-only."""
        resp = client.post(
            "/api/v1/messages",
            json={"conversationId": "direct-architect-default", "content": "   "},
        )
        assert_error_response(resp, 422, "validation_error")
        assert "content" in resp.json()["error"]["message"].lower()

    def test_post_message_content_too_long(self, client):
        """422 - content exceeds 4000 characters."""
        resp = client.post(
            "/api/v1/messages",
            json={"conversationId": "direct-architect-default", "content": "x" * 4001},
        )
        assert_error_response(resp, 422, "validation_error")
        assert "too long" in resp.json()["error"]["message"].lower()

    def test_post_message_conversation_not_found(self, client):
        """404 - conversationId references a non-existent conversation."""
        resp = client.post(
            "/api/v1/messages",
            json={"conversationId": "nonexistent-id", "content": "hello"},
        )
        assert_error_response(resp, 404, "conversation_not_found")

    def test_post_message_unsupported_image_capability(self, client):
        """422 - image attachments are blocked by model capability and use uniform API code."""
        model_config_response = client.post(
            "/api/v1/model-configs",
            json={
                "provider": "openai",
                "model": "gpt-4o-mini",
                "displayName": "OpenAI - GPT-4o Mini",
                "apiFormat": "openai",
                "baseUrl": "https://api.openai.com/v1",
                "useFullUrl": False,
                "apiKey": "secret-key",
                "capabilities": {
                    "supportsImageInput": False,
                    "supportsFileInput": False,
                    "supportsStreaming": True,
                    "contextWindow": 128000,
                },
            },
        )
        model_config_id = model_config_response.json()["id"]

        bind_response = client.post(
            "/api/v1/conversations/direct",
            json={"agentId": "architect", "modelConfigId": model_config_id},
        )
        assert bind_response.status_code == 200

        resp = client.post(
            "/api/v1/messages",
            json={
                "conversationId": "direct-architect-default",
                "content": "hello",
                "attachments": [
                    {
                        "attachmentId": "att-image-unsupported",
                        "kind": "image",
                        "mimeType": "image/png",
                    }
                ],
            },
        )
        assert_error_response(resp, 422, "IMAGE_NOT_SUPPORTED")
        assert "image attachments" in resp.json()["error"]["message"].lower()


# ===================================================================
# settings.py error paths
# ===================================================================

class TestSettingsErrorPaths:
    """PUT /settings/llm has 2 error paths."""

    def test_put_llm_settings_empty_provider(self, client):
        """422 - provider is whitespace-only."""
        resp = client.put(
            "/api/v1/settings/llm",
            json={"provider": "   ", "model": "gpt-4", "apiKey": "key"},
        )
        assert_error_response(resp, 422, "llm_provider_required")
        assert "provider" in resp.json()["error"]["message"].lower()

    def test_put_llm_settings_empty_model(self, client):
        """422 - model is whitespace-only."""
        resp = client.put(
            "/api/v1/settings/llm",
            json={"provider": "openai", "model": "   ", "apiKey": "key"},
        )
        assert_error_response(resp, 422, "llm_model_required")
        assert "model" in resp.json()["error"]["message"].lower()


# ===================================================================
# Cross-cutting: response_model does NOT corrupt JSONResponse
# ===================================================================

class TestResponseModelDoesNotCorruptJSONResponse:
    """Directly verify that response_model filtering is NOT applied
    to JSONResponse returns. This is the core of BUG-1 verification."""

    def test_error_body_structure_intact(self, client):
        """The error body must have exactly {"error": {"code": ..., "message": ...}}
        with NO extra keys that response_model might inject."""
        resp = client.put(
            "/api/v1/agents/nonexistent-id",
            json={
                "name": "X",
                "roleSummary": "X",
                "styleSummary": "X",
                "systemPrompt": "X",
                "avatar": "X",
            },
        )
        body = resp.json()
        # The top-level keys should be exactly ["error"], not ["id", "name", ...]
        # which would appear if AgentResponse model filtered the output.
        assert list(body.keys()) == ["error"], (
            f"Expected only 'error' key, got: {list(body.keys())}. "
            f"response_model may have corrupted the JSONResponse."
        )
        error_obj = body["error"]
        assert list(error_obj.keys()) == ["code", "message"], (
            f"Expected 'code' and 'message' keys, got: {list(error_obj.keys())}"
        )

    def test_error_status_code_preserved(self, client):
        """JSONResponse status code must NOT be overridden by response_model."""
        # 404 case
        resp = client.put(
            "/api/v1/agents/nonexistent-id",
            json={
                "name": "X",
                "roleSummary": "X",
                "styleSummary": "X",
                "systemPrompt": "X",
                "avatar": "X",
            },
        )
        assert resp.status_code == 404, (
            f"Expected 404, got {resp.status_code}. "
            f"response_model may have forced a 200."
        )

        # 422 case
        resp = client.put(
            "/api/v1/agents/architect",
            json={
                "name": "   ",
                "roleSummary": "X",
                "styleSummary": "X",
                "systemPrompt": "X",
                "avatar": "X",
            },
        )
        assert resp.status_code == 422, (
            f"Expected 422, got {resp.status_code}. "
            f"response_model may have forced a 200."
        )

    def test_success_path_still_uses_response_model(self, client):
        """Verify that the happy path still serializes through response_model
        (camelCase aliasing), proving response_model is active but only
        for non-Response returns."""
        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        agents = resp.json()
        assert isinstance(agents, list)
        if len(agents) > 0:
            agent = agents[0]
            # AgentResponse uses alias_generator=to_camel, so DB field
            # role_summary should appear as roleSummary in the response.
            assert "roleSummary" in agent, (
                f"Expected camelCase key 'roleSummary', got keys: {list(agent.keys())}. "
                f"response_model may not be working for success paths."
            )
            # The raw field name should NOT appear
            assert "role_summary" not in agent, (
                "Snake_case 'role_summary' should not appear when "
                "response_model alias_generator is active."
            )
