from sqlalchemy import select

from app.models import Conversation, ConversationMember, Message


def test_get_conversations_returns_seeded_conversations_sorted(client):
    response = client.get("/api/v1/conversations")

    assert response.status_code == 200
    body = response.json()
    assert [conversation["id"] for conversation in body] == [
        "group-product-discussion-default",
        "direct-architect-default",
    ]
    assert body[0]["pinned"] is True
    assert body[0]["pinnedAt"] == "2026-05-10T09:40:00.000Z"
    assert body[0]["modelConfigId"] is None
    assert body[1]["memberIds"] == ["user", "architect"]


def test_create_direct_conversation_returns_new_conversation(client):
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
                "supportsImageInput": True,
                "supportsFileInput": False,
                "supportsStreaming": True,
                "contextWindow": 128000,
            },
        },
    )
    model_config_id = model_config_response.json()["id"]

    response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": "critic", "title": "与 Critic 的新对话", "modelConfigId": model_config_id},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "direct"
    assert body["agentId"] == "critic"
    assert body["modelConfigId"] == model_config_id
    assert body["memberIds"] == ["user", "critic"]
    assert len(body["id"]) == 32


def test_create_direct_conversation_reuses_existing_record_and_updates_session_model(client):
    first_model_response = client.post(
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
                "supportsImageInput": True,
                "supportsFileInput": False,
                "supportsStreaming": True,
                "contextWindow": 128000,
            },
        },
    )
    second_model_response = client.post(
        "/api/v1/model-configs",
        json={
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "displayName": "OpenAI - GPT-4.1 Mini",
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
        },
    )
    first_model_id = first_model_response.json()["id"]
    second_model_id = second_model_response.json()["id"]

    first_response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": "architect", "modelConfigId": first_model_id},
    )
    second_response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": "architect", "modelConfigId": second_model_id, "title": "新的会话标题"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["id"] == "direct-architect-default"
    assert second_response.json()["id"] == "direct-architect-default"
    assert second_response.json()["modelConfigId"] == second_model_id
    assert second_response.json()["title"] == "新的会话标题"

    conversations = client.get("/api/v1/conversations").json()
    direct_conversation = next(item for item in conversations if item["id"] == "direct-architect-default")
    assert direct_conversation["modelConfigId"] == second_model_id
    assert direct_conversation["title"] == "新的会话标题"


def test_create_group_conversation_adds_user_and_preserves_members(client):
    response = client.post(
        "/api/v1/conversations/group",
        json={
            "title": "产品方案讨论",
            "memberIds": ["architect", "critic", "writer"],
            "includeContext": True,
            "contextRounds": 10,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "group"
    assert body["memberIds"] == ["user", "architect", "critic", "writer"]
    assert body["pinned"] is False
    assert body["pinnedAt"] is None
    assert body["runtimeMetadata"]["group_runtime"]["protocol"] == {
        "version": "group_runtime_v1",
        "mode": "fixed_group_chat",
        "thread_id": "default",
        "scope": "conversation_default_thread",
    }
    assert body["runtimeMetadata"]["group_runtime"]["default_thread"]["moderator_note"] == {
        "status": "pending",
        "content": None,
        "generated_by_agent_id": None,
        "generated_at": None,
        "input": None,
    }


def test_create_group_conversation_persists_source_and_copies_recent_rounds(client):
    direct_send = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "先把最近一轮直聊补出来",
        },
    )
    assert direct_send.status_code == 201

    response = client.post(
        "/api/v1/conversations/group",
        json={
            "title": "从直聊扩展出来的群聊",
            "memberIds": ["architect", "critic"],
            "sourceConversationId": "direct-architect-default",
            "includeContext": True,
            "contextRounds": 1,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["sourceConversationId"] == "direct-architect-default"
    assert body["memberIds"] == ["user", "architect", "critic"]

    messages_response = client.get(
        "/api/v1/messages",
        params={"conversationId": body["id"], "limit": 20, "offset": 0},
    )
    assert messages_response.status_code == 200
    copied_items = messages_response.json()["items"]
    assert [item["senderType"] for item in copied_items] == ["user", "agent"]
    assert [item["content"] for item in copied_items] == [
        "先把最近一轮直聊补出来",
        direct_send.json()["agentMessages"][0]["content"],
    ]

    conversations_response = client.get("/api/v1/conversations")
    created_conversation = next(item for item in conversations_response.json() if item["id"] == body["id"])
    assert created_conversation["sourceConversationId"] == "direct-architect-default"

    with client.app.state.session_factory() as db:
        created = db.get(Conversation, body["id"])
        assert created.source_conversation_id == "direct-architect-default"
        persisted_messages = db.scalars(
            select(Message)
            .where(Message.conversation_id == body["id"])
            .order_by(Message.created_at.asc())
        ).all()
        assert [message.sender_type for message in persisted_messages] == ["user", "agent"]


def test_create_group_conversation_rejects_non_direct_source_conversation(client):
    response = client.post(
        "/api/v1/conversations/group",
        json={
            "title": "来源校验",
            "memberIds": ["architect", "critic"],
            "sourceConversationId": "group-product-discussion-default",
            "includeContext": True,
            "contextRounds": 1,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "sourceConversationId must reference a direct conversation",
        }
    }


def test_create_direct_conversation_returns_agent_not_found(client):
    response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": "missing-agent", "title": "测试"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "agent_not_found", "message": "Agent not found"}
    }


def test_create_direct_conversation_returns_model_config_not_found(client):
    response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": "architect", "modelConfigId": "missing-model"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "model_config_not_found", "message": "Model config not found"}
    }


