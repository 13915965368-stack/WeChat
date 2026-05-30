from app.models import Agent
from app.services.group_text_sanitizer import (
    sanitize_group_reply_content,
    strip_speaker_prefix_once,
)


def test_strip_speaker_prefix_once_colon():
    assert strip_speaker_prefix_once("张三：你好", ["张三"]) == "你好"


def test_strip_speaker_prefix_once_no_match():
    assert strip_speaker_prefix_once("你好", ["张三"]) == "你好"


def test_sanitize_group_reply_strips_self_prefix():
    agent = Agent(
        id="a1",
        name="张三",
        role_summary="",
        style_summary="",
        system_prompt="",
        avatar="",
    )
    assert sanitize_group_reply_content(agent, "张三：内容") == "内容"
