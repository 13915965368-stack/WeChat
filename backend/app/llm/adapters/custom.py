from __future__ import annotations

from app.llm.adapters.openai_compatible import OpenAICompatibleAdapter


class CustomCompatibleAdapter(OpenAICompatibleAdapter):
    adapter_name = "custom-compatible"
