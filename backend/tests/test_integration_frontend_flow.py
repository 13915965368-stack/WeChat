from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "integration_frontend_flow.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock-model")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv(
        "MODEL_CONFIG_ENCRYPTION_KEY",
        "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    )

    app = create_app()
    with TestClient(app, base_url="http://testserver/api/v1") as c:
        yield c


class TestM1Bootstrap:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_cors_preflight_localhost(self, client):
        r = client.options("/agents", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        })
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_cors_preflight_loopback(self, client):
        r = client.options("/agents", headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        })
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"

    def test_cors_rejects_unknown_origin(self, client):
        r = client.options("/agents", headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        })
        assert "access-control-allow-origin" not in r.headers or r.headers.get("access-control-allow-origin") != "http://evil.example.com"

    def test_get_agents(self, client):
        r = client.get("/agents")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 4
        ids = [a["id"] for a in body]
        assert ids == ["architect", "blank-agent", "critic", "writer"]
        agent = body[0]
        for key in [
            "id",
            "name",
            "roleSummary",
            "styleSummary",
            "systemPrompt",
            "avatar",
            "avatarImage",
            "themeColor",
            "themeLight",
            "themeSoft",
            "modelConfigId",
            "modelUnavailable",
            "isTemplate",
        ]:
            assert key in agent, f"Missing key: {key}"

    def test_agents_camel_case_fields(self, client):
        r = client.get("/agents")
        body = r.json()
        agent = body[0]
        assert "roleSummary" in agent
        assert "role_summary" not in agent
        assert "themeColor" in agent
        assert "theme_color" not in agent

    def test_agent_theme_values(self, client):
        r = client.get("/agents")
        body = r.json()
        by_id = {a["id"]: a for a in body}
        assert by_id["architect"]["themeColor"] == "#D4A574"
        assert by_id["critic"]["themeLight"] == "#F5DEDE"
        assert by_id["writer"]["themeSoft"] == "#F0F7F5"

    def test_get_conversations(self, client):
        r = client.get("/conversations")
        assert r.status_code == 200
        body = r.json()
        assert len(body) >= 2
        ids = [c["id"] for c in body]
        assert "group-product-discussion-default" in ids
        assert "direct-architect-default" in ids

    def test_conversations_pinned_first(self, client):
        r = client.get("/conversations")
        body = r.json()
        assert body[0]["pinned"] is True

    def test_conversation_fields(self, client):
        r = client.get("/conversations")
        body = r.json()
        for key in ["id", "type", "title", "memberIds", "agentId", "createdAt", "updatedAt", "pinned"]:
            assert key in body[0], f"Missing key: {key}"

    def test_direct_conversation_members(self, client):
        r = client.get("/conversations")
        body = r.json()
        direct = [c for c in body if c["id"] == "direct-architect-default"][0]
        assert direct["memberIds"] == ["user", "architect"]
        assert direct["agentId"] == "architect"

    def test_group_conversation_members(self, client):
        r = client.get("/conversations")
        body = r.json()
        group = [c for c in body if c["type"] == "group"][0]
        assert "user" in group["memberIds"]
        assert group["agentId"] is None

    def test_get_messages_direct(self, client):
        r = client.get("/messages", params={"conversationId": "direct-architect-default"})
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "limit" in body
        assert "offset" in body
        assert "hasMore" in body
        assert len(body["items"]) >= 1

    def test_get_messages_group(self, client):
        r = client.get("/messages", params={"conversationId": "group-product-discussion-default"})
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) >= 2

    def test_message_fields(self, client):
        r = client.get("/messages", params={"conversationId": "direct-architect-default"})
        body = r.json()
        msg = body["items"][0]
        for key in ["id", "conversationId", "senderType", "senderId", "content", "createdAt"]:
            assert key in msg, f"Missing key: {key}"

    def test_messages_pagination(self, client):
        r = client.get("/messages", params={"conversationId": "group-product-discussion-default", "limit": 1, "offset": 0})
        body = r.json()
        assert len(body["items"]) == 1
        assert body["hasMore"] is True

    def test_messages_not_found_conversation(self, client):
        r = client.get("/messages", params={"conversationId": "nonexistent"})
        assert r.status_code == 404


