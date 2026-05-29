from __future__ import annotations

from app.models import Message
from app.routes import messages as messages_route
from app.services import chat_service
from app.llm.schemas import ChatResponse, MessageUsage


def test_post_message_returns_thinking_usage_and_summary_contract(client, monkeypatch):
    def fake_generate_agent_reply(
        db,
        conversation,
        agent,
        content,
        attachments=None,
        history_messages=None,
        thinking_enabled=False,
        **kwargs,
    ):
        return ChatResponse(
            content="<think>先做内部推理</think>\n\n# 结论\n\n这是结构化回复。",
            provider="qwen",
            model="qwen-plus",
            raw={"reasoning_content": "先做内部推理"},
            usage=MessageUsage(
                prompt_tokens=12,
                completion_tokens=18,
                reasoning_tokens=6,
                total_tokens=30,
            ),
        )

    monkeypatch.setattr(chat_service, "generate_agent_reply", fake_generate_agent_reply)

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "请给我一个结构化结论",
            "options": {
                "thinking": {
                    "enabled": True,
                }
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    agent_message = body["agentMessages"][0]
    assert agent_message["content"] == "# 结论\n\n这是结构化回复。"
    assert agent_message["renderFormat"] == "markdown"
    assert agent_message["thinking"] == {
        "available": True,
        "content": "先做内部推理",
        "defaultCollapsed": True,
    }
    assert agent_message["usage"] == {
        "promptTokens": 12,
        "completionTokens": 18,
        "reasoningTokens": 6,
        "totalTokens": 30,
    }
    assert agent_message["messageMeta"] == {
        "provider": "qwen",
        "model": "qwen-plus",
        "agentId": "architect",
        "agentName": "Architect",
        "roundIndex": None,
    }
    assert body["conversationUsageSummary"] == {
        "totalTokens": 30,
        "totalPromptTokens": 12,
        "totalCompletionTokens": 18,
        "totalReasoningTokens": 6,
        "byAgent": [
            {
                "agentId": "architect",
                "agentName": "Architect",
                "totalTokens": 30,
                "totalPromptTokens": 12,
                "totalCompletionTokens": 18,
                "totalReasoningTokens": 6,
            }
        ],
    }

    messages_response = client.get(
        "/api/v1/messages",
        params={"conversationId": "direct-architect-default"},
    )
    assert messages_response.status_code == 200
    last_message = messages_response.json()["items"][-1]
    assert last_message["thinking"]["content"] == "先做内部推理"
    assert messages_response.json()["conversationUsageSummary"]["totalTokens"] >= 30


def test_post_message_forwards_thinking_option_to_service_layer(client, monkeypatch):
    captured: dict[str, object] = {}

    def fake_send_message(db, conversation, content, attachments=None, thinking_enabled=False):
        captured["thinking_enabled"] = thinking_enabled
        user_message = Message(
            id="user-msg",
            conversation_id=conversation.id,
            sender_type="user",
            sender_id="user",
            content=content,
            render_format="plain_text",
            thinking_payload={},
            usage_payload={},
            message_meta={},
            attachments=attachments or [],
            created_at="2026-05-28T00:00:00.000Z",
        )
        agent_message = Message(
            id="agent-msg",
            conversation_id=conversation.id,
            sender_type="agent",
            sender_id=conversation.agent_id or "architect",
            content="已收到",
            render_format="markdown",
            thinking_payload={},
            usage_payload={},
            message_meta={},
            attachments=[],
            created_at="2026-05-28T00:00:01.000Z",
        )
        return chat_service.MessageSendResult(
            user_message=user_message,
            agent_messages=[agent_message],
            conversation_updated_at="2026-05-28T00:00:01.000Z",
            conversation_usage_summary={
                "total_tokens": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "by_agent": [],
            },
            warnings=[],
        )

    monkeypatch.setattr(messages_route, "send_message", fake_send_message)

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "开启 thinking",
            "options": {
                "thinking": {
                    "enabled": True,
                }
            },
        },
    )

    assert response.status_code == 201
    assert captured["thinking_enabled"] is True
