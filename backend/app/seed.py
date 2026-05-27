from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, Conversation, ConversationMember, Message


DEFAULT_AGENTS = [
    {
        "id": "architect",
        "name": "Architect",
        "role_summary": "擅长结构化拆解与系统设计",
        "style_summary": "表达克制、偏框架化，习惯从整体到局部展开思路",
        "system_prompt": "你是一个偏系统性与结构化思考的智能助手。",
        "avatar": "A",
        "avatar_image": None,
        "theme_color": "#D4A574",
        "theme_light": "#F5E6D3",
        "theme_soft": "#FAF3EC",
        "model_config_id": None,
        "model_unavailable": False,
        "is_template": False,
        "pinned": False,
        "pinned_at": None,
    },
    {
        "id": "critic",
        "name": "Critic",
        "role_summary": "擅长找风险、挑漏洞、做反向检验",
        "style_summary": "偏审慎、偏质疑，善于提出边界条件和反面论证",
        "system_prompt": "你是一个偏风险识别和问题质疑的智能助手。",
        "avatar": "C",
        "avatar_image": None,
        "theme_color": "#C97B7B",
        "theme_light": "#F5DEDE",
        "theme_soft": "#FCF5F5",
        "model_config_id": None,
        "model_unavailable": False,
        "is_template": False,
        "pinned": False,
        "pinned_at": None,
    },
    {
        "id": "writer",
        "name": "Writer",
        "role_summary": "擅长表达、整理和改写",
        "style_summary": "偏自然、偏叙述，善于把复杂想法转化为流畅文字",
        "system_prompt": "你是一个偏表达整理和内容组织的智能助手。",
        "avatar": "W",
        "avatar_image": None,
        "theme_color": "#7BA89C",
        "theme_light": "#D4E8E2",
        "theme_soft": "#F0F7F5",
        "model_config_id": None,
        "model_unavailable": False,
        "is_template": False,
        "pinned": False,
        "pinned_at": None,
    },
    {
        "id": "blank-agent",
        "name": "Blank Agent",
        "role_summary": "空白模板 Agent，用于承接无预设提示词的对话入口",
        "style_summary": "不预置角色、风格或语气，由用户在会话中自由驱动",
        "system_prompt": "",
        "avatar": "B",
        "avatar_image": None,
        "theme_color": "#94A3B8",
        "theme_light": "#E2E8F0",
        "theme_soft": "#F8FAFC",
        "model_config_id": None,
        "model_unavailable": False,
        "is_template": True,
        "pinned": False,
        "pinned_at": None,
    },
]


def seed_agents(db: Session) -> None:
    existing_agents = {
        agent.id: agent
        for agent in db.scalars(select(Agent)).all()
    }
    for payload in DEFAULT_AGENTS:
        existing_agent = existing_agents.get(payload["id"])
        if existing_agent is None:
            db.add(Agent(**payload))
            continue

        if existing_agent.avatar_image is None and payload["avatar_image"] is not None:
            existing_agent.avatar_image = payload["avatar_image"]
        if existing_agent.theme_color is None:
            existing_agent.theme_color = payload["theme_color"]
        if existing_agent.theme_light is None:
            existing_agent.theme_light = payload["theme_light"]
        if existing_agent.theme_soft is None:
            existing_agent.theme_soft = payload["theme_soft"]
        if existing_agent.model_config_id is None and payload["model_config_id"] is not None:
            existing_agent.model_config_id = payload["model_config_id"]
        if existing_agent.model_unavailable is None:
            existing_agent.model_unavailable = payload["model_unavailable"]
        if existing_agent.id == "blank-agent":
            existing_agent.is_template = True
        elif existing_agent.is_template is None:
            existing_agent.is_template = payload["is_template"]
        if existing_agent.pinned is None:
            existing_agent.pinned = False
    db.flush()


def seed_default_data(db: Session) -> None:
    seed_agents(db)

    direct_id = "direct-architect-default"
    if db.get(Conversation, direct_id) is None:
        direct_conversation = Conversation(
            id=direct_id,
            type="direct",
            title="默认对话",
            agent_id="architect",
            model_config_id=None,
            runtime_metadata={},
            is_disabled=False,
            pinned=False,
            pinned_at=None,
            created_at="2026-05-10T09:00:00.000Z",
            updated_at="2026-05-10T09:57:00.000Z",
        )
        db.add(direct_conversation)
        db.flush()
        db.add_all(
            [
                ConversationMember(conversation_id=direct_id, member_id="user", sort_order=0),
                ConversationMember(conversation_id=direct_id, member_id="architect", sort_order=1),
                Message(
                    id="msg-seed-architect-1",
                    conversation_id=direct_id,
                    sender_type="agent",
                    sender_id="architect",
                    content="我们可以先把产品目标压缩成最小可运行版本。",
                    attachments=[],
                    created_at="2026-05-10T09:57:00.000Z",
                ),
            ]
        )
    else:
        existing_direct_conversation = db.get(Conversation, direct_id)
        if existing_direct_conversation is not None and existing_direct_conversation.runtime_metadata is None:
            existing_direct_conversation.runtime_metadata = {}

    group_id = "group-product-discussion-default"
    existing_group_conversation = db.get(Conversation, group_id)
    if existing_group_conversation is None:
        group_conversation = Conversation(
            id=group_id,
            type="group",
            title="产品方案讨论",
            agent_id=None,
            model_config_id=None,
            runtime_metadata={},
            is_disabled=False,
            pinned=True,
            pinned_at="2026-05-10T09:40:00.000Z",
            created_at="2026-05-10T09:20:00.000Z",
            updated_at="2026-05-10T09:40:00.000Z",
        )
        db.add(group_conversation)
        db.flush()
        db.add_all(
            [
                ConversationMember(conversation_id=group_id, member_id="user", sort_order=0),
                ConversationMember(conversation_id=group_id, member_id="architect", sort_order=1),
                ConversationMember(conversation_id=group_id, member_id="critic", sort_order=2),
                ConversationMember(conversation_id=group_id, member_id="writer", sort_order=3),
                Message(
                    id="msg-seed-group-1",
                    conversation_id=group_id,
                    sender_type="user",
                    sender_id="user",
                    content="我们来讨论一下第一版产品的核心功能吧。",
                    attachments=[],
                    created_at="2026-05-10T09:35:00.000Z",
                ),
                Message(
                    id="msg-seed-group-2",
                    conversation_id=group_id,
                    sender_type="agent",
                    sender_id="architect",
                    content="我先从结构上拆一下：第一版应该优先跑通主链路。",
                    attachments=[],
                    created_at="2026-05-10T09:36:00.000Z",
                ),
            ]
        )
    elif existing_group_conversation.pinned and existing_group_conversation.pinned_at is None:
        existing_group_conversation.pinned_at = existing_group_conversation.updated_at
    if existing_group_conversation is not None and existing_group_conversation.runtime_metadata is None:
        existing_group_conversation.runtime_metadata = {}

    db.commit()