class TestM2AgentInteraction:
    def test_update_agent_full(self, client):
        r = client.put("/agents/architect", json={
            "name": "Architect Pro",
            "roleSummary": "升级版结构拆解",
            "styleSummary": "更偏框架",
            "systemPrompt": "你是升级后的 Architect。",
            "avatar": "AP",
            "avatarImage": "data:image/png;base64,abc",
            "themeColor": "#123456",
            "themeLight": "#ABCDEF",
            "themeSoft": "#FEDCBA",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Architect Pro"
        assert body["themeColor"] == "#123456"
        assert body["avatarImage"] == "data:image/png;base64,abc"

        list_r = client.get("/agents")
        agents = {a["id"]: a for a in list_r.json()}
        assert agents["architect"]["name"] == "Architect Pro"

    def test_update_agent_not_found(self, client):
        r = client.put("/agents/nonexistent", json={
            "name": "X", "roleSummary": "x", "styleSummary": "y",
            "systemPrompt": "z", "avatar": "M",
        })
        assert r.status_code == 404

    def test_update_agent_empty_name(self, client):
        r = client.put("/agents/architect", json={
            "name": "  ", "roleSummary": "x", "styleSummary": "y",
            "systemPrompt": "z", "avatar": "M",
        })
        assert r.status_code == 422

    def test_update_agent_null_theme(self, client):
        r = client.put("/agents/critic", json={
            "name": "Critic", "roleSummary": "r", "styleSummary": "s",
            "systemPrompt": "p", "avatar": "C",
            "themeColor": None, "themeLight": None, "themeSoft": None,
        })
        assert r.status_code == 200
        assert r.json()["themeColor"] is None


class TestM3MessageSend:
    def test_send_direct_message(self, client):
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "测试消息",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["userMessage"]["senderType"] == "user"
        assert body["userMessage"]["content"] == "测试消息"
        assert len(body["agentMessages"]) == 1
        assert body["agentMessages"][0]["senderId"] == "architect"
        assert body["conversationUpdatedAt"] == body["agentMessages"][0]["createdAt"]

    def test_send_group_message(self, client):
        r = client.post("/messages", json={
            "conversationId": "group-product-discussion-default",
            "content": "群聊测试消息",
        })
        assert r.status_code == 201
        body = r.json()
        assert len(body["agentMessages"]) == 3
        sender_ids = [m["senderId"] for m in body["agentMessages"]]
        assert set(sender_ids) == {"architect", "critic", "writer"}

    def test_send_message_persists(self, client):
        client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "持久化测试",
        })
        r = client.get("/messages", params={"conversationId": "direct-architect-default"})
        items = r.json()["items"]
        contents = [m["content"] for m in items]
        assert "持久化测试" in contents

    def test_send_empty_content(self, client):
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "   ",
        })
        assert r.status_code == 422

    def test_send_to_missing_conversation(self, client):
        r = client.post("/messages", json={
            "conversationId": "nonexistent",
            "content": "hello",
        })
        assert r.status_code == 404

    def test_send_content_at_4000_limit(self, client):
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "A" * 4000,
        })
        assert r.status_code == 201

    def test_send_content_over_4000_limit(self, client):
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "A" * 4001,
        })
        assert r.status_code == 422


