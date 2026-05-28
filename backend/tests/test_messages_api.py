import json
import httpx
from types import SimpleNamespace

from app.routes import messages as messages_route
from app.schemas import MessageStreamRuntimeHooks
from app.llm.validator import LLMStreamInterruptedError
from app.services import chat_service


def _install_group_runtime_fake_client(monkeypatch, captured_requests, public_replies):
    class FakeClient:
        def chat(self, request):
            captured_requests.append(
                {
                    "agent_id": request.agent_id,
                    "messages": [(message.role, message.content) for message in request.messages],
                    "metadata": dict(request.metadata),
                }
            )
            if request.metadata.get("purpose") == "group_moderator_note":
                return SimpleNamespace(content="先由前序成员拆骨架，后续成员按顺位补充，不要复述转录稿。")
            return SimpleNamespace(content=public_replies[request.agent_id])

    monkeypatch.setattr(chat_service, "create_client", lambda _config: FakeClient())
    monkeypatch.setattr(
        chat_service,
        "run_with_endpoint_fallback",
        lambda adapter_config, callback: callback(adapter_config),
    )


def _find_identity_message(public_request):
    return next(
        content
        for role, content in public_request["messages"]
        if role == "system" and "当前公开回复身份说明" in content
    )


def _parse_sse_events(raw_text):
    events = []
    for block in raw_text.split("\n\n"):
        normalized_block = block.strip()
        if not normalized_block:
            continue
        event_name = None
        data_lines = []
        for line in normalized_block.splitlines():
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())
        if event_name is None or not data_lines:
            continue
        events.append({"event": event_name, "data": json.loads("\n".join(data_lines))})
    return events


def test_get_messages_returns_paginated_items(client):
    response = client.get(
        "/api/v1/messages",
        params={"conversationId": "direct-architect-default", "limit": 20, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["hasMore"] is False
    assert body["items"][0]["senderId"] == "architect"
    assert body["items"][0]["attachments"] == []


def test_get_messages_returns_conversation_not_found(client):
    response = client.get(
        "/api/v1/messages",
        params={"conversationId": "missing-conversation", "limit": 20, "offset": 0},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "conversation_not_found", "message": "Conversation not found"}
    }


def test_post_message_in_direct_conversation_returns_single_agent_reply(client):
    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "你觉得第一版应该包含哪些功能？",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["userMessage"]["senderId"] == "user"
    assert body["userMessage"]["attachments"] == []
    assert len(body["agentMessages"]) == 1
    assert body["agentMessages"][0]["senderId"] == "architect"
    assert body["agentMessages"][0]["attachments"] == []
    assert body["conversationUpdatedAt"] == body["agentMessages"][0]["createdAt"]


def test_post_message_in_direct_conversation_reflects_system_prompt_and_history_in_mock_reply(client):
    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "继续往下拆解这个问题",
        },
    )

    assert response.status_code == 201
    reply_content = response.json()["agentMessages"][0]["content"]
    assert "已参考系统提示词" in reply_content
    assert "已参考1条历史消息" in reply_content


def test_post_message_persists_user_attachments_and_returns_them(client):
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

    bind_response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": "architect", "modelConfigId": model_config_id},
    )
    assert bind_response.status_code == 200

    attachments = [
        {
            "attachmentId": "att-image-1",
            "kind": "image",
            "mimeType": "image/png",
            "name": "wireframe.png",
            "size": 2048,
            "previewUrl": "https://example.com/wireframe.png",
            "expiresAt": "2026-06-01T00:00:00.000Z",
            "metadata": {"width": 1280, "height": 720},
        }
    ]

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "请结合这张草图给建议",
            "attachments": attachments,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["userMessage"]["attachments"] == attachments
    assert body["agentMessages"][0]["attachments"] == []

    messages_response = client.get(
        "/api/v1/messages",
        params={"conversationId": "direct-architect-default", "limit": 20, "offset": 0},
    )
    assert messages_response.status_code == 200
    assert messages_response.json()["items"][-2]["attachments"] == attachments
    assert messages_response.json()["items"][-1]["attachments"] == []


def test_post_message_maps_unsupported_image_capability_to_uniform_api_error(client):
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

    attachments = [
        {
            "attachmentId": "att-image-unsupported",
            "kind": "image",
            "mimeType": "image/png",
            "name": "wireframe.png",
            "size": 2048,
            "previewUrl": "https://example.com/wireframe.png",
            "expiresAt": "2026-06-01T00:00:00.000Z",
            "metadata": {"width": 1280, "height": 720},
        }
    ]

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "请结合这张草图给建议",
            "attachments": attachments,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "IMAGE_NOT_SUPPORTED",
            "message": "image attachments are not supported by the current model",
        }
    }


def test_post_message_maps_remote_unsupported_image_provider_error_to_uniform_api_error(
    client,
    monkeypatch,
):
    class FakeStreamResponse:
        def __init__(self, url_text: str) -> None:
            self.status_code = 400
            self.headers = {"content-type": "text/event-stream"}
            self.text = ""
            self.request = httpx.Request("POST", url_text)

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError(
                "stream request failed",
                request=self.request,
                response=httpx.Response(
                    400,
                    json={
                        "error": {
                            "message": "Invalid content type. image_url is only supported by certain models.",
                            "code": "unsupported_content_type",
                        }
                    },
                    request=self.request,
                ),
            )

        def iter_lines(self):
            return iter(())

    class FakeStreamContext:
        def __init__(self, url_text: str) -> None:
            self.response = FakeStreamResponse(url_text)

        def __enter__(self):
            return self.response

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def fake_stream(method, url, *args, **kwargs):
        return FakeStreamContext(str(url))

    monkeypatch.setattr(httpx, "stream", fake_stream)

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

    bind_response = client.post(
        "/api/v1/conversations/direct",
        json={"agentId": "architect", "modelConfigId": model_config_id},
    )
    assert bind_response.status_code == 200

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "请结合这张草图给建议",
            "attachments": [
                {
                    "attachmentId": "att-image-remote-unsupported",
                    "kind": "image",
                    "mimeType": "image/png",
                    "name": "wireframe.png",
                    "size": 2048,
                    "previewUrl": "https://example.com/wireframe.png",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "IMAGE_NOT_SUPPORTED",
            "message": "image attachments are not supported by the current model",
        }
    }


