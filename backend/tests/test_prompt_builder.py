from __future__ import annotations

from app.llm.schemas import ChatMessage
from app.models import Agent, Conversation
from app.services import chat_service
from app.services.prompt_builder import build_chat_messages, build_moderator_note_messages


def _agent() -> Agent:
    return Agent(
        id="a1",
        name="助手",
        role_summary="通用助手",
        style_summary="简洁",
        system_prompt="你是一个助手",
        avatar="A",
        avatar_image=None,
        theme_color=None,
        theme_light=None,
        theme_soft=None,
        model_config_id=None,
        model_unavailable=False,
        is_template=False,
        pinned=False,
        pinned_at=None,
    )


def _direct_conversation() -> Conversation:
    conversation = Conversation(
        id="c1",
        title="t",
        type="direct",
        agent_id="a1",
        source_conversation_id=None,
        model_config_id=None,
        runtime_metadata={},
        is_disabled=False,
        pinned=False,
        pinned_at=None,
        created_at="2026-05-29T00:00:00.000Z",
        updated_at="2026-05-29T00:00:00.000Z",
    )
    conversation.runtime_metadata = {}
    return conversation


def _group_conversation() -> Conversation:
    conversation = Conversation(
        id="g1",
        title="t",
        type="group",
        agent_id=None,
        source_conversation_id=None,
        model_config_id=None,
        runtime_metadata={},
        is_disabled=False,
        pinned=False,
        pinned_at=None,
        created_at="2026-05-29T00:00:00.000Z",
        updated_at="2026-05-29T00:00:00.000Z",
    )
    conversation.runtime_metadata = {}
    return conversation


def test_direct_messages_have_system_then_user():
    msgs = build_chat_messages(
        conversation=_direct_conversation(),
        agent=_agent(),
        content="你好",
        is_group=False,
        history_messages=[],
    )

    assert msgs[0].role == "system"
    assert "你是一个助手" in msgs[0].content
    assert msgs[-1].role == "user"
    assert msgs[-1].content == "你好"


def test_group_messages_contain_protocol_and_identity_and_context():
    conv = _group_conversation()
    agent = _agent()
    msgs = build_chat_messages(
        conversation=conv,
        agent=agent,
        content="继续",
        is_group=True,
        history_messages=[],
        member_summary=[
            {
                "position": 1,
                "agent_id": "a1",
                "agent_name": "助手",
                "role_summary": "通用助手",
            }
        ],
        replied_agent_ids=[],
        event_window=[],
        dispatch_state={
            "status": "running",
            "strategy": "broadcast_chain",
            "completed_member_ids": [],
            "failed_member_ids": [],
            "pending_member_ids": [],
            "trigger_event_id": None,
        },
    )

    roles = [message.role for message in msgs]
    assert roles[0] == "system"
    assert all(role == "system" for role in roles[:-1])
    assert msgs[-1].role in {"system", "user"}
    joined = "\n".join(message.content for message in msgs)
    assert "助手" in joined
    assert "固定顺序的群聊接力" in joined


def test_build_chat_request_messages_match_prompt_builder():
    agent = _agent()
    conv = _direct_conversation()
    cfg = chat_service.AdapterConfig(provider="mock", model="m")

    req = chat_service.build_chat_request(
        cfg,
        conv,
        agent,
        "你好",
        is_group=False,
        history_messages=[],
    )
    direct = build_chat_messages(
        conversation=conv,
        agent=agent,
        content="你好",
        is_group=False,
        history_messages=[],
    )

    assert [(message.role, message.content) for message in req.messages] == [
        (message.role, message.content) for message in direct
    ]


def test_build_moderator_note_messages_structure():
    conv = _group_conversation()
    msgs = build_moderator_note_messages(
        conversation=conv,
        agent=_agent(),
        content="开始",
        member_summary=[
            {
                "position": 1,
                "agent_id": "a1",
                "agent_name": "助手",
                "role_summary": "通用助手",
            }
        ],
        history_messages=[],
        event_window=[],
    )

    assert msgs[-1].role == "user"
    assert any(message.role == "system" for message in msgs)
    assert "当前用户输入：开始" in msgs[-1].content


def test_style_summary_injected_into_group_identity_when_enabled():
    conv = _group_conversation()
    agent = _agent()
    msgs = build_chat_messages(
        conversation=conv,
        agent=agent,
        content="继续",
        is_group=True,
        history_messages=[],
        member_summary=[
            {
                "position": 1,
                "agent_id": "a1",
                "agent_name": "助手",
                "role_summary": "通用助手",
            }
        ],
        replied_agent_ids=[],
        event_window=[],
        dispatch_state={
            "status": "running",
            "strategy": "broadcast_chain",
            "completed_member_ids": [],
            "failed_member_ids": [],
            "pending_member_ids": [],
            "trigger_event_id": None,
        },
        include_style_summary=True,
    )

    joined = "\n".join(message.content for message in msgs)
    assert "简洁" in joined