class TestM4ConversationManagement:
    def test_create_direct_conversation(self, client):
        r = client.post("/conversations/direct", json={
            "agentId": "critic",
            "title": "与 Critic 的新对话",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["type"] == "direct"
        assert body["agentId"] == "critic"
        assert body["memberIds"] == ["user", "critic"]
        assert len(body["id"]) == 32

    def test_create_direct_without_title(self, client):
        r = client.post("/conversations/direct", json={
            "agentId": "writer",
        })
        assert r.status_code == 201
        assert "Writer" in r.json()["title"]

    def test_create_direct_missing_agent(self, client):
        r = client.post("/conversations/direct", json={
            "agentId": "nonexistent",
            "title": "test",
        })
        assert r.status_code == 404

    def test_create_direct_empty_agent_id(self, client):
        r = client.post("/conversations/direct", json={
            "agentId": "",
            "title": "test",
        })
        assert r.status_code == 422

    def test_create_group_conversation(self, client):
        r = client.post("/conversations/group", json={
            "title": "测试群聊",
            "memberIds": ["architect", "critic"],
        })
        assert r.status_code == 201
        body = r.json()
        assert body["type"] == "group"
        assert body["agentId"] is None
        assert body["memberIds"] == ["user", "architect", "critic"]
        assert body["pinned"] is False

    def test_create_group_too_few_members(self, client):
        r = client.post("/conversations/group", json={
            "title": "test",
            "memberIds": ["architect"],
        })
        assert r.status_code == 422

    def test_create_group_duplicate_members(self, client):
        r = client.post("/conversations/group", json={
            "title": "test",
            "memberIds": ["architect", "architect"],
        })
        assert r.status_code == 422

    def test_create_group_invalid_agents(self, client):
        r = client.post("/conversations/group", json={
            "title": "test",
            "memberIds": ["architect", "nonexistent"],
        })
        assert r.status_code == 422

    def test_create_group_blank_title(self, client):
        r = client.post("/conversations/group", json={
            "title": "   ",
            "memberIds": ["architect", "critic"],
        })
        assert r.status_code == 422


class TestM5Settings:
    def test_get_llm_settings(self, client):
        r = client.get("/settings/llm")
        assert r.status_code == 200
        body = r.json()
        assert "provider" in body
        assert "model" in body
        assert "hasApiKey" in body
        assert "apiKey" not in body

    def test_put_llm_settings(self, client):
        r = client.put("/settings/llm", json={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "apiKey": "sk-test-key",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "openai"
        assert body["model"] == "gpt-4o-mini"
        assert body["hasApiKey"] is True
        assert "apiKey" not in body

        get_r = client.get("/settings/llm")
        assert get_r.json()["provider"] == "openai"

    def test_put_llm_settings_empty_provider(self, client):
        r = client.put("/settings/llm", json={
            "provider": "  ",
            "model": "gpt-4o-mini",
            "apiKey": "",
        })
        assert r.status_code == 422

    def test_put_llm_settings_empty_model(self, client):
        r = client.put("/settings/llm", json={
            "provider": "openai",
            "model": "  ",
            "apiKey": "",
        })
        assert r.status_code == 422

    def test_put_llm_settings_empty_api_key(self, client):
        r = client.put("/settings/llm", json={
            "provider": "anthropic",
            "model": "claude-3",
            "apiKey": "",
        })
        assert r.status_code == 200
        assert r.json()["hasApiKey"] is False


class TestFrontendContractConsistency:
    def test_agent_response_matches_frontend_type(self, client):
        r = client.get("/agents")
        for agent in r.json():
            assert isinstance(agent["id"], str)
            assert isinstance(agent["name"], str)
            assert isinstance(agent["roleSummary"], str)
            assert isinstance(agent["styleSummary"], str)
            assert isinstance(agent["systemPrompt"], str)
            assert isinstance(agent["avatar"], str)
            assert agent["avatarImage"] is None or isinstance(agent["avatarImage"], str)
            assert agent["themeColor"] is None or isinstance(agent["themeColor"], str)
            assert agent["themeLight"] is None or isinstance(agent["themeLight"], str)
            assert agent["themeSoft"] is None or isinstance(agent["themeSoft"], str)

    def test_conversation_response_matches_frontend_type(self, client):
        r = client.get("/conversations")
        for conv in r.json():
            assert isinstance(conv["id"], str)
            assert conv["type"] in ("direct", "group")
            assert isinstance(conv["title"], str)
            assert isinstance(conv["memberIds"], list)
            assert conv["agentId"] is None or isinstance(conv["agentId"], str)
            assert isinstance(conv["createdAt"], str)
            assert isinstance(conv["updatedAt"], str)
            assert isinstance(conv["pinned"], bool)

    def test_message_response_matches_frontend_type(self, client):
        r = client.get("/messages", params={"conversationId": "direct-architect-default"})
        for msg in r.json()["items"]:
            assert isinstance(msg["id"], str)
            assert isinstance(msg["conversationId"], str)
            assert msg["senderType"] in ("user", "agent")
            assert isinstance(msg["senderId"], str)
            assert isinstance(msg["content"], str)
            assert isinstance(msg["createdAt"], str)

    def test_send_message_response_matches_frontend_type(self, client):
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "契约测试",
        })
        body = r.json()
        assert "userMessage" in body
        assert "agentMessages" in body
        assert "conversationUpdatedAt" in body
        assert isinstance(body["agentMessages"], list)
