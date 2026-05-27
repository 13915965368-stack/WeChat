from app.seed import seed_default_data


def build_model_payload(**overrides):
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


def test_health_route_exists(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_cors_allows_localhost_and_loopback_frontend_origins(client):
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response = client.options(
            "/api/v1/agents",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_get_agents_returns_seeded_agents(client):
    response = client.get("/api/v1/agents")

    assert response.status_code == 200
    body = response.json()
    assert [agent["id"] for agent in body] == ["architect", "blank-agent", "critic", "writer"]
    assert body[0]["pinned"] is False
    assert body[1]["isTemplate"] is True
    assert body[1]["modelConfigId"] is None
    assert body[1]["modelUnavailable"] is False
    assert body[3]["roleSummary"] == "擅长表达、整理和改写"
    assert body[0]["themeColor"] == "#D4A574"
    assert body[2]["themeLight"] == "#F5DEDE"
    assert body[3]["themeSoft"] == "#F0F7F5"


def test_put_agent_updates_text_and_visual_fields(client):
    response = client.put(
        "/api/v1/agents/architect",
        json={
            "name": "Architect Pro",
            "roleSummary": "升级版结构拆解",
            "styleSummary": "更偏框架、更加克制",
            "systemPrompt": "你是升级后的 Architect。",
            "avatar": "AP",
            "avatarImage": "data:image/png;base64,abc123",
            "themeColor": "#123456",
            "themeLight": "#ABCDEF",
            "themeSoft": "#FEDCBA",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "architect",
        "name": "Architect Pro",
        "roleSummary": "升级版结构拆解",
        "styleSummary": "更偏框架、更加克制",
        "systemPrompt": "你是升级后的 Architect。",
        "avatar": "AP",
        "avatarImage": "data:image/png;base64,abc123",
        "themeColor": "#123456",
        "themeLight": "#ABCDEF",
        "themeSoft": "#FEDCBA",
        "modelConfigId": None,
        "modelUnavailable": False,
        "isTemplate": False,
        "pinned": False,
        "pinnedAt": None,
    }

    list_response = client.get("/api/v1/agents")

    assert list_response.status_code == 200
    agents = {agent["id"]: agent for agent in list_response.json()}
    assert agents["architect"]["name"] == "Architect Pro"
    assert agents["architect"]["themeColor"] == "#123456"
    assert agents["architect"]["avatarImage"] == "data:image/png;base64,abc123"


def test_post_agent_creates_new_agent_and_allows_blank_system_prompt(client):
    model_response = client.post("/api/v1/model-configs", json=build_model_payload())
    model_config_id = model_response.json()["id"]

    response = client.post(
        "/api/v1/agents",
        json={
            "name": "我的空白助手",
            "roleSummary": "无预设角色",
            "styleSummary": "自然对话",
            "systemPrompt": "",
            "avatar": "M",
            "modelConfigId": model_config_id,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("agent-")
    assert body["name"] == "我的空白助手"
    assert body["systemPrompt"] == ""
    assert body["modelConfigId"] == model_config_id
    assert body["modelUnavailable"] is False
    assert body["isTemplate"] is False


def test_patch_agent_model_binding_supports_bind_failed_model_and_unbind(client):
    create_agent_response = client.post(
        "/api/v1/agents",
        json={
            "name": "待绑定助手",
            "roleSummary": "测试绑定模型",
            "styleSummary": "简洁",
            "systemPrompt": "你负责测试。",
            "avatar": "T",
        },
    )
    agent_id = create_agent_response.json()["id"]

    model_response = client.post("/api/v1/model-configs", json=build_model_payload())
    model_config_id = model_response.json()["id"]
    fail_response = client.patch(
        f"/api/v1/model-configs/{model_config_id}",
        json={"baseUrl": "   "},
    )
    assert fail_response.status_code == 200
    assert fail_response.json()["status"] == "failed"

    bind_response = client.patch(
        f"/api/v1/agents/{agent_id}/model",
        json={"modelConfigId": model_config_id},
    )

    assert bind_response.status_code == 200
    assert bind_response.json()["modelConfigId"] == model_config_id
    assert bind_response.json()["modelUnavailable"] is True

    unbind_response = client.patch(
        f"/api/v1/agents/{agent_id}/model",
        json={"modelConfigId": None},
    )

    assert unbind_response.status_code == 200
    assert unbind_response.json()["modelConfigId"] is None
    assert unbind_response.json()["modelUnavailable"] is False


def test_delete_agent_removes_direct_and_prunes_group_without_deleting_history(client):
    create_agent_response = client.post(
        "/api/v1/agents",
        json={
            "name": "临时助手",
            "roleSummary": "用于删除语义测试",
            "styleSummary": "简洁",
            "systemPrompt": "你负责参与测试。",
            "avatar": "X",
        },
    )
    agent_id = create_agent_response.json()["id"]

    direct_response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": agent_id, "title": "待删除单聊"},
    )
    group_response = client.post(
        "/api/v1/conversations/group",
        json={"title": "保留历史群聊", "memberIds": [agent_id, "critic"]},
    )
    group_id = group_response.json()["id"]
    message_response = client.post(
        "/api/v1/messages",
        json={"conversationId": group_id, "content": "保留这段历史"},
    )
    direct_id = direct_response.json()["id"]

    assert direct_response.status_code == 201
    assert group_response.status_code == 201
    assert message_response.status_code == 201

    delete_response = client.delete(f"/api/v1/agents/{agent_id}")

    assert delete_response.status_code == 204

    agents_response = client.get("/api/v1/agents")
    assert agent_id not in {agent["id"] for agent in agents_response.json()}

    direct_messages_response = client.get("/api/v1/messages", params={"conversationId": direct_id})
    assert direct_messages_response.status_code == 404

    conversations_response = client.get("/api/v1/conversations")
    conversations = {conversation["id"]: conversation for conversation in conversations_response.json()}
    assert direct_id not in conversations
    assert group_id in conversations
    assert conversations[group_id]["memberIds"] == ["user", "critic"]
    assert conversations[group_id]["isDisabled"] is False

    group_messages_response = client.get("/api/v1/messages", params={"conversationId": group_id})
    assert group_messages_response.status_code == 200
    group_messages = group_messages_response.json()["items"]
    assert any(message["senderId"] == agent_id for message in group_messages)


def test_patch_agent_pin_updates_sorting_and_fields(client):
    first_response = client.patch("/api/v1/agents/critic/pin", json={"pinned": True})
    second_response = client.patch("/api/v1/agents/writer/pin", json={"pinned": True})

    assert first_response.status_code == 200
    assert first_response.json()["pinned"] is True
    assert first_response.json()["pinnedAt"] is not None
    assert second_response.status_code == 200
    assert second_response.json()["pinned"] is True

    list_response = client.get("/api/v1/agents")

    assert list_response.status_code == 200
    ids = [agent["id"] for agent in list_response.json()]
    assert ids[:2] == ["writer", "critic"]


def test_patch_agent_pin_false_clears_pin_state(client):
    client.patch("/api/v1/agents/critic/pin", json={"pinned": True})

    response = client.patch("/api/v1/agents/critic/pin", json={"pinned": False})

    assert response.status_code == 200
    assert response.json()["pinned"] is False
    assert response.json()["pinnedAt"] is None


def test_seed_does_not_overwrite_existing_agent_customizations(client):
    update_response = client.put(
        "/api/v1/agents/architect",
        json={
            "name": "Architect Custom",
            "roleSummary": "保留原有能力，但允许用户自定义",
            "styleSummary": "更偏个性化输出",
            "systemPrompt": "你应该保留用户配置。",
            "avatar": "ZQ",
            "avatarImage": None,
            "themeColor": "#654321",
            "themeLight": "#765432",
            "themeSoft": "#876543",
        },
    )

    assert update_response.status_code == 200

    with client.app.state.session_factory() as db:
        seed_default_data(db)

    list_response = client.get("/api/v1/agents")

    assert list_response.status_code == 200
    agents = {agent["id"]: agent for agent in list_response.json()}
    assert agents["architect"]["name"] == "Architect Custom"
    assert agents["architect"]["avatar"] == "ZQ"
    assert agents["architect"]["themeColor"] == "#654321"
    assert agents["architect"]["themeLight"] == "#765432"
    assert agents["architect"]["themeSoft"] == "#876543"


def test_delete_seed_agent_is_forbidden(client):
    response = client.delete("/api/v1/agents/architect")

    assert response.status_code == 403
    assert response.json() == {
        "error": {"code": "agent_protected", "message": "Seed agents cannot be deleted"}
    }


def test_put_agent_returns_not_found_when_agent_missing(client):
    response = client.put(
        "/api/v1/agents/missing-agent",
        json={
            "name": "Missing",
            "roleSummary": "x",
            "styleSummary": "y",
            "systemPrompt": "z",
            "avatar": "M",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "agent_not_found", "message": "Agent not found"}
    }


def test_patch_agent_pin_returns_not_found_when_agent_missing(client):
    response = client.patch("/api/v1/agents/missing-agent/pin", json={"pinned": True})

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "agent_not_found", "message": "Agent not found"}
    }


def test_patch_agent_model_returns_not_found_when_model_missing(client):
    response = client.patch("/api/v1/agents/architect/model", json={"modelConfigId": "missing-model"})

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "model_config_not_found", "message": "Model config not found"}
    }


def test_delete_agent_returns_not_found_when_agent_missing(client):
    response = client.delete("/api/v1/agents/missing-agent")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "agent_not_found", "message": "Agent not found"}
    }
