from __future__ import annotations


def build_agent_local_reply(
    agent_id: str,
    agent_name: str,
    user_text: str,
    is_group: bool,
    *,
    has_system_prompt: bool = False,
    history_count: int = 0,
) -> str:
    if agent_id == "architect":
        prefix = "我先从结构上拆一下："
        suffix = f"先把问题拆成几个可执行部分，再围绕“{user_text}”推进。"
    elif agent_id == "critic":
        prefix = "我先提醒几个风险点："
        suffix = f"这件事里最需要先看的，是“{user_text}”背后的风险和边界。"
    elif agent_id == "writer":
        prefix = "我先帮你整理表达："
        suffix = f"我先帮你把“{user_text}”整理成更顺的表达，再往下展开。"
    else:
        prefix = f"{agent_name}："
        suffix = f"我先围绕“{user_text}”给出一个可执行回应。"

    context_hints = []
    if has_system_prompt:
        context_hints.append("已参考系统提示词")
    if history_count > 0:
        context_hints.append(f"已参考{history_count}条历史消息")

    reply = f"{prefix}{suffix}" if not is_group else f"{agent_name}：{prefix}{suffix}"
    if not context_hints:
        return reply
    return f"{reply}（{'，'.join(context_hints)}）"
