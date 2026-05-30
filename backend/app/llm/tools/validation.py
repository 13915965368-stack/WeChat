from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.llm.tools.spec import ToolSpec


@dataclass(slots=True)
class ToolValidationResult:
    ok: bool
    data: dict[str, Any]
    error_message: str = ""


def validate_tool_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> ToolValidationResult:
    model = spec.args_model
    if model is None:
        return ToolValidationResult(ok=True, data=dict(arguments))
    try:
        validated = model.model_validate(arguments)
    except ValidationError as exc:
        return ToolValidationResult(ok=False, data={}, error_message=str(exc))
    return ToolValidationResult(ok=True, data=validated.model_dump())