def test_post_message_maps_stream_interrupted_to_uniform_api_error(client, monkeypatch):
    def fake_send_message(db, conversation, content, attachments=None):
        raise LLMStreamInterruptedError("openai-compatible stream interrupted: peer closed connection")

    monkeypatch.setattr(messages_route, "send_message", fake_send_message)

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "帮我看一下最近王鹤棣的事情",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "model_stream_interrupted",
            "message": "openai-compatible stream interrupted: peer closed connection",
        }
    }


def test_post_message_in_blank_conversation_uses_conversation_level_model_binding(client):
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

    create_conversation_response = client.post(
        "/api/v1/conversations/direct",
        json={
            "agentId": "blank-agent",
            "title": "空白对话",
            "modelConfigId": model_config_id,
        },
    )
    assert create_conversation_response.status_code == 201
    conversation = create_conversation_response.json()
    assert conversation["agentId"] == "blank-agent"
    assert conversation["modelConfigId"] == model_config_id

    send_response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": conversation["id"],
            "content": "这是一条空白对话测试消息",
        },
    )
    assert send_response.status_code == 201
    body = send_response.json()
    assert body["userMessage"]["senderId"] == "user"
    assert body["agentMessages"][0]["senderId"] == "blank-agent"
    assert body["conversationUpdatedAt"] == body["agentMessages"][0]["createdAt"]

    list_response = client.get("/api/v1/messages", params={"conversationId": conversation["id"]})
    assert list_response.status_code == 200
    assert [item["content"] for item in list_response.json()["items"]][-2:] == [
        "这是一条空白对话测试消息",
        body["agentMessages"][0]["content"],
    ]

    agents_response = client.get("/api/v1/agents")
    blank_agent = next(agent for agent in agents_response.json() if agent["id"] == "blank-agent")
    assert blank_agent["modelConfigId"] is None


def test_post_message_in_group_conversation_returns_multiple_agent_replies(client):
    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "group-product-discussion-default",
            "content": "我们来讨论一下第一版产品的核心功能吧。",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert [message["senderId"] for message in body["agentMessages"]] == [
        "architect",
        "critic",
        "writer",
    ]
    assert len(body["agentMessages"]) == 3
    assert body["warnings"] == []


def test_post_message_in_group_conversation_keeps_following_members_when_one_fails(client, monkeypatch):
    def fake_generate_agent_reply(
        db,
        conversation,
        agent,
        content,
        attachments=None,
        history_messages=None,
        round_messages=None,
        member_summary=None,
        replied_agent_ids=None,
    ):
        if agent.id == "critic":
            raise ValueError("critic request failed")
        return f"{agent.id} safe reply"

    monkeypatch.setattr(chat_service, "generate_agent_reply", fake_generate_agent_reply)

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "group-product-discussion-default",
            "content": "请继续接力，但第二位会失败。",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert [message["senderId"] for message in body["agentMessages"]] == [
        "architect",
        "writer",
    ]
    assert body["warnings"] == [
        {
            "code": "model_request_failed",
            "message": "Critic 回复失败：critic request failed",
        }
    ]

    messages_response = client.get(
        "/api/v1/messages",
        params={"conversationId": "group-product-discussion-default"},
    )
    items = messages_response.json()["items"]
    assert [item["content"] for item in items][-3:] == [
        "请继续接力，但第二位会失败。",
        "architect safe reply",
        "writer safe reply",
    ]


def test_post_message_in_group_conversation_continues_when_moderator_note_fails(client, monkeypatch):
    def fake_generate_group_moderator_note(
        db,
        conversation,
        agent,
        content,
        member_summary,
        history_messages=None,
        event_window=None,
    ):
        raise ValueError("moderator note failed")

    def fake_generate_agent_reply(
        db,
        conversation,
        agent,
        content,
        attachments=None,
        history_messages=None,
        round_messages=None,
        member_summary=None,
        replied_agent_ids=None,
    ):
        return f"{agent.id} safe reply"

    monkeypatch.setattr(
        chat_service,
        "generate_group_moderator_note",
        fake_generate_group_moderator_note,
    )
    monkeypatch.setattr(chat_service, "generate_agent_reply", fake_generate_agent_reply)

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "group-product-discussion-default",
            "content": "主持说明失败后也继续。",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert [message["senderId"] for message in body["agentMessages"]] == [
        "architect",
        "critic",
        "writer",
    ]
    assert body["warnings"] == [
        {
            "code": "model_request_failed",
            "message": "群聊主持说明生成失败：moderator note failed",
        }
    ]


