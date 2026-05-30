from __future__ import annotations

import re

from app.models import Agent

GROUP_REPLY_PREFIX_MAX_STRIPS = 3


def _strip_one_prefix(content: str, prefix: str) -> str:
    normalized_prefix = prefix.strip()
    if not normalized_prefix:
        return content

    escaped_prefix = re.escape(normalized_prefix)
    patterns = (
        rf"^{escaped_prefix}\s*[：:]\s*",
        rf"^{escaped_prefix}\s+(?:updated|update)\s*[：:]\s*",
    )
    for pattern in patterns:
        stripped = re.sub(pattern, "", content, count=1, flags=re.IGNORECASE).strip()
        if stripped and stripped != content:
            return stripped
    return content


def strip_speaker_prefix_once(content: str, prefix_candidates: list[str]) -> str:
    for prefix in prefix_candidates:
        stripped = _strip_one_prefix(content, prefix)
        if stripped != content:
            return stripped
    return content


def sanitize_group_reply_content(agent: Agent, reply_content: str) -> str:
    cleaned = reply_content.strip()
    if not cleaned:
        return cleaned

    prefix_candidates = [agent.name.strip(), agent.id.strip()]
    for _ in range(GROUP_REPLY_PREFIX_MAX_STRIPS):
        updated = strip_speaker_prefix_once(cleaned, prefix_candidates)
        if updated == cleaned:
            break
        cleaned = updated
    return cleaned
