from __future__ import annotations

from dataclasses import dataclass

from app.llm.tools.tool_services import ToolServices
from app.services.search_types import SearchRuntimeConfigSnapshot


@dataclass(slots=True)
class SearchCapability:
    config: SearchRuntimeConfigSnapshot


@dataclass(slots=True)
class ToolCapabilities:
    search: SearchCapability | None = None
    services: ToolServices | None = None