def test_post_message_in_group_conversation_passes_previous_agent_reply_to_next_agent(client, monkeypatch):
    contexts_by_agent = {}

    def fake_generate_agent_reply(
        db,
        conversation,
        agent,
        content,
        attachments=None,
        history_messages=None,
        event_window=None,
        dispatch_state=None,
    ):
        contexts_by_agent[agent.id] = {
            "history": [message.content for message in history_messages or []],
            "event_window": [dict(event) for event in event_window or []],
            "dispatch_state": dict(dispatch_state or {}),
        }
        return f"{agent.id} reply"

    monkeypatch.setattr(chat_service, "generate_agent_reply", fake_generate_agent_reply)

    create_response = client.post(
        "/api/v1/conversations/group",
        json={
            "title": "接力讨论",
            "memberIds": ["architect", "critic", "writer"],
        },
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": conversation_id,
            "content": "请开始接力讨论",
        },
    )

    assert response.status_code == 201
    assert contexts_by_agent["architect"]["history"] == []
    assert [event["event_type"] for event in contexts_by_agent["architect"]["event_window"]] == [
        "user_message"
    ]
    assert contexts_by_agent["architect"]["event_window"][0]["content"] == "请开始接力讨论"
    assert contexts_by_agent["critic"]["history"] == []
    assert [event["event_type"] for event in contexts_by_agent["critic"]["event_window"]] == [
        "user_message",
        "agent_message",
    ]
    assert contexts_by_agent["critic"]["event_window"][0]["content"] == "请开始接力讨论"
    assert contexts_by_agent["critic"]["event_window"][1]["speaker_name"] == "Architect"
    assert contexts_by_agent["critic"]["event_window"][1]["content"] == "architect reply"
    assert contexts_by_agent["writer"]["history"] == []
    assert [event["event_type"] for event in contexts_by_agent["writer"]["event_window"]] == [
        "user_message",
        "agent_message",
        "agent_message",
    ]
    assert contexts_by_agent["writer"]["event_window"][0]["content"] == "请开始接力讨论"
    assert contexts_by_agent["writer"]["event_window"][1]["speaker_name"] == "Architect"
    assert contexts_by_agent["writer"]["event_window"][1]["content"] == "architect reply"
    assert contexts_by_agent["writer"]["event_window"][2]["speaker_name"] == "Critic"
    assert contexts_by_agent["writer"]["event_window"][2]["content"] == "critic reply"
    assert [message["content"] for message in response.json()["agentMessages"]] == [
        "architect reply",
        "critic reply",
        "writer reply",
    ]


def test_post_message_in_group_conversation_formats_copied_history_as_group_transcript(client, monkeypatch):
    contexts_by_agent = {}

    def fake_generate_agent_reply(
        db,
        conversation,
        agent,
        content,
        attachments=None,
        history_messages=None,
        event_window=None,
        dispatch_state=None,
    ):
        contexts_by_agent[agent.id] = {
            "history": [message.content for message in history_messages or []],
            "event_window": [dict(event) for event in event_window or []],
            "dispatch_state": dict(dispatch_state or {}),
        }
        return f"{agent.id} reply"

    monkeypatch.setattr(chat_service, "generate_agent_reply", fake_generate_agent_reply)

    direct_send = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "先把最近一轮直聊补出来",
        },
    )
    assert direct_send.status_code == 201

    create_response = client.post(
        "/api/v1/conversations/group",
        json={
            "title": "从直聊扩展出来的群聊",
            "memberIds": ["architect", "critic"],
            "sourceConversationId": "direct-architect-default",
            "includeContext": True,
            "contextRounds": 1,
        },
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": conversation_id,
            "content": "群里继续",
        },
    )

    assert response.status_code == 201
    assert [event["event_type"] for event in contexts_by_agent["architect"]["event_window"]] == [
        "user_message"
    ]
    assert contexts_by_agent["architect"]["event_window"][0]["content"] == "群里继续"
    assert "speaker_name=用户" in contexts_by_agent["architect"]["history"][0]
    assert "content=先把最近一轮直聊补出来" in contexts_by_agent["architect"]["history"][0]
    assert "speaker_name=Architect" in contexts_by_agent["architect"]["history"][1]
    assert (
        f"content={direct_send.json()['agentMessages'][0]['content']}"
        in contexts_by_agent["architect"]["history"][1]
    )


