from __future__ import annotations

import app.llm.adapters.base as base_module
import app.llm.protocols.agents as agent_protocol
import app.llm.protocols.common as common_protocol
import app.services.chat_service as chat_service
from app.llm.protocols.agents import (
    build_agent_local_reply,
    build_group_moderator_note_prompt,
    build_group_runtime_protocol_system_message,
)


def test_agent_local_reply_builder_lives_in_agent_protocol_module():
    reply = build_agent_local_reply(
        agent_id="architect",
        agent_name="Architect",
        user_text="继续拆解方案",
        is_group=False,
        has_system_prompt=True,
        history_count=2,
    )

    assert "我先从结构上拆一下" in reply
    assert "继续拆解方案" in reply
    assert "已参考系统提示词" in reply
    assert "已参考2条历史消息" in reply


def test_common_protocol_module_does_not_expose_agent_style_builders():
    assert not hasattr(common_protocol, "build_local_reply")
    assert not hasattr(base_module, "STYLE_PREFIX")


def test_group_runtime_prompt_builders_live_in_agent_protocol_module():
    protocol_message = build_group_runtime_protocol_system_message()
    moderator_prompt = build_group_moderator_note_prompt(
        user_content="继续围绕第一版范围展开。",
        member_count=3,
        member_order_text="1. Architect\n2. Critic\n3. Writer",
        current_agent_name="Architect",
        current_agent_id="architect",
        current_agent_position=1,
        has_source_context=False,
        context_preview_text="speaker_name=用户 content=继续围绕第一版范围展开。",
    )

    assert protocol_message.role == "system"
    assert "固定顺序的群聊接力" in protocol_message.content
    assert "一次性主持说明" in moderator_prompt
    assert "当前 Agent 身份：Architect (architect)，位于第 1 位" in moderator_prompt


def test_chat_service_no_longer_owns_group_runtime_protocol_text_constants():
    assert not hasattr(chat_service, "GROUP_RUNTIME_PROTOCOL_TEXT")
    assert not hasattr(chat_service, "GROUP_MODERATOR_NOTE_SYSTEM_TEXT")
    assert hasattr(agent_protocol, "GROUP_RUNTIME_PROTOCOL_TEXT")


def test_common_protocol_module_does_not_expose_thinking_display_controls():
    assert not hasattr(common_protocol, "build_thinking_display_state")
    assert not hasattr(common_protocol, "resolve_thinking_visibility")