def test_create_group_conversation_rejects_invalid_members(client):
    response = client.post(
        "/api/v1/conversations/group",
        json={"title": "测试", "memberIds": ["architect"]},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "memberIds must contain at least two unique agent ids",
        }
    }


def test_create_group_conversation_rejects_blank_title(client):
    response = client.post(
        "/api/v1/conversations/group",
        json={"title": "   ", "memberIds": ["architect", "critic"]},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "message": "title cannot be empty"}
    }


def test_patch_conversation_pin_sets_pinned_at_and_resorts(client):
    create_response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": "critic", "title": "与 Critic 的新对话"},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/conversations/{conversation_id}/pin",
        json={"pinned": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pinned"] is True
    assert body["pinnedAt"] is not None

    list_response = client.get("/api/v1/conversations")
    ids = [conversation["id"] for conversation in list_response.json()]
    assert ids[0] == conversation_id
    assert ids[1] == "group-product-discussion-default"


def test_patch_conversation_pin_false_clears_pinned_at(client):
    response = client.patch(
        "/api/v1/conversations/group-product-discussion-default/pin",
        json={"pinned": False},
    )

    assert response.status_code == 200
    assert response.json()["pinned"] is False
    assert response.json()["pinnedAt"] is None


def test_patch_conversation_pin_returns_not_found(client):
    response = client.patch(
        "/api/v1/conversations/missing-conversation/pin",
        json={"pinned": True},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "conversation_not_found", "message": "Conversation not found"}
    }


def test_delete_conversation_removes_messages_and_members(client):
    create_response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": "critic", "title": "待删除单聊"},
    )
    conversation_id = create_response.json()["id"]

    message_response = client.post(
        "/api/v1/messages",
        json={"conversationId": conversation_id, "content": "测试删除"},
    )
    assert message_response.status_code == 201

    delete_response = client.delete(f"/api/v1/conversations/{conversation_id}")

    assert delete_response.status_code == 204
    with client.app.state.session_factory() as db:
        assert db.get(Conversation, conversation_id) is None
        assert db.scalars(
            select(ConversationMember).where(ConversationMember.conversation_id == conversation_id)
        ).all() == []
        assert db.scalars(
            select(Message).where(Message.conversation_id == conversation_id)
        ).all() == []


def test_delete_conversation_returns_not_found(client):
    response = client.delete("/api/v1/conversations/missing-conversation")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "conversation_not_found", "message": "Conversation not found"}
    }


def test_bulk_delete_conversations_deletes_multiple_records(client):
    direct_response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": "critic", "title": "待批量删除单聊"},
    )
    group_response = client.post(
        "/api/v1/conversations/group",
        json={"title": "待批量删除群聊", "memberIds": ["architect", "writer"]},
    )
    direct_id = direct_response.json()["id"]
    group_id = group_response.json()["id"]

    response = client.post(
        "/api/v1/conversations/bulk-delete",
        json={"conversationIds": [direct_id, group_id]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["deletedCount"] == 2
    assert direct_id not in body["remainingConversationIds"]
    assert group_id not in body["remainingConversationIds"]

    list_response = client.get("/api/v1/conversations")
    remaining_ids = {conversation["id"] for conversation in list_response.json()}
    assert direct_id not in remaining_ids
    assert group_id not in remaining_ids


def test_bulk_delete_conversations_rejects_empty_ids(client):
    response = client.post("/api/v1/conversations/bulk-delete", json={"conversationIds": []})

    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "message": "conversationIds cannot be empty"}
    }


def test_bulk_delete_conversations_returns_not_found_for_missing_id(client):
    response = client.post(
        "/api/v1/conversations/bulk-delete",
        json={"conversationIds": ["group-product-discussion-default", "missing-conversation"]},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "conversation_not_found", "message": "Conversation not found"}
    }