def test_post_message_in_group_conversation_injects_protocol_and_persists_moderator_note(client, monkeypatch):
    captured_requests = []

    class FakeClient:
        def chat(self, request):
            captured_requests.append(
                {
                    "agent_id": request.agent_id,
                    "messages": [(message.role, message.content) for message in request.messages],
                    "metadata": dict(request.metadata),
                }
            )
            if request.metadata.get("purpose") == "group_moderator_note":
                return SimpleNamespace(content="先由 1 号位拆解任务，后续成员按顺序补充，不要重复转录稿。")
            return SimpleNamespace(content=f"{request.agent_id} reply")

    monkeypatch.setattr(chat_service, "create_client", lambda _config: FakeClient())
    monkeypatch.setattr(
        chat_service,
        "run_with_endpoint_fallback",
        lambda adapter_config, callback: callback(adapter_config),
    )

    create_response = client.post(
        "/api/v1/conversations/group",
        json={
            "title": "协议化接力讨论",
            "memberIds": ["architect", "critic", "writer"],
        },
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": conversation_id,
            "content": "请你们按顺序接力完成方案拆解",
        },
    )
    assert response.status_code == 201

    moderator_request = captured_requests[0]
    assert moderator_request["metadata"]["purpose"] == "group_moderator_note"
    assert "当前用户输入：请你们按顺序接力完成方案拆解" in moderator_request["messages"][-1][1]
    assert "成员数量：3" in moderator_request["messages"][-1][1]
    assert "1. Architect (architect)" in moderator_request["messages"][-1][1]
    assert "2. Critic (critic)" in moderator_request["messages"][-1][1]
    assert "3. Writer (writer)" in moderator_request["messages"][-1][1]

    public_requests = captured_requests[1:]
    assert [item["agent_id"] for item in public_requests] == ["architect", "critic", "writer"]
    for public_request in public_requests:
        roles = [role for role, _ in public_request["messages"]]
        system_messages = [content for role, content in public_request["messages"] if role == "system"]
        assert roles[-1] == "user"
        assert all(role == "system" for role in roles[:-1])
        assert any("固定顺序的群聊接力" in content for content in system_messages)
        assert any("群聊内部主持说明" in content for content in system_messages)
        assert public_request["metadata"]["group_protocol_version"] == "group_runtime_v1"
        assert public_request["metadata"]["moderator_note_present"] is True
        assert public_request["metadata"]["dispatch_strategy"] == "broadcast_chain"
        assert public_request["metadata"]["trigger_event_type"] == "user_message"
        assert public_request["metadata"]["reserved_event_types"] == [
            "user_message",
            "moderator_note_ready",
            "agent_message",
            "conversation_updated",
            "done",
            "error",
        ]
        assert public_request["metadata"]["reserved_dispatch_strategies"] == ["broadcast_chain"]
        assert public_request["metadata"]["reserved_future_event_types"] == [
            "agent_thinking",
            "tool_call",
            "tool_result",
            "dispatch_progress",
        ]
        assert public_request["metadata"]["reserved_future_dispatch_strategies"] == [
            "round_robin",
            "parallel_fan_out",
            "manual_handoff",
        ]
        assert any("当前群聊运行段信息" in content for content in system_messages)

    with client.app.state.session_factory() as db:
        conversation = db.get(chat_service.Conversation, conversation_id)
        default_thread = conversation.runtime_metadata["group_runtime"]["default_thread"]
        moderator_note = default_thread["moderator_note"]
        event_window = default_thread["event_window"]
        dispatch_state = default_thread["dispatch_state"]
        assert moderator_note["content"] == "先由 1 号位拆解任务，后续成员按顺序补充，不要重复转录稿。"
        assert moderator_note["generated_by_agent_id"] == "architect"
        assert moderator_note["input"]["member_count"] == 3
        assert moderator_note["input"]["has_source_context"] is False
        assert moderator_note["input"]["transcript"] == ["请你们按顺序接力完成方案拆解"]
        assert event_window["version"] == "group_event_window_v1"
        assert [event["event_type"] for event in event_window["events"]] == [
            "user_message",
            "agent_message",
            "agent_message",
            "agent_message",
        ]
        assert event_window["last_event_type"] == "agent_message"
        assert dispatch_state == {
            "status": "completed",
            "strategy": "broadcast_chain",
            "trigger_event_id": event_window["events"][0]["event_id"],
            "cursor": 3,
            "pending_member_ids": [],
            "completed_member_ids": ["architect", "critic", "writer"],
            "failed_member_ids": [],
            "last_completed_event_id": event_window["events"][-1]["event_id"],
        }

    messages_response = client.get("/api/v1/messages", params={"conversationId": conversation_id})
    items = messages_response.json()["items"]
    assert [item["senderType"] for item in items] == ["user", "agent", "agent", "agent"]
    assert all("主持说明" not in item["content"] for item in items)


