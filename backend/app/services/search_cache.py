from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import time

from app.services.search_types import SearchResponse


def normalize_search_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


@dataclass(slots=True)
class _CacheEntry:
    response: SearchResponse
    expires_at: float


class SearchCache:
    def __init__(self, *, max_size: int = 1000) -> None:
        self.max_size = max(1, max_size)
        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()

    def get(self, query: str) -> SearchResponse | None:
        key = normalize_search_query(query)
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.time():
            self._entries.pop(key, None)
            return None
        self._entries.move_to_end(key)
        return entry.response

    def set(self, query: str, response: SearchResponse, ttl_seconds: int) -> None:
        key = normalize_search_query(query)
        self._entries[key] = _CacheEntry(response=response, expires_at=time.time() + max(1, ttl_seconds))
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_size:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()
