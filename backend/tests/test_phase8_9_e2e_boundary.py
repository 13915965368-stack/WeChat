from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import seed_default_data


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "phase8_9_e2e.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock-model")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv(
        "MODEL_CONFIG_ENCRYPTION_KEY",
        "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    )
        monkeypatch.setenv(
            "MODEL_CONFIG_ENCRYPTION_KEY",
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        )
        monkeypatch.setenv(
            "MODEL_CONFIG_ENCRYPTION_KEY",
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        )
        monkeypatch.setenv(
            "MODEL_CONFIG_ENCRYPTION_KEY",
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        )
        monkeypatch.setenv(
            "MODEL_CONFIG_ENCRYPTION_KEY",
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        )
        monkeypatch.setenv(
            "MODEL_CONFIG_ENCRYPTION_KEY",
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        )
        monkeypatch.setenv(
            "MODEL_CONFIG_ENCRYPTION_KEY",
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        )

    app = create_app()
    with TestClient(app, base_url="http://testserver/api/v1") as c:
        yield c

# ===================================================================
# Phase 8: 端到端前端流程测试 (L4)
# ===================================================================


class TestPhase8BootstrapFlow:
    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_bootstrap_parallel_fetch(self, client):
        agents_r = client.get("/agents")
        conversations_r = client.get("/conversations")
        assert agents_r.status_code == 200
        assert conversations_r.status_code == 200

        agents = agents_r.json()
        conversations = conversations_r.json()

        assert len(agents) == 4, f"Expected 4 agents, got {len(agents)}"
        assert len(conversations) >= 2, f"Expected >=2 conversations, got {len(conversations)}"

    def test_bootstrap_messages_for_each_conversation(self, client):
        conversations_r = client.get("/conversations")
        conversations = conversations_r.json()

        seed_conv_ids = {"direct-architect-default", "group-product-discussion-default"}
        for conversation in conversations:
            r = client.get("/messages", params={"conversationId": conversation["id"], "limit": 100})
            assert r.status_code == 200
            body = r.json()
            assert "items" in body
            if conversation["id"] in seed_conv_ids:
                assert len(body["items"]) >= 1, f"No messages for seed conversation {conversation['id']}"

    def test_bootstrap_data_integrity(self, client):
        agents_r = client.get("/agents")
        conversations_r = client.get("/conversations")

        agents = agents_r.json()
        conversations = conversations_r.json()

        agent_ids = {a["id"] for a in agents}
        assert agent_ids == {"architect", "blank-agent", "critic", "writer"}

        conv_ids = {c["id"] for c in conversations}
        assert "group-product-discussion-default" in conv_ids
        assert "direct-architect-default" in conv_ids

        has_messages = False
        for conversation in conversations:
            r = client.get("/messages", params={"conversationId": conversation["id"]})
            if len(r.json()["items"]) > 0:
                has_messages = True
                break
        assert has_messages, "No conversation has any messages"


class TestPhase8SingleChatFlow:
    def test_create_direct_conversation_for_critic(self, client):
        r = client.post("/conversations/direct", json={"agentId": "critic"})
        assert r.status_code in (200, 201)
        body = r.json()
        assert body["type"] == "direct"
        assert body["agentId"] == "critic"
        assert body["memberIds"] == ["user", "critic"]
        self._conversation_id = body["id"]

    def test_send_message_to_critic(self, client):
        r = client.post("/conversations/direct", json={"agentId": "critic"})
        conv_id = r.json()["id"]

        msg_r = client.post("/messages", json={
            "conversationId": conv_id,
            "content": "你觉得第一版应该包含哪些功能？",
        })
        assert msg_r.status_code == 201
        body = msg_r.json()

        assert body["userMessage"]["senderType"] == "user"
        assert body["userMessage"]["content"] == "你觉得第一版应该包含哪些功能？"
        assert len(body["agentMessages"]) == 1
        assert body["agentMessages"][0]["senderId"] == "critic"
        assert body["agentMessages"][0]["senderType"] == "agent"

    def test_message_persistence_after_send(self, client):
        r = client.post("/conversations/direct", json={"agentId": "writer"})
        conv_id = r.json()["id"]

        client.post("/messages", json={
            "conversationId": conv_id,
            "content": "持久化验证消息",
        })

        r = client.get("/messages", params={"conversationId": conv_id})
        items = r.json()["items"]
        contents = [m["content"] for m in items]
        assert "持久化验证消息" in contents

        user_senders = [m for m in items if m["senderType"] == "user"]
        agent_senders = [m for m in items if m["senderType"] == "agent"]
        assert len(user_senders) >= 1
        assert len(agent_senders) >= 1


class TestPhase8GroupChatFlow:
    def test_create_group_conversation(self, client):
        r = client.post("/conversations/group", json={
            "title": "产品方案讨论",
            "memberIds": ["architect", "critic", "writer"],
        })
        assert r.status_code == 201
        body = r.json()
        assert body["type"] == "group"
        assert body["title"] == "产品方案讨论"
        assert body["memberIds"] == ["user", "architect", "critic", "writer"]
        assert body["agentId"] is None
        self._group_conv_id = body["id"]

    def test_send_group_message_three_replies(self, client):
        r = client.post("/conversations/group", json={
            "title": "请分别说说第一版重点",
            "memberIds": ["architect", "critic", "writer"],
        })
        conv_id = r.json()["id"]

        msg_r = client.post("/messages", json={
            "conversationId": conv_id,
            "content": "请分别说说第一版重点",
        })
        assert msg_r.status_code == 201
        body = msg_r.json()

        assert len(body["agentMessages"]) == 3
        sender_ids = [m["senderId"] for m in body["agentMessages"]]
        assert sender_ids == ["architect", "critic", "writer"]

    def test_group_replies_in_member_order(self, client):
        r = client.post("/conversations/group", json={
            "title": "顺序验证",
            "memberIds": ["critic", "writer", "architect"],
        })
        conv_id = r.json()["id"]

        msg_r = client.post("/messages", json={
            "conversationId": conv_id,
            "content": "请按顺序回复",
        })
        sender_ids = [m["senderId"] for m in msg_r.json()["agentMessages"]]
        assert sender_ids == ["critic", "writer", "architect"]


class TestPhase8AgentSettings:
    def test_update_agent_name_and_theme(self, client):
        r = client.put("/agents/architect", json={
            "name": "Architect Pro",
            "roleSummary": "擅长结构化拆解与系统设计",
            "styleSummary": "表达克制、偏框架化，习惯从整体到局部展开思路",
            "systemPrompt": "你是一个偏系统性与结构化思考的智能助手。",
            "avatar": "A",
            "themeColor": "#123456",
            "themeLight": "#F5E6D3",
            "themeSoft": "#FAF3EC",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Architect Pro"
        assert body["themeColor"] == "#123456"

    def test_agent_update_persists_after_get(self, client):
        update_r = client.put("/agents/architect", json={
            "name": "Architect Pro",
            "roleSummary": "擅长结构化拆解与系统设计",
            "styleSummary": "表达克制、偏框架化，习惯从整体到局部展开思路",
            "systemPrompt": "你是一个偏系统性与结构化思考的智能助手。",
            "avatar": "A",
            "themeColor": "#123456",
            "themeLight": "#F5E6D3",
            "themeSoft": "#FAF3EC",
        })
        assert update_r.status_code == 200

        r = client.get("/agents")
        agents = {a["id"]: a for a in r.json()}
        assert agents["architect"]["name"] == "Architect Pro"
        assert agents["architect"]["themeColor"] == "#123456"

    def test_seed_does_not_overwrite_update(self, client):
        update_r = client.put("/agents/architect", json={
            "name": "Architect Pro",
            "roleSummary": "擅长结构化拆解与系统设计",
            "styleSummary": "表达克制、偏框架化，习惯从整体到局部展开思路",
            "systemPrompt": "你是一个偏系统性与结构化思考的智能助手。",
            "avatar": "A",
            "themeColor": "#123456",
            "themeLight": "#F5E6D3",
            "themeSoft": "#FAF3EC",
        })
        assert update_r.status_code == 200
        with client.app.state.session_factory() as db:
            seed_default_data(db)

        r = client.get("/agents")
        agents = {a["id"]: a for a in r.json()}
        assert agents["architect"]["name"] == "Architect Pro"


class TestPhase8LLMSettings:
    def test_get_llm_settings_defaults(self, client):
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
            "apiKey": "sk-test",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "openai"
        assert body["model"] == "gpt-4o-mini"
        assert body["hasApiKey"] is True
        assert "apiKey" not in body

    def test_get_after_put_llm_settings(self, client):
        put_r = client.put("/settings/llm", json={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "apiKey": "sk-test",
        })
        assert put_r.status_code == 200

        r = client.get("/settings/llm")
        body = r.json()
        assert body["provider"] == "openai"
        assert body["model"] == "gpt-4o-mini"
        assert body["hasApiKey"] is True
        assert "apiKey" not in body

    def test_put_llm_settings_overwrite(self, client):
        r = client.put("/settings/llm", json={
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "apiKey": "sk-ant-overwrite",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "anthropic"
        assert body["model"] == "claude-3-5-sonnet"
        assert body["hasApiKey"] is True

        r = client.get("/settings/llm")
        body = r.json()
        assert body["provider"] == "anthropic"
        assert body["model"] == "claude-3-5-sonnet"
        assert body["hasApiKey"] is True


class TestPhase8MissingFeatures:
    def test_delete_conversations_now_available(self, client):
        create_r = client.post("/conversations/direct", json={"agentId": "critic"})
        conversation_id = create_r.json()["id"]

        r = client.delete(f"/conversations/{conversation_id}")
        assert r.status_code == 204

        list_r = client.get("/conversations")
        ids = [conversation["id"] for conversation in list_r.json()]
        assert conversation_id not in ids

    def test_patch_conversations_not_available(self, client):
        r = client.patch("/conversations/direct-architect-default")
        assert r.status_code in (404, 405), f"Expected 404 or 405, got {r.status_code}"

    def test_put_conversations_not_available(self, client):
        r = client.put("/conversations/direct-architect-default", json={"title": "test"})
        assert r.status_code in (404, 405), f"Expected 404 or 405, got {r.status_code}"


# ===================================================================
# Phase 9: 异常与边界条件深度测试
# ===================================================================


class TestPhase9SQLInjection:
    def test_sql_injection_drop_table(self, client):
        r = client.post("/conversations/direct", json={"agentId": "architect"})
        conv_id = r.json()["id"]

        sql_injection = "'; DROP TABLE agents; --"
        msg_r = client.post("/messages", json={
            "conversationId": conv_id,
            "content": sql_injection,
        })
        assert msg_r.status_code == 201
        body = msg_r.json()
        assert body["userMessage"]["content"] == sql_injection

        agents_r = client.get("/agents")
        assert agents_r.status_code == 200
        assert len(agents_r.json()) == 4

    def test_sql_injection_select_star(self, client):
        r = client.post("/conversations/direct", json={"agentId": "critic"})
        conv_id = r.json()["id"]

        sql_injection = "1'; SELECT * FROM users; --"
        msg_r = client.post("/messages", json={
            "conversationId": conv_id,
            "content": sql_injection,
        })
        assert msg_r.status_code == 201
        assert msg_r.json()["userMessage"]["content"] == sql_injection

    def test_sql_injection_union_select(self, client):
        r = client.post("/conversations/direct", json={"agentId": "writer"})
        conv_id = r.json()["id"]

        sql_injection = "' UNION SELECT username, password FROM users --"
        msg_r = client.post("/messages", json={
            "conversationId": conv_id,
            "content": sql_injection,
        })
        assert msg_r.status_code == 201
        assert msg_r.json()["userMessage"]["content"] == sql_injection


class TestPhase9SpecialCharacters:
    def test_html_tags_in_content(self, client):
        r = client.post("/conversations/direct", json={"agentId": "architect"})
        conv_id = r.json()["id"]

        html_content = "<script>alert(1)</script>"
        msg_r = client.post("/messages", json={
            "conversationId": conv_id,
            "content": html_content,
        })
        assert msg_r.status_code == 201
        assert msg_r.json()["userMessage"]["content"] == html_content

        verify_r = client.get("/messages", params={"conversationId": conv_id})
        contents = [m["content"] for m in verify_r.json()["items"]]
        assert html_content in contents

    def test_json_special_chars_in_content(self, client):
        r = client.post("/conversations/direct", json={"agentId": "critic"})
        conv_id = r.json()["id"]

        json_content = '{"key": "value", "nested": {"a": 1}}'
        msg_r = client.post("/messages", json={
            "conversationId": conv_id,
            "content": json_content,
        })
        assert msg_r.status_code == 201
        assert msg_r.json()["userMessage"]["content"] == json_content

    def test_emoji_in_agent_name(self, client):
        r = client.put("/agents/architect", json={
            "name": "测试🏗️",
            "roleSummary": "擅长结构化拆解与系统设计",
            "styleSummary": "表达克制、偏框架化",
            "systemPrompt": "你是一个偏系统性与结构化思考的智能助手。",
            "avatar": "测",
        })
        assert r.status_code == 200
        assert r.json()["name"] == "测试🏗️"

        r = client.get("/agents")
        agents = {a["id"]: a for a in r.json()}
        assert agents["architect"]["name"] == "测试🏗️"


class TestPhase9RapidConsecutiveSends:
    def test_rapid_five_messages(self, client):
        r = client.post("/conversations/group", json={
            "title": "快速并发测试",
            "memberIds": ["architect", "critic"],
        })
        conv_id = r.json()["id"]

        message_ids = []
        for i in range(5):
            msg_r = client.post("/messages", json={
                "conversationId": conv_id,
                "content": f"快速消息{i+1}",
            })
            assert msg_r.status_code == 201
            user_msg_id = msg_r.json()["userMessage"]["id"]
            agent_msg_ids = [m["id"] for m in msg_r.json()["agentMessages"]]
            message_ids.append(user_msg_id)
            message_ids.extend(agent_msg_ids)

        assert len(message_ids) == len(set(message_ids))

        r = client.get("/messages", params={"conversationId": conv_id, "limit": 100})
        items = r.json()["items"]
        user_messages = [m for m in items if m["senderType"] == "user"]
        assert len(user_messages) == 5

        for i in range(1, len(items)):
            assert items[i]["createdAt"] >= items[i - 1]["createdAt"]


class TestPhase9EmptyDatabase:
    @pytest.fixture
    def empty_db_path(self, tmp_path):
        db_path = tmp_path / "empty_test.db"
        return db_path.as_posix()

    def test_empty_db_get_agents_empty(self, empty_db_path, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{empty_db_path}")
        monkeypatch.setenv("APP_ENV", "test_empty")
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.setenv("LLM_MODEL", "mock-model")
        monkeypatch.setenv("LLM_API_KEY", "")
        monkeypatch.setattr("app.main.seed_default_data", lambda db: None)

        from app.main import create_app
        from app.models import Base

        app = create_app()
        Base.metadata.create_all(bind=app.state.engine)

        with TestClient(app) as c:
            r = c.get("/api/v1/agents")
            assert r.status_code == 200
            assert r.json() == []

    def test_empty_db_get_conversations_empty(self, empty_db_path, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{empty_db_path}")
        monkeypatch.setenv("APP_ENV", "test_empty")
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.setenv("LLM_MODEL", "mock-model")
        monkeypatch.setenv("LLM_API_KEY", "")
        monkeypatch.setattr("app.main.seed_default_data", lambda db: None)

        from app.main import create_app
        from app.models import Base

        app = create_app()
        Base.metadata.create_all(bind=app.state.engine)

        with TestClient(app) as c:
            r = c.get("/api/v1/conversations")
            assert r.status_code == 200
            assert r.json() == []

    def test_empty_db_get_messages_404(self, empty_db_path, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{empty_db_path}")
        monkeypatch.setenv("APP_ENV", "test_empty")
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.setenv("LLM_MODEL", "mock-model")
        monkeypatch.setenv("LLM_API_KEY", "")
        monkeypatch.setattr("app.main.seed_default_data", lambda db: None)

        from app.main import create_app
        from app.models import Base

        app = create_app()
        Base.metadata.create_all(bind=app.state.engine)

        with TestClient(app) as c:
            r = c.get("/api/v1/messages", params={"conversationId": "nonexistent"})
            assert r.status_code == 404

    def test_empty_db_send_message_404(self, empty_db_path, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{empty_db_path}")
        monkeypatch.setenv("APP_ENV", "test_empty")
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.setenv("LLM_MODEL", "mock-model")
        monkeypatch.setenv("LLM_API_KEY", "")
        monkeypatch.setattr("app.main.seed_default_data", lambda db: None)

        from app.main import create_app
        from app.models import Base

        app = create_app()
        Base.metadata.create_all(bind=app.state.engine)

        with TestClient(app) as c:
            r = c.post("/api/v1/messages", json={
                "conversationId": "nonexistent",
                "content": "hello",
            })
            assert r.status_code == 404

    def test_empty_db_create_direct_agent_not_found(self, empty_db_path, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{empty_db_path}")
        monkeypatch.setenv("APP_ENV", "test_empty")
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.setenv("LLM_MODEL", "mock-model")
        monkeypatch.setenv("LLM_API_KEY", "")
        monkeypatch.setattr("app.main.seed_default_data", lambda db: None)

        from app.main import create_app
        from app.models import Base

        app = create_app()
        Base.metadata.create_all(bind=app.state.engine)

        with TestClient(app) as c:
            r = c.post("/api/v1/conversations/direct", json={"agentId": "architect"})
            assert r.status_code == 404

    def test_empty_db_create_group_invalid_agents(self, empty_db_path, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{empty_db_path}")
        monkeypatch.setenv("APP_ENV", "test_empty")
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.setenv("LLM_MODEL", "mock-model")
        monkeypatch.setenv("LLM_API_KEY", "")
        monkeypatch.setattr("app.main.seed_default_data", lambda db: None)

        from app.main import create_app
        from app.models import Base

        app = create_app()
        Base.metadata.create_all(bind=app.state.engine)

        with TestClient(app) as c:
            r = c.post("/api/v1/conversations/group", json={
                "title": "test",
                "memberIds": ["architect", "critic"],
            })
            assert r.status_code == 422


class TestPhase9LongContentBoundary:
    def test_content_4000_chars_passes(self, client):
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "A" * 4000,
        })
        assert r.status_code == 201

    def test_content_4001_chars_rejected(self, client):
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "A" * 4001,
        })
        assert r.status_code == 422

    def test_agent_name_128_chars_passes(self, client):
        long_name = "测" * 128
        r = client.put("/agents/writer", json={
            "name": long_name,
            "roleSummary": "r",
            "styleSummary": "s",
            "systemPrompt": "p",
            "avatar": "W",
        })
        assert r.status_code == 200
        assert r.json()["name"] == long_name

    def test_content_unicode_4000_chars_passes(self, client):
        content = "好" * 4000
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": content,
        })
        assert r.status_code == 201
        assert r.json()["userMessage"]["content"] == content

    def test_content_mixed_chars_boundary(self, client):
        content = "a好🌟" * 1333 + "a"
        assert len(content) == 4000
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": content,
        })
        assert r.status_code == 201