def test_post_message_in_group_conversation_generates_moderator_note_only_once(client, monkeypatch):
    call_counts = {"moderator": 0, "public": 0}

    class FakeClient:
        def chat(self, request):
            if request.metadata.get("purpose") == "group_moderator_note":
                call_counts["moderator"] += 1
                return SimpleNamespace(content="请按既定顺序接力，不要重复。")
            call_counts["public"] += 1
            return SimpleNamespace(content=f"{request.agent_id} reply")

    monkeypatch.setattr(chat_service, "create_client", lambda _config: FakeClient())
    monkeypatch.setattr(
        chat_service,
        "run_with_endpoint_fallback",
        lambda adapter_config, callback: callback(adapter_config),
    )

    create_response = client.post(
        "/api/v1/conversations/group",
        json={
            "title": "一次性主持说明",
            "memberIds": ["architect", "critic"],
        },
    )
    conversation_id = create_response.json()["id"]

    first_response = client.post(
        "/api/v1/messages",
        json={"conversationId": conversation_id, "content": "第一轮任务"},
    )
    second_response = client.post(
        "/api/v1/messages",
        json={"conversationId": conversation_id, "content": "第二轮任务"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert call_counts == {"moderator": 1, "public": 4}


def test_post_message_in_group_conversation_injects_identity_order_and_self_intro_constraints(client, monkeypatch):
    captured_requests = []
    _install_group_runtime_fake_client(
        monkeypatch,
        captured_requests,
        public_replies={
            "architect": "Architect：我是 Architect，负责结构化拆解。",
            "critic": "Critic：我是 Critic，负责找风险和边界。",
            "writer": "Writer：我是 Writer，负责把讨论整理成顺畅表达。",
        },
    )

    create_response = client.post(
        "/api/v1/conversations/group",
        json={
            "title": "自我介绍群聊",
            "memberIds": ["architect", "critic", "writer"],
        },
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": conversation_id,
            "content": "请你们各自做一个简短自我介绍。",
        },
    )
    assert response.status_code == 201

    public_requests = captured_requests[1:]
    assert [item["agent_id"] for item in public_requests] == ["architect", "critic", "writer"]

    for public_request in public_requests:
        system_messages = [content for role, content in public_request["messages"] if role == "system"]
        assert any("固定顺序的群聊接力" in content for content in system_messages)
        assert any("发言者身份会由系统单独展示" in content for content in system_messages)
        assert any("群聊内部主持说明" in content for content in system_messages)

    architect_identity = _find_identity_message(public_requests[0])
    critic_identity = _find_identity_message(public_requests[1])
    writer_identity = _find_identity_message(public_requests[2])

    assert "- 你的显示名：Architect (architect)" in architect_identity
    assert "- 你的角色定位：擅长结构化拆解与系统设计" in architect_identity
    assert "- 你的当前顺位：第 1 位，共 3 位成员" in architect_identity
    assert "1. Architect (architect) - 擅长结构化拆解与系统设计" in architect_identity
    assert "2. Critic (critic) - 擅长找风险、挑漏洞、做反向检验" in architect_identity
    assert "3. Writer (writer) - 擅长表达、整理和改写" in architect_identity
    assert "在你之前已完成当前轮次发言的成员：当前轮次暂无其他成员已发言" in architect_identity
    assert "在你之后将继续接力的成员：Critic、Writer" in architect_identity

    assert "- 你的显示名：Critic (critic)" in critic_identity
    assert "- 你的角色定位：擅长找风险、挑漏洞、做反向检验" in critic_identity
    assert "- 你的当前顺位：第 2 位，共 3 位成员" in critic_identity
    assert "在你之前已完成当前轮次发言的成员：Architect" in critic_identity
    assert "在你之后将继续接力的成员：Writer" in critic_identity

    assert "- 你的显示名：Writer (writer)" in writer_identity
    assert "- 你的角色定位：擅长表达、整理和改写" in writer_identity
    assert "- 你的当前顺位：第 3 位，共 3 位成员" in writer_identity
    assert "在你之前已完成当前轮次发言的成员：Architect、Critic" in writer_identity
    assert "在你之后将继续接力的成员：你是本轮最后一位发言成员" in writer_identity

    assert [message["content"] for message in response.json()["agentMessages"]] == [
        "我是 Architect，负责结构化拆解。",
        "我是 Critic，负责找风险和边界。",
        "我是 Writer，负责把讨论整理成顺畅表达。",
    ]


def test_sanitize_group_reply_content_only_strips_current_agent_prefix_without_harming_body():
    agent = SimpleNamespace(id="architect", name="Architect")

    assert chat_service.sanitize_group_reply_content(
        agent,
        "Architect Updated: 我同意 Critic：提出的边界，也建议 Writer：把结论整理成摘要。",
    ) == "我同意 Critic：提出的边界，也建议 Writer：把结论整理成摘要。"
    assert chat_service.sanitize_group_reply_content(
        agent,
        "Architect：Architect：先拆需求边界。",
    ) == "先拆需求边界。"


def test_post_message_in_group_conversation_sequential_smoke_prevents_double_prefix_pollution(client, monkeypatch):
    captured_requests = []
    _install_group_runtime_fake_client(
        monkeypatch,
        captured_requests,
        public_replies={
            "architect": "Architect：Architect：先拆需求边界。",
            "critic": "Critic Update: Critic：补充失败路径。",
            "writer": "Writer Updated: Writer：整理为结论。",
        },
    )

    create_response = client.post(
        "/api/v1/conversations/group",
        json={
            "title": "顺序接力 smoke",
            "memberIds": ["architect", "critic", "writer"],
        },
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": conversation_id,
            "content": "请按顺序接力，先拆需求，再补风险，最后整理结果。",
        },
    )
    assert response.status_code == 201
    assert [message["content"] for message in response.json()["agentMessages"]] == [
        "先拆需求边界。",
        "补充失败路径。",
        "整理为结论。",
    ]

    public_requests = captured_requests[1:]
    critic_visible_context = [content for role, content in public_requests[1]["messages"] if role != "system"]
    writer_visible_context = [content for role, content in public_requests[2]["messages"] if role != "system"]
    assert critic_visible_context == ["请按顺序接力，先拆需求，再补风险，最后整理结果。"]
    assert writer_visible_context == ["请按顺序接力，先拆需求，再补风险，最后整理结果。"]
    assert [role for role, _ in public_requests[1]["messages"]][-1] == "user"
    assert [role for role, _ in public_requests[2]["messages"]][-1] == "user"
    assert all(role == "system" for role, _ in public_requests[1]["messages"][:-1])
    assert all(role == "system" for role, _ in public_requests[2]["messages"][:-1])
    critic_system_context = [content for role, content in public_requests[1]["messages"] if role == "system"]
    writer_system_context = [content for role, content in public_requests[2]["messages"] if role == "system"]
    assert public_requests[1]["metadata"]["dispatch_strategy"] == "broadcast_chain"
    assert public_requests[2]["metadata"]["dispatch_strategy"] == "broadcast_chain"
    assert public_requests[1]["metadata"]["trigger_event_type"] == "user_message"
    assert any("speaker_name=Architect" in content and "content=先拆需求边界。" in content for content in critic_system_context)
    assert any("speaker_name=Architect" in content and "content=先拆需求边界。" in content for content in writer_system_context)
    assert any("speaker_name=Critic" in content and "content=补充失败路径。" in content for content in writer_system_context)
    assert any("event_type=agent_message" in content for content in critic_system_context)
    assert any("event_type=agent_message" in content for content in writer_system_context)

    messages_response = client.get("/api/v1/messages", params={"conversationId": conversation_id})
    items = messages_response.json()["items"]
    assert [item["content"] for item in items][-4:] == [
        "请按顺序接力，先拆需求，再补风险，最后整理结果。",
        "先拆需求边界。",
        "补充失败路径。",
        "整理为结论。",
    ]
    assert all("：Architect：" not in item["content"] for item in items)
    assert all("：Critic：" not in item["content"] for item in items)
    assert all("：Writer：" not in item["content"] for item in items)


def test_post_message_in_group_conversation_open_discussion_smoke_preserves_role_difference(client, monkeypatch):
    captured_requests = []
    _install_group_runtime_fake_client(
        monkeypatch,
        captured_requests,
        public_replies={
            "architect": "我先把方案拆成目标、范围和接口三层。",
            "critic": "我重点盯失败路径、资源约束和误用风险。",
            "writer": "我把前两位的观点整理成用户能直接理解的结论。",
        },
    )

    create_response = client.post(
        "/api/v1/conversations/group",
        json={
            "title": "开放讨论 smoke",
            "memberIds": ["architect", "critic", "writer"],
        },
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": conversation_id,
            "content": "围绕首版产品怎么做，开放讨论一下。",
        },
    )
    assert response.status_code == 201

    public_requests = captured_requests[1:]
    architect_system_messages = [content for role, content in public_requests[0]["messages"] if role == "system"]
    critic_system_messages = [content for role, content in public_requests[1]["messages"] if role == "system"]
    writer_system_messages = [content for role, content in public_requests[2]["messages"] if role == "system"]

    assert any("偏系统性与结构化思考" in content for content in architect_system_messages)
    assert any("偏风险识别和问题质疑" in content for content in critic_system_messages)
    assert any("偏表达整理和内容组织" in content for content in writer_system_messages)

    assert [message["content"] for message in response.json()["agentMessages"]] == [
        "我先把方案拆成目标、范围和接口三层。",
        "我重点盯失败路径、资源约束和误用风险。",
        "我把前两位的观点整理成用户能直接理解的结论。",
    ]


