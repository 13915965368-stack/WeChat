from __future__ import annotations

import re
from typing import Any

from app.llm.schemas import ChatRequest, MessageThinking

THINK_TAG_PATTERN = re.compile(r"<think\b[^>]*>(.*?)</think>", re.IGNORECASE | re.DOTALL)
THINK_NOISE_PREFIX_PATTERN = re.compile(
    r"^\s*(?:reasoning(?:_content|_details)?|analysis|thoughts?)\s*[:：-]\s*",
    re.IGNORECASE,
)
MARKDOWN_OUTPUT_GUIDE_MARKER = "Markdown 输出格式要求："
MARKDOWN_OUTPUT_GUIDE = """Markdown 输出格式要求：
1. 使用规范 Markdown 输出。
2. 标题必须独立成行，标题前后各保留一个空行。
3. 表格必须使用标准 GFM 表格语法，表格前后各保留一个空行。
4. 列表项独立成行，不要把标题、列表、表格和正文挤在同一段里。
5. 如果内容不适合稳定组织成表格，改用小标题加列表，不要输出损坏的表格。
6. 不要把整篇内容写成一整段连续文本。

正确示例：
## 事件背景

这里是背景说明。

| 项目 | 内容 |
| --- | --- |
| 时间 | 2026年 |

## 影响

- 第一项
- 第二项"""


def resolve_render_format(*, sender_type: str, content: str) -> str:
    if sender_type == "agent" and content.strip():
        return "markdown"
    return "plain_text"


def split_content_and_thinking(
    content: str,
    *,
    reasoning_content: str = "",
    default_collapsed: bool = True,
) -> tuple[str, MessageThinking | None]:
    normalized_content = content.strip()
    extracted_parts = [match.strip() for match in THINK_TAG_PATTERN.findall(normalized_content) if match.strip()]
    cleaned_content = THINK_TAG_PATTERN.sub("", normalized_content).strip()
    thinking_content = normalize_thinking_content(
        reasoning_content.strip() or "\n\n".join(extracted_parts).strip()
    )

    thinking = None
    if thinking_content:
        thinking = MessageThinking(
            available=True,
            content=thinking_content,
            default_collapsed=default_collapsed,
        )

    if cleaned_content:
        return cleaned_content, thinking
    if thinking is not None:
        return "", thinking
    return normalized_content, thinking


def normalize_thinking_content(content: str) -> str:
    cleaned = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        return ""

    cleaned = THINK_NOISE_PREFIX_PATTERN.sub("", cleaned).strip()
    cleaned = re.sub(r"</?(?:analysis|reasoning|thoughts?)\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_markdown_output_system_prompt(system_prompt: str) -> str:
    normalized_prompt = system_prompt.strip()
    if not normalized_prompt:
        return MARKDOWN_OUTPUT_GUIDE
    if MARKDOWN_OUTPUT_GUIDE_MARKER in normalized_prompt:
        return normalized_prompt
    return f"{normalized_prompt}\n\n{MARKDOWN_OUTPUT_GUIDE}"


def build_thinking_provider_overrides(request: ChatRequest) -> dict[str, Any]:
    provider = request.config.provider.strip().lower()
    metadata = request.config.metadata or {}
    protocol = metadata.get("protocol", {}) if isinstance(metadata, dict) else {}
    thinking_protocol = protocol.get("thinking", {}) if isinstance(protocol, dict) else {}

    parameter_name = thinking_protocol.get("parameter")
    if isinstance(parameter_name, str) and parameter_name.strip():
        if not request.thinking.enabled and "disabled_value" not in thinking_protocol:
            return {}
        return {
            parameter_name.strip(): thinking_protocol.get(
                "enabled_value" if request.thinking.enabled else "disabled_value",
                request.thinking.enabled,
            )
        }

    if provider in {"qwen", "dashscope"}:
        return {"enable_thinking": request.thinking.enabled}
    if provider in {"minimax"}:
        return {
            "thinking_budget": 1024 if request.thinking.enabled else 0,
            "reasoning_split": True,
        }
    if provider in {"moonshot", "kimi"}:
        return {"thinking_enabled": request.thinking.enabled}
    if provider in {"deepseek"}:
        return {"thinking": {"type": "enabled" if request.thinking.enabled else "disabled"}}
    return {}


def build_response_format_provider_overrides(request: ChatRequest) -> dict[str, Any]:
    metadata = request.config.metadata or {}
    protocol = metadata.get("protocol", {}) if isinstance(metadata, dict) else {}
    response_format_protocol = protocol.get("response_format", {}) if isinstance(protocol, dict) else {}
    if not isinstance(response_format_protocol, dict) or not response_format_protocol:
        return {}

    parameter_name = str(response_format_protocol.get("parameter") or "response_format").strip()
    explicit_payload = response_format_protocol.get("payload")
    if explicit_payload is not None:
        return {parameter_name: explicit_payload}

    mode = str(response_format_protocol.get("type") or "").strip().lower()
    if mode in {"", "text"}:
        return {}
    if mode == "json_object":
        return {parameter_name: {"type": "json_object"}}
    if mode == "json_schema":
        schema = response_format_protocol.get("schema") or response_format_protocol.get("json_schema")
        if isinstance(schema, dict) and schema:
            schema_name = str(response_format_protocol.get("name") or "structured_output").strip()
            return {
                parameter_name: {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name or "structured_output",
                        "schema": schema,
                    },
                }
            }
    return {}
