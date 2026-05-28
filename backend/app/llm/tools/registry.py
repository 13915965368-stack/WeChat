from __future__ import annotations

import inspect
from typing import Any, Callable

from app.llm.schemas import ToolDefinition, ToolParameters, ToolParameterProperty, ToolRuntimeContext

_TOOL_DEFINITIONS: list[ToolDefinition] = []
_TOOL_EXECUTORS: dict[str, Callable[..., str]] = {}
_TOOL_AVAILABILITY: dict[str, Callable[[ToolRuntimeContext], bool]] = {}


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, dict[str, str]],
    required: list[str],
    executor: Callable[..., str],
    availability_resolver: Callable[[ToolRuntimeContext], bool] | None = None,
) -> None:
    definition = ToolDefinition(
        name=name,
        description=description,
        parameters=ToolParameters(
            properties={
                k: ToolParameterProperty(type=v.get("type", "string"), description=v.get("description", ""))
                for k, v in parameters.items()
            },
            required=required,
        ),
    )
    _TOOL_DEFINITIONS.append(definition)
    _TOOL_EXECUTORS[name] = executor
    if availability_resolver is not None:
        _TOOL_AVAILABILITY[name] = availability_resolver


def get_tool_definitions(context: ToolRuntimeContext | None = None) -> list[ToolDefinition]:
    if context is None:
        return list(_TOOL_DEFINITIONS)
    visible: list[ToolDefinition] = []
    for definition in _TOOL_DEFINITIONS:
        resolver = _TOOL_AVAILABILITY.get(definition.name)
        if resolver is None or resolver(context):
            visible.append(definition)
    return visible


def get_global_tool_definitions() -> list[ToolDefinition]:
    return get_tool_definitions()


def _executor_accepts_context(executor: Callable[..., str]) -> bool:
    try:
        signature = inspect.signature(executor)
    except (TypeError, ValueError):
        return False
    return "context" in signature.parameters


def execute_tool(name: str, arguments: dict[str, Any], context: ToolRuntimeContext | None = None) -> str:
    executor = _TOOL_EXECUTORS.get(name)
    if executor is None:
        return f"Error: unknown tool '{name}'"
    try:
        if context is not None and _executor_accepts_context(executor):
            return executor(context=context, **arguments)
        return executor(**arguments)
    except Exception as exc:
        return f"Error executing tool '{name}': {exc}"


def clear_tools() -> None:
    _TOOL_DEFINITIONS.clear()
    _TOOL_EXECUTORS.clear()
    _TOOL_AVAILABILITY.clear()
