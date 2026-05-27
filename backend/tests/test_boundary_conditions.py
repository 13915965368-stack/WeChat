from __future__ import annotations

from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import seed_default_data

P = "/api/v1"


@pytest.fixture
def test_db_path(tmp_path, monkeypatch):
    db_path = tmp_path / "test_boundary.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock-model")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv(
        "MODEL_CONFIG_ENCRYPTION_KEY",
        "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    )
    yield db_path


@pytest.fixture
def client(test_db_path):
    app = create_app()
    with TestClient(app) as test_client:
        with app.state.session_factory() as db:
            seed_default_data(db)
        yield test_client


class TestMessageBoundaryConditions:
    def test_content_exactly_4000_chars_succeeds(self, client):
        r = client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
            "content": "x" * 4000,
        })
        assert r.status_code == 201

    def test_content_4001_chars_rejected(self, client):
        r = client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
            "content": "x" * 4001,
        })
        assert r.status_code == 422
        assert "too long" in r.json()["error"]["message"]

    def test_content_single_char_succeeds(self, client):
        r = client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
            "content": "a",
        })
        assert r.status_code == 201

    def test_content_unicode_succeeds(self, client):
        r = client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
            "content": "你好世界 🌍 émojis",
        })
        assert r.status_code == 201
        assert r.json()["userMessage"]["content"] == "你好世界 🌍 émojis"

    def test_content_with_newlines_succeeds(self, client):
        r = client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
            "content": "line1\nline2\nline3",
        })
        assert r.status_code == 201

    def test_conversation_id_whitespace_trimmed(self, client):
        r = client.post(f"{P}/messages", json={
            "conversationId": "  direct-architect-default  ",
            "content": "test",
        })
        assert r.status_code == 201

    def test_missing_conversation_id_field(self, client):
        r = client.post(f"{P}/messages", json={
            "content": "test",
        })
        assert r.status_code == 422

    def test_missing_content_field(self, client):
        r = client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
        })
        assert r.status_code == 422


class TestConversationBoundaryConditions:
    def test_create_direct_with_whitespace_only_title(self, client):
        r = client.post(f"{P}/conversations/direct", json={
            "agentId": "critic",
            "title": "   ",
        })
        assert r.status_code == 422

    def test_create_direct_with_null_title_gets_default(self, client):
        r = client.post(f"{P}/conversations/direct", json={
            "agentId": "writer",
        })
        assert r.status_code == 201
        assert "Writer" in r.json()["title"]

    def test_create_group_with_exactly_two_members(self, client):
        r = client.post(f"{P}/conversations/group", json={
            "title": "二人组",
            "memberIds": ["architect", "critic"],
        })
        assert r.status_code == 201
        assert r.json()["memberIds"] == ["user", "architect", "critic"]

    def test_create_group_with_three_members(self, client):
        r = client.post(f"{P}/conversations/group", json={
            "title": "三人组",
            "memberIds": ["architect", "critic", "writer"],
        })
        assert r.status_code == 201
        assert len(r.json()["memberIds"]) == 4

    def test_create_group_with_whitespace_member_ids_filtered(self, client):
        r = client.post(f"{P}/conversations/group", json={
            "title": "测试",
            "memberIds": ["  architect  ", "critic"],
        })
        assert r.status_code == 201

    def test_create_direct_same_agent_twice_returns_existing(self, client):
        r1 = client.post(f"{P}/conversations/direct", json={"agentId": "critic"})
        r2 = client.post(f"{P}/conversations/direct", json={"agentId": "critic"})
        assert r1.status_code == 201
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]

    def test_conversation_id_is_32_char_hex(self, client):
        r = client.post(f"{P}/conversations/direct", json={"agentId": "writer"})
        conv_id = r.json()["id"]
        assert len(conv_id) == 32
        int(conv_id, 16)


class TestAgentBoundaryConditions:
    def test_update_agent_with_long_name(self, client):
        long_name = "A" * 128
        r = client.put(f"{P}/agents/architect", json={
            "name": long_name,
            "roleSummary": "r",
            "styleSummary": "s",
            "systemPrompt": "p",
            "avatar": "X",
        })
        assert r.status_code == 200
        assert r.json()["name"] == long_name

    def test_update_agent_with_unicode(self, client):
        r = client.put(f"{P}/agents/architect", json={
            "name": "架构师 🏗️",
            "roleSummary": "结构化拆解与系统设计",
            "styleSummary": "表达克制",
            "systemPrompt": "你是一个智能助手。",
            "avatar": "架",
        })
        assert r.status_code == 200
        assert r.json()["name"] == "架构师 🏗️"

    def test_update_agent_avatar_image_base64(self, client):
        r = client.put(f"{P}/agents/architect", json={
            "name": "Architect",
            "roleSummary": "r",
            "styleSummary": "s",
            "systemPrompt": "p",
            "avatar": "A",
            "avatarImage": "data:image/png;base64,iVBORw0KGgo=",
        })
        assert r.status_code == 200
        assert r.json()["avatarImage"] == "data:image/png;base64,iVBORw0KGgo="

    def test_update_agent_null_avatar_image(self, client):
        r = client.put(f"{P}/agents/architect", json={
            "name": "Architect",
            "roleSummary": "r",
            "styleSummary": "s",
            "systemPrompt": "p",
            "avatar": "A",
            "avatarImage": None,
        })
        assert r.status_code == 200
        assert r.json()["avatarImage"] is None

    def test_update_agent_preserves_other_agents(self, client):
        client.put(f"{P}/agents/architect", json={
            "name": "Modified",
            "roleSummary": "r",
            "styleSummary": "s",
            "systemPrompt": "p",
            "avatar": "M",
        })
        r = client.get(f"{P}/agents")
        agents = {a["id"]: a for a in r.json()}
        assert agents["critic"]["name"] == "Critic"
        assert agents["writer"]["name"] == "Writer"


