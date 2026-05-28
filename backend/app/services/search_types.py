from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SearchItem:
    title: str
    url: str
    snippet: str = ""


@dataclass(slots=True)
class SearchAttempt:
    provider: str
    success: bool
    duration_ms: int = 0
    error: str | None = None


@dataclass(slots=True)
class SearchResponse:
    provider: str
    query: str
    items: list[SearchItem] = field(default_factory=list)
    cached: bool = False
    error: str | None = None
    attempts: list[SearchAttempt] = field(default_factory=list)
