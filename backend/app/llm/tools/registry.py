from __future__ import annotations

import inspect
import threading
from typing import Any, Callable

from app.llm.schemas import ToolResult, ToolRuntimeContext
from app.llm.tools.middleware import MiddlewarePipeline, ToolCallContext, ToolMiddleware, ValidationMiddleware
from app.llm.tools.spec import ToolSpec, tool_spec_from_legacy

_TOOL_DEFINITIONS: list[ToolDefinition] = []
_TOOL_EXECUTORS: dict[str, Callable[..., object]] = {}
_TOOL_AVAILABILITY: dict[str, Callable[[ToolRuntimeContext], bool]] = {}
_TOOL_SPECS: dict[str, ToolSpec] = {}
_TOOL_MIDDLEWARES: list[ToolMiddleware] = []
TOOL_EXECUTION_TIMEOUT_SECONDS = 30


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, dict[str, Any]],
    required: list[str],
    executor: Callable[..., object],
    availability_resolver: Callable[[ToolRuntimeContext], bool] | None = None,
) -> None:
    register_tool_spec(
        tool_spec_from_legacy(
            name=name,
            description=description,
            parameters=parameters,
            required=required,
            executor=executor,
            availability_resolver=availability_resolver,
        )
    )


def register_tool_spec(spec: ToolSpec) -> None:
    _TOOL_SPECS[spec.name] = spec
    _TOOL_DEFINITIONS[:] = [item.to_definition() for item in _TOOL_SPECS.values()]
    _TOOL_EXECUTORS[spec.name] = spec.executor
    if spec.availability_resolver is not None:
        _TOOL_AVAILABILITY[spec.name] = spec.availability_resolver
    elif spec.name in _TOOL_AVAILABILITY:
        del _TOOL_AVAILABILITY[spec.name]


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


def register_tool_middleware(middleware: ToolMiddleware) -> None:
    _TOOL_MIDDLEWARES.append(middleware)


def _executor_accepts_context(executor: Callable[..., object]) -> bool:
    try:
        signature = inspect.signature(executor)
    except (TypeError, ValueError):
        return False
    return "context" in signature.parameters


def _pipeline() -> MiddlewarePipeline:
    return MiddlewarePipeline(middlewares=[ValidationMiddleware(), *_TOOL_MIDDLEWARES])


def _run_with_timeout(fn: Callable[[], Any], timeout_seconds: int) -> tuple[bool, Any]:
    box: dict[str, Any] = {}

    def _runner() -> None:
        try:
            box["result"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        return False, None
    if "error" in box:
        raise box["error"]
    return True, box.get("result")


def execute_tool_full(
    name: str,
    arguments: dict[str, Any],
    context: ToolRuntimeContext | None = None,
) -> ToolResult:
    spec = _TOOL_SPECS.get(name)
    if spec is None:
        return ToolResult(text=f"Error: unknown tool '{name}'", is_error=True)
    executor = spec.executor
    call_ctx = ToolCallContext(spec=spec, arguments=dict(arguments), runtime_context=context)
    pipeline = _pipeline()

    def _call() -> Any:
        normalized_arguments = call_ctx.arguments
        if context is not None and _executor_accepts_context(executor):
            return executor(context=context, **normalized_arguments)
        return executor(**normalized_arguments)

    try:
        call_ctx = pipeline.run_before(call_ctx)
        completed, raw = _run_with_timeout(_call, TOOL_EXECUTION_TIMEOUT_SECONDS)
    except Exception as exc:
        handled = pipeline.run_error(call_ctx, exc)
        if handled is not None:
            return handled
        return ToolResult(text=f"Error executing tool '{name}': {exc}", is_error=True)
    if not completed:
        result = ToolResult(
            text=f"Error: tool '{name}' timeout after {TOOL_EXECUTION_TIMEOUT_SECONDS}s",
            is_error=True,
        )
        return pipeline.run_after(call_ctx, result)
    if isinstance(raw, ToolResult):
        result = raw
    else:
        result = ToolResult(text=str(raw), is_error=False)
    return pipeline.run_after(call_ctx, result)


def execute_tool(name: str, arguments: dict[str, Any], context: ToolRuntimeContext | None = None) -> str:
    return execute_tool_full(name, arguments, context).text


def clear_tools() -> None:
    _TOOL_DEFINITIONS.clear()
    _TOOL_EXECUTORS.clear()
    _TOOL_AVAILABILITY.clear()
    _TOOL_SPECS.clear()
    _TOOL_MIDDLEWARES.clear()
