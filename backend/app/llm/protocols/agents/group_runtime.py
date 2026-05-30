from __future__ import annotations

from app.llm.schemas import ChatMessage

GROUP_RUNTIME_PROTOCOL_TEXT = (
    "你正在参与一个固定顺序的群聊接力。你要承接当前讨论继续推进，而不是复述用户原话、"
    "前序 Agent 原话或整段上下文记录。请结合自己的角色定位，只补充当前轮次最有价值的新增判断；"
    "后续成员会继续接力，因此不要替别人一次性说完全部内容。内部主持说明只作为运行时协作约束，"
    "不要在公开回复里直接暴露或自称正在主持。公开回复只需要写出你这轮真正要表达的内容；"
    "发言者身份会由系统单独展示。若上下文中出现群聊记录，它们用于说明之前是谁说了什么，"
    "不等于公开回复模板。如果用户要求你做自我介绍，可以自然介绍自己的身份和角色，"
    "是否提到名字由你当前的人设和语境决定。"
)

GROUP_MODERATOR_NOTE_SYSTEM_TEXT = (
    "你现在不是在生成公开回复，而是在为当前群聊生成一次性内部主持说明。"
    "这段说明只写入群聊运行时元数据，不进入普通消息流。"
)


def build_group_runtime_protocol_system_message() -> ChatMessage:
    return ChatMessage(role="system", content=GROUP_RUNTIME_PROTOCOL_TEXT)


def build_group_runtime_identity_system_message(
    *,
    agent_name: str,
    agent_id: str,
    role_summary: str,
    current_position: int,
    member_count: int,
    member_order_text: str,
    replied_text: str,
    upcoming_text: str,
) -> ChatMessage:
    return ChatMessage(
        role="system",
        content=(
            "当前公开回复身份说明：\n"
            f"- 你的显示名：{agent_name} ({agent_id})\n"
            f"- 你的角色定位：{role_summary}\n"
            f"- 你的当前顺位：第 {current_position} 位，共 {member_count} 位成员\n"
            f"- 当前群聊成员：\n{member_order_text}\n"
            f"- 在你之前已完成当前轮次发言的成员：{replied_text}\n"
            # f"- 在你之后将继续接力的成员：{upcoming_text}\n"
            "- 你不能只靠转录稿猜身份；以上身份信息就是当前群结构。\n"
            "- 发言者身份会由显示层单独展示；公开回复只需要写出你这轮真正要表达的内容。\n"
            "- 如果下方出现群聊上下文记录，其中的 speaker 字段是运行时元数据，不是公开回复模板。"
        ),
    )


def build_group_runtime_dispatch_system_message(
    *,
    strategy: str,
    status: str,
    trigger_event_type: str,
    completed_member_ids: list[str],
    failed_member_ids: list[str],
    pending_member_ids: list[str],
) -> ChatMessage:
    return ChatMessage(
        role="system",
        content=(
            "当前群聊运行段信息：\n"
            f"- 调度策略：{strategy}\n"
            f"- 运行状态：{status}\n"
            f"- 触发事件类型：{trigger_event_type}\n"
            f"- 当前已完成成员：{', '.join(completed_member_ids) or '(空)'}\n"
            f"- 当前失败成员：{', '.join(failed_member_ids) or '(空)'}\n"
            # f"- 当前待发言成员：{', '.join(pending_member_ids) or '(空)'}\n"
            "- 你需要承接当前公开事件窗口里最新的状态继续推进，不要把窗口里的记录当成公开回复模板。"
        ),
    )


def build_group_runtime_moderator_note_system_message(note: str) -> ChatMessage:
    return ChatMessage(
        role="system",
        content=f"群聊内部主持说明（仅内部使用，不要直接说出来）：{note}",
    )


def build_group_moderator_note_instruction_message() -> ChatMessage:
    return ChatMessage(role="system", content=GROUP_MODERATOR_NOTE_SYSTEM_TEXT)


def build_group_moderator_note_prompt(
    *,
    user_content: str,
    member_count: int,
    member_order_text: str,
    current_agent_name: str,
    current_agent_id: str,
    current_agent_position: int,
    has_source_context: bool,
    context_preview_text: str,
) -> str:
    return (
        "请生成一段只供群聊内部使用的一次性主持说明。\n"
        f"当前用户输入：{user_content.strip()}\n"
        f"成员数量：{member_count}\n"
        f"成员顺序：\n{member_order_text}\n"
        f"当前 Agent 身份：{current_agent_name} ({current_agent_id})，位于第 {current_agent_position} 位\n"
        f"是否存在来源上下文：{'是' if has_source_context else '否'}\n"
        f"当前上下文记录：\n{context_preview_text}\n\n"
        "输出要求：\n"
        "1. 用 2-5 句中文概括当前群聊要完成的事和协作方式。\n"
        "2. 明确后续成员要按顺序承接，不要重复上下文记录。\n"
        "3. 不要写成对用户可见的发言，不要自称主持人已经发言。\n"
        "4. 不要输出 Markdown 标题或列表符号。"
    )