def test_post_message_stream_rejects_direct_conversation(client):
    response = client.post(
        "/api/v1/messages/stream",
        json={
            "conversationId": "direct-architect-default",
            "content": "这条直聊不应该走流式接口",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conversation_not_streamable",
            "message": "Streaming is only supported for group conversations",
        }
    }


def test_post_message_stream_in_group_conversation_yields_ordered_events(client, monkeypatch):
    captured_requests = []
    _install_group_runtime_fake_client(
        monkeypatch,
        captured_requests,
        public_replies={
            "architect": "Architect：先拆主结构。",
            "critic": "Critic：补充风险边界。",
            "writer": "Writer：整理成结论。",
        },
    )

    with client.stream(
        "POST",
        "/api/v1/messages/stream",
        json={
            "conversationId": "group-product-discussion-default",
            "content": "请按顺序接力完成方案。",
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse_events(response.read().decode("utf-8"))

    assert [event["event"] for event in events] == [
        "user_message",
        "moderator_note_ready",
        "agent_message",
        "agent_message",
        "agent_message",
        "conversation_updated",
        "done",
    ]
    assert events[0]["data"]["payload"]["message"]["senderId"] == "user"
    assert events[0]["data"]["payload"]["message"]["content"] == "请按顺序接力完成方案。"
    assert events[0]["data"]["payload"]["runtimeHooks"] == {
        "dispatchStrategy": "broadcast_chain",
        "triggerEventType": "user_message",
        "reservedEventTypes": [
            "user_message",
            "moderator_note_ready",
            "agent_message",
            "conversation_updated",
            "done",
            "error",
        ],
        "reservedDispatchStrategies": ["broadcast_chain"],
        "reservedFutureEventTypes": [
            "agent_thinking",
            "tool_call",
            "tool_result",
            "dispatch_progress",
        ],
        "reservedFutureDispatchStrategies": [
            "round_robin",
            "parallel_fan_out",
            "manual_handoff",
        ],
    }
    assert [event["data"]["payload"]["message"]["senderId"] for event in events[2:5]] == [
        "architect",
        "critic",
        "writer",
    ]
    assert [event["data"]["payload"]["message"]["content"] for event in events[2:5]] == [
        "先拆主结构。",
        "补充风险边界。",
        "整理成结论。",
    ]
    final_updated_at = events[4]["data"]["payload"]["conversationUpdatedAt"]
    assert events[5]["data"]["payload"]["conversationUpdatedAt"] == final_updated_at
    assert events[6]["data"]["payload"]["conversationUpdatedAt"] == final_updated_at
    assert captured_requests[0]["metadata"]["purpose"] == "group_moderator_note"
    assert [request["agent_id"] for request in captured_requests[1:]] == ["architect", "critic", "writer"]
    assert all(request["metadata"]["dispatch_strategy"] == "broadcast_chain" for request in captured_requests[1:])
    assert all(request["metadata"]["trigger_event_type"] == "user_message" for request in captured_requests[1:])
    assert all(
        request["metadata"]["reserved_event_types"]
        == [
            "user_message",
            "moderator_note_ready",
            "agent_message",
            "conversation_updated",
            "done",
            "error",
        ]
        for request in captured_requests[1:]
    )
    assert all(
        request["metadata"]["reserved_dispatch_strategies"] == ["broadcast_chain"]
        for request in captured_requests[1:]
    )
    assert all(
        request["metadata"]["reserved_future_event_types"]
        == [
            "agent_thinking",
            "tool_call",
            "tool_result",
            "dispatch_progress",
        ]
        for request in captured_requests[1:]
    )
    assert all(
        request["metadata"]["reserved_future_dispatch_strategies"]
        == [
            "round_robin",
            "parallel_fan_out",
            "manual_handoff",
        ]
        for request in captured_requests[1:]
    )


def test_post_message_stream_uses_runtime_hooks_from_stream_payload(client, monkeypatch):
    def fake_stream_group_message(db, conversation, content, attachments=None):
        user_message = chat_service.Message(
            id="msg-user",
            conversation_id=conversation.id,
            sender_type="user",
            sender_id="user",
            content=content,
            attachments=[],
            created_at="2026-05-27T10:00:00.000Z",
        )
        yield (
            "user_message",
            {
                "conversation_id": conversation.id,
                "message": user_message,
                "conversation_updated_at": "2026-05-27T10:00:00.000Z",
                "runtime_hooks": {
                    "dispatch_strategy": "broadcast_chain",
                    "trigger_event_type": "user_message",
                    "reserved_event_types": [
                        "user_message",
                        "moderator_note_ready",
                        "agent_message",
                        "conversation_updated",
                        "done",
                        "error",
                    ],
                    "reserved_dispatch_strategies": ["broadcast_chain"],
                    "reserved_future_event_types": [
                        "agent_thinking",
                        "tool_call",
                        "tool_result",
                        "dispatch_progress",
                    ],
                    "reserved_future_dispatch_strategies": [
                        "round_robin",
                        "parallel_fan_out",
                        "manual_handoff",
                    ],
                },
            },
        )
        yield (
            "done",
            {
                "conversation_id": conversation.id,
                "conversation_updated_at": "2026-05-27T10:00:01.000Z",
                "runtime_hooks": {
                    "dispatch_strategy": "round_robin",
                    "trigger_event_type": "dispatch_progress",
                    "reserved_event_types": [
                        "user_message",
                        "moderator_note_ready",
                        "agent_message",
                        "conversation_updated",
                        "done",
                        "error",
                    ],
                    "reserved_dispatch_strategies": ["broadcast_chain"],
                    "reserved_future_event_types": [
                        "agent_thinking",
                        "tool_call",
                        "tool_result",
                        "dispatch_progress",
                    ],
                    "reserved_future_dispatch_strategies": [
                        "round_robin",
                        "parallel_fan_out",
                        "manual_handoff",
                    ],
                },
            },
        )

    monkeypatch.setattr(messages_route, "stream_group_message", fake_stream_group_message)

    with client.stream(
        "POST",
        "/api/v1/messages/stream",
        json={
            "conversationId": "group-product-discussion-default",
            "content": "请按顺序接力完成方案。",
        },
    ) as response:
        assert response.status_code == 200
        events = _parse_sse_events(response.read().decode("utf-8"))

    assert [event["event"] for event in events] == ["user_message", "done"]
    assert events[0]["data"]["payload"]["runtimeHooks"]["dispatchStrategy"] == "broadcast_chain"
    assert events[1]["data"]["payload"]["runtimeHooks"]["dispatchStrategy"] == "round_robin"
    assert events[1]["data"]["payload"]["runtimeHooks"]["triggerEventType"] == "dispatch_progress"


def test_post_message_stream_in_group_conversation_keeps_completed_messages_and_emits_error(client, monkeypatch):
    def fake_generate_agent_reply(
        db,
        conversation,
        agent,
        content,
        attachments=None,
        history_messages=None,
        round_messages=None,
        member_summary=None,
        replied_agent_ids=None,
    ):
        if agent.id == "critic":
            raise ValueError("critic stream failed")
        return f"{agent.id} safe reply"

    monkeypatch.setattr(chat_service, "generate_agent_reply", fake_generate_agent_reply)

    with client.stream(
        "POST",
        "/api/v1/messages/stream",
        json={
            "conversationId": "group-product-discussion-default",
            "content": "请继续接力，但第二位会失败。",
        },
    ) as response:
        assert response.status_code == 200
        events = _parse_sse_events(response.read().decode("utf-8"))

    assert [event["event"] for event in events] == [
        "user_message",
        "moderator_note_ready",
        "agent_message",
        "error",
        "agent_message",
        "conversation_updated",
        "done",
    ]
    assert events[2]["data"]["payload"]["message"]["senderId"] == "architect"
    assert events[2]["data"]["payload"]["message"]["content"] == "architect safe reply"
    assert events[3]["data"]["payload"]["error"] == {
        "code": "model_request_failed",
        "message": "Critic 回复失败：critic stream failed",
    }
    assert events[4]["data"]["payload"]["message"]["senderId"] == "writer"
    assert events[4]["data"]["payload"]["message"]["content"] == "writer safe reply"
    assert events[3]["data"]["payload"]["runtimeHooks"] == {
        "dispatchStrategy": "broadcast_chain",
        "triggerEventType": "user_message",
        "reservedEventTypes": [
            "user_message",
            "moderator_note_ready",
            "agent_message",
            "conversation_updated",
            "done",
            "error",
        ],
        "reservedDispatchStrategies": ["broadcast_chain"],
        "reservedFutureEventTypes": [
            "agent_thinking",
            "tool_call",
            "tool_result",
            "dispatch_progress",
        ],
        "reservedFutureDispatchStrategies": [
            "round_robin",
            "parallel_fan_out",
            "manual_handoff",
        ],
    }

    messages_response = client.get(
        "/api/v1/messages",
        params={"conversationId": "group-product-discussion-default"},
    )
    items = messages_response.json()["items"]
    assert [item["content"] for item in items][-3:] == [
        "请继续接力，但第二位会失败。",
        "architect safe reply",
        "writer safe reply",
    ]

    with client.app.state.session_factory() as db:
        conversation = db.get(chat_service.Conversation, "group-product-discussion-default")
        default_thread = conversation.runtime_metadata["group_runtime"]["default_thread"]
        assert default_thread["dispatch_state"]["status"] == "completed"
        assert default_thread["dispatch_state"]["completed_member_ids"] == ["architect", "writer"]
        assert default_thread["dispatch_state"]["failed_member_ids"] == ["critic"]
        assert default_thread["dispatch_state"]["pending_member_ids"] == []


def test_post_message_stream_in_group_conversation_continues_when_moderator_note_fails(client, monkeypatch):
    def fake_generate_group_moderator_note(
        db,
        conversation,
        agent,
        content,
        member_summary,
        history_messages=None,
        event_window=None,
    ):
        raise ValueError("moderator note failed")

    def fake_generate_agent_reply(
        db,
        conversation,
        agent,
        content,
        attachments=None,
        history_messages=None,
        round_messages=None,
        member_summary=None,
        replied_agent_ids=None,
    ):
        return f"{agent.id} safe reply"

    monkeypatch.setattr(
        chat_service,
        "generate_group_moderator_note",
        fake_generate_group_moderator_note,
    )
    monkeypatch.setattr(chat_service, "generate_agent_reply", fake_generate_agent_reply)

    with client.stream(
        "POST",
        "/api/v1/messages/stream",
        json={
            "conversationId": "group-product-discussion-default",
            "content": "主持说明失败后也继续。",
        },
    ) as response:
        assert response.status_code == 200
        events = _parse_sse_events(response.read().decode("utf-8"))

    assert [event["event"] for event in events] == [
        "user_message",
        "error",
        "agent_message",
        "agent_message",
        "agent_message",
        "conversation_updated",
        "done",
    ]
    assert events[1]["data"]["payload"]["error"] == {
        "code": "model_request_failed",
        "message": "群聊主持说明生成失败：moderator note failed",
    }
    assert [events[index]["data"]["payload"]["message"]["senderId"] for index in (2, 3, 4)] == [
        "architect",
        "critic",
        "writer",
    ]

    messages_response = client.get(
        "/api/v1/messages",
        params={"conversationId": "group-product-discussion-default"},
    )
    items = messages_response.json()["items"]
    assert [item["content"] for item in items][-4:] == [
        "主持说明失败后也继续。",
        "architect safe reply",
        "critic safe reply",
        "writer safe reply",
    ]


def test_build_chat_request_group_runtime_hooks_follow_dispatch_trigger_event(client):
    with client.app.state.session_factory() as db:
        conversation = db.get(chat_service.Conversation, "group-product-discussion-default")
        agent = db.get(chat_service.Agent, "critic")
        assert conversation is not None
        assert agent is not None

        event_window = [
            chat_service._build_group_public_event(
                event_type="agent_message",
                sender_type="agent",
                sender_id="architect",
                content="先拆主结构。",
                speaker_name="Architect",
                event_id="evt-agent-latest",
                created_at="2026-05-27T10:00:01.000Z",
            ),
            chat_service._build_group_trigger_event(
                content="请继续接力。",
                event_id="evt-user-trigger",
                created_at="2026-05-27T10:00:00.000Z",
            ),
        ]
        dispatch_state = chat_service._build_group_dispatch_state(
            trigger_event_id="evt-user-trigger",
            reply_agent_ids=["critic", "writer"],
            completed_member_ids=["architect"],
            status="running",
        )

        request = chat_service.build_chat_request(
            config=chat_service.AdapterConfig(
                provider="mock",
                model="mock-model",
                api_key="",
                api_format="openai",
            ),
            conversation=conversation,
            agent=agent,
            content="请继续接力。",
            is_group=True,
            event_window=event_window,
            dispatch_state=dispatch_state,
        )

    assert request.metadata["dispatch_strategy"] == "broadcast_chain"
    assert request.metadata["trigger_event_type"] == "user_message"
    assert request.metadata["reserved_event_types"] == [
        "user_message",
        "moderator_note_ready",
        "agent_message",
        "conversation_updated",
        "done",
        "error",
    ]
    assert request.metadata["reserved_dispatch_strategies"] == ["broadcast_chain"]
    assert request.metadata["reserved_future_event_types"] == [
        "agent_thinking",
        "tool_call",
        "tool_result",
        "dispatch_progress",
    ]
    assert request.metadata["reserved_future_dispatch_strategies"] == [
        "round_robin",
        "parallel_fan_out",
        "manual_handoff",
    ]
    assert any(
        message.role == "user" and message.content == "请继续接力。"
        for message in request.messages
    )


def test_message_stream_runtime_hooks_contract_accepts_reserved_future_values():
    hooks = MessageStreamRuntimeHooks(
        dispatch_strategy="round_robin",
        trigger_event_type="dispatch_progress",
        reserved_event_types=[
            "user_message",
            "moderator_note_ready",
            "agent_message",
            "conversation_updated",
            "done",
            "error",
        ],
        reserved_dispatch_strategies=["broadcast_chain"],
        reserved_future_event_types=[
            "agent_thinking",
            "tool_call",
            "tool_result",
            "dispatch_progress",
        ],
        reserved_future_dispatch_strategies=[
            "round_robin",
            "parallel_fan_out",
            "manual_handoff",
        ],
    )

    assert hooks.model_dump(by_alias=True) == {
        "dispatchStrategy": "round_robin",
        "triggerEventType": "dispatch_progress",
        "reservedEventTypes": [
            "user_message",
            "moderator_note_ready",
            "agent_message",
            "conversation_updated",
            "done",
            "error",
        ],
        "reservedDispatchStrategies": ["broadcast_chain"],
        "reservedFutureEventTypes": [
            "agent_thinking",
            "tool_call",
            "tool_result",
            "dispatch_progress",
        ],
        "reservedFutureDispatchStrategies": [
            "round_robin",
            "parallel_fan_out",
            "manual_handoff",
        ],
    }

def test_post_message_returns_conversation_not_found_for_missing_conversation(client):
    response = client.post(
        "/api/v1/messages",
        json={"conversationId": "missing-conversation", "content": "hello"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "conversation_not_found", "message": "Conversation not found"}
    }


def test_post_message_rejects_blank_content_with_uniform_error(client):
    response = client.post(
        "/api/v1/messages",
        json={"conversationId": "direct-architect-default", "content": "   "},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "message": "content cannot be empty"}
    }


def test_post_message_rejects_inactive_group_conversation(client):
    first_agent = client.post(
        "/api/v1/agents",
        json={
            "name": "甲助手",
            "roleSummary": "用于禁用群聊测试",
            "styleSummary": "简洁",
            "systemPrompt": "负责测试。",
            "avatar": "J",
        },
    ).json()["id"]
    second_agent = client.post(
        "/api/v1/agents",
        json={
            "name": "乙助手",
            "roleSummary": "用于禁用群聊测试",
            "styleSummary": "简洁",
            "systemPrompt": "负责测试。",
            "avatar": "Y",
        },
    ).json()["id"]

    group_response = client.post(
        "/api/v1/conversations/group",
        json={"title": "待禁用群聊", "memberIds": [first_agent, second_agent]},
    )
    group_id = group_response.json()["id"]
    assert group_response.status_code == 201

    assert client.delete(f"/api/v1/agents/{first_agent}").status_code == 204
    assert client.delete(f"/api/v1/agents/{second_agent}").status_code == 204

    conversations_response = client.get("/api/v1/conversations")
    group = next(conversation for conversation in conversations_response.json() if conversation["id"] == group_id)
    assert group["memberIds"] == ["user"]
    assert group["isDisabled"] is True

    response = client.post(
        "/api/v1/messages",
        json={"conversationId": group_id, "content": "还能继续发吗？"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "conversation_inactive", "message": "Conversation is inactive"}
    }
