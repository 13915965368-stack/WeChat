from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class ToolServices:
    """Legacy service container exposed to tool executors.

    P0 之后新能力优先通过 ToolCapabilities 挂载；本类型继续保留，
    作为兼容外壳承载请求级 db session factory。
    """

    db_session_factory: Callable[[], object] | None = None