class TestSettingsBoundaryConditions:
    def test_put_llm_settings_with_long_api_key(self, client):
        long_key = "sk-" + "a" * 200
        r = client.put(f"{P}/settings/llm", json={
            "provider": "openai",
            "model": "gpt-4o",
            "apiKey": long_key,
        })
        assert r.status_code == 200
        assert r.json()["hasApiKey"] is True

    def test_put_llm_settings_api_key_not_exposed(self, client):
        client.put(f"{P}/settings/llm", json={
            "provider": "openai",
            "model": "gpt-4o",
            "apiKey": "super-secret-key",
        })
        r = client.get(f"{P}/settings/llm")
        body = r.json()
        assert "apiKey" not in body
        assert body["hasApiKey"] is True

    def test_put_then_get_llm_settings_consistency(self, client):
        client.put(f"{P}/settings/llm", json={
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "apiKey": "sk-ant-test",
        })
        r = client.get(f"{P}/settings/llm")
        body = r.json()
        assert body["provider"] == "anthropic"
        assert body["model"] == "claude-3-5-sonnet"
        assert body["hasApiKey"] is True

    def test_put_llm_settings_overwrite(self, client):
        client.put(f"{P}/settings/llm", json={
            "provider": "openai",
            "model": "gpt-4o",
            "apiKey": "key1",
        })
        client.put(f"{P}/settings/llm", json={
            "provider": "anthropic",
            "model": "claude-3",
            "apiKey": "",
        })
        r = client.get(f"{P}/settings/llm")
        assert r.json()["provider"] == "anthropic"
        assert r.json()["hasApiKey"] is False


class TestErrorFormatConsistency:
    def _assert_error_format(self, response, status_code, code):
        assert response.status_code == status_code
        body = response.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert body["error"]["code"] == code

    def test_404_agent_not_found_format(self, client):
        r = client.put(f"{P}/agents/nonexistent", json={
            "name": "X", "roleSummary": "r", "styleSummary": "s",
            "systemPrompt": "p", "avatar": "A",
        })
        self._assert_error_format(r, 404, "agent_not_found")

    def test_404_conversation_not_found_in_direct(self, client):
        r = client.post(f"{P}/conversations/direct", json={
            "agentId": "nonexistent", "title": "test",
        })
        self._assert_error_format(r, 404, "agent_not_found")

    def test_404_conversation_not_found_in_messages(self, client):
        r = client.get(f"{P}/messages", params={"conversationId": "nonexistent"})
        self._assert_error_format(r, 404, "conversation_not_found")

    def test_404_conversation_not_found_in_post_message(self, client):
        r = client.post(f"{P}/messages", json={
            "conversationId": "nonexistent", "content": "hello",
        })
        self._assert_error_format(r, 404, "conversation_not_found")

    def test_422_validation_error_format(self, client):
        r = client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
            "content": "   ",
        })
        self._assert_error_format(r, 422, "validation_error")

    def test_422_group_validation_format(self, client):
        r = client.post(f"{P}/conversations/group", json={
            "title": "test",
            "memberIds": ["architect"],
        })
        self._assert_error_format(r, 422, "validation_error")


class TestMessageFlowIntegrity:
    def test_send_message_updates_conversation_timestamp(self, client):
        convs_before = client.get(f"{P}/conversations").json()
        direct_before = [c for c in convs_before if c["id"] == "direct-architect-default"][0]

        r = client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
            "content": "timestamp test",
        })
        updated_at = r.json()["conversationUpdatedAt"]

        convs_after = client.get(f"{P}/conversations").json()
        direct_after = [c for c in convs_after if c["id"] == "direct-architect-default"][0]

        assert direct_after["updatedAt"] == updated_at
        assert direct_after["updatedAt"] >= direct_before["updatedAt"]

    def test_group_reply_order_matches_member_order(self, client):
        r = client.post(f"{P}/conversations/group", json={
            "title": "顺序测试",
            "memberIds": ["critic", "writer", "architect"],
        })
        conv_id = r.json()["id"]

        msg_r = client.post(f"{P}/messages", json={
            "conversationId": conv_id,
            "content": "顺序测试",
        })
        sender_ids = [m["senderId"] for m in msg_r.json()["agentMessages"]]
        assert sender_ids == ["critic", "writer", "architect"]

    def test_direct_conversation_only_main_agent_replies(self, client):
        r = client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
            "content": "只有 architect 回复",
        })
        agent_msgs = r.json()["agentMessages"]
        assert len(agent_msgs) == 1
        assert agent_msgs[0]["senderId"] == "architect"

    def test_messages_ordered_by_created_at(self, client):
        client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
            "content": "first message",
        })
        client.post(f"{P}/messages", json={
            "conversationId": "direct-architect-default",
            "content": "second message",
        })

        r = client.get(f"{P}/messages", params={"conversationId": "direct-architect-default"})
        items = r.json()["items"]
        for i in range(1, len(items)):
            assert items[i]["createdAt"] >= items[i - 1]["createdAt"]
