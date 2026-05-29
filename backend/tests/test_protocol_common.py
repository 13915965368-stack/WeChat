from __future__ import annotations

from app.llm.protocols.common import (
    MARKDOWN_OUTPUT_GUIDE,
    MARKDOWN_OUTPUT_GUIDE_MARKER,
    build_response_format_provider_overrides,
    build_markdown_output_system_prompt,
    build_thinking_provider_overrides,
    split_content_and_thinking,
)
from app.llm.schemas import AdapterConfig, ChatMessage, ChatRequest


def _make_request(protocol: dict[str, object] | None = None) -> ChatRequest:
    return ChatRequest(
        config=AdapterConfig(
            provider="qwen",
            model="qwen-plus",
            metadata={"protocol": protocol or {}},
        ),
        messages=[ChatMessage(role="user", content="hello")],
        agent_id="architect",
        agent_name="Architect",
        user_text="hello",
    )


def test_build_response_format_provider_overrides_defaults_to_empty():
    assert build_response_format_provider_overrides(_make_request()) == {}


def test_build_response_format_provider_overrides_supports_json_object():
    request = _make_request({"response_format": {"type": "json_object"}})
    assert build_response_format_provider_overrides(request) == {
        "response_format": {"type": "json_object"}
    }


def test_build_response_format_provider_overrides_supports_json_schema():
    request = _make_request(
        {
            "response_format": {
                "type": "json_schema",
                "name": "task_output",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                    },
                    "required": ["summary"],
                },
            }
        }
    )
    assert build_response_format_provider_overrides(request) == {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "task_output",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                    },
                    "required": ["summary"],
                },
            },
        }
    }


def test_build_thinking_provider_overrides_uses_deepseek_thinking_object():
    request = ChatRequest(
        config=AdapterConfig(provider="deepseek", model="deepseek-chat"),
        messages=[ChatMessage(role="user", content="hello")],
        agent_id="architect",
        agent_name="Architect",
        user_text="hello",
    )
    request.thinking.enabled = True
    assert build_thinking_provider_overrides(request) == {"thinking": {"type": "enabled"}}


def test_build_thinking_provider_overrides_adds_minimax_reasoning_split():
    request = ChatRequest(
        config=AdapterConfig(provider="minimax", model="MiniMax-M2.7"),
        messages=[ChatMessage(role="user", content="hello")],
        agent_id="architect",
        agent_name="Architect",
        user_text="hello",
    )
    request.thinking.enabled = True
    assert build_thinking_provider_overrides(request) == {
        "thinking_budget": 1024,
        "reasoning_split": True,
    }


def test_build_thinking_provider_overrides_keeps_explicit_qwen_disable():
    request = _make_request()
    request.thinking.enabled = False
    assert build_thinking_provider_overrides(request) == {"enable_thinking": False}


def test_build_thinking_provider_overrides_keeps_explicit_deepseek_disable():
    request = ChatRequest(
        config=AdapterConfig(provider="deepseek", model="deepseek-chat"),
        messages=[ChatMessage(role="user", content="hello")],
        agent_id="architect",
        agent_name="Architect",
        user_text="hello",
    )
    request.thinking.enabled = False
    assert build_thinking_provider_overrides(request) == {"thinking": {"type": "disabled"}}


def test_split_content_and_thinking_matches_think_tags_with_attributes():
    content, thinking = split_content_and_thinking(
        '<think class="internal">先做推理</think>\n\n最终正文'
    )
    assert content == "最终正文"
    assert thinking is not None
    assert thinking.content == "先做推理"


def test_split_content_and_thinking_does_not_fallback_to_raw_think_tag_when_body_is_empty():
    content, thinking = split_content_and_thinking("<think>只保留推理</think>")
    assert content == ""
    assert thinking is not None
    assert thinking.content == "只保留推理"


def test_split_content_and_thinking_normalizes_reasoning_noise_prefix():
    content, thinking = split_content_and_thinking(
        "最终正文",
        reasoning_content="reasoning_content: 先整理结论",
    )
    assert content == "最终正文"
    assert thinking is not None
    assert thinking.content == "先整理结论"


def test_build_markdown_output_system_prompt_appends_format_guide_once():
    prompt = build_markdown_output_system_prompt("你是一个偏结构化思考的助手。")
    assert prompt.startswith("你是一个偏结构化思考的助手。")
    assert MARKDOWN_OUTPUT_GUIDE_MARKER in prompt
    assert prompt.count(MARKDOWN_OUTPUT_GUIDE_MARKER) == 1


def test_build_markdown_output_system_prompt_keeps_existing_guide_without_duplication():
    prompt = build_markdown_output_system_prompt(
        "你是一个偏结构化思考的助手。\n\nMarkdown 输出格式要求：\n- 保持规范。"
    )
    assert prompt.count(MARKDOWN_OUTPUT_GUIDE_MARKER) == 1


def test_build_markdown_output_system_prompt_returns_default_guide_for_empty_prompt():
    assert build_markdown_output_system_prompt("") == MARKDOWN_OUTPUT_GUIDE
