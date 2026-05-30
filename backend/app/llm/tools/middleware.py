from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.llm.schemas import ToolResult, ToolRuntimeContext
from app.llm.tools.spec import ToolSpec
from app.llm.tools.validation import validate_tool_arguments


@dataclass(slots=True)
class ToolCallContext:
    spec: ToolSpec
    arguments: dict[str, Any]
    runtime_context: ToolRuntimeContext | None = None


class ToolMiddleware(Protocol):
    def before_call(self, ctx: ToolCallContext) -> ToolCallContext: ...

    def after_call(self, ctx: ToolCallContext, result: ToolResult) -> ToolResult: ...

    def on_error(self, ctx: ToolCallContext, error: Exception) -> ToolResult | None: ...


@dataclass(slots=True)
class MiddlewarePipeline:
    middlewares: list[ToolMiddleware] = field(default_factory=list)

    def run_before(self, ctx: ToolCallContext) -> ToolCallContext:
        for middleware in self.middlewares:
            ctx = middleware.before_call(ctx)
        return ctx

    def run_after(self, ctx: ToolCallContext, result: ToolResult) -> ToolResult:
        for middleware in reversed(self.middlewares):
            result = middleware.after_call(ctx, result)
        return result

    def run_error(self, ctx: ToolCallContext, error: Exception) -> ToolResult | None:
        for middleware in reversed(self.middlewares):
            handled = middleware.on_error(ctx, error)
            if handled is not None:
                return handled
        return None


class ValidationMiddleware:
    def before_call(self, ctx: ToolCallContext) -> ToolCallContext:
        validation = validate_tool_arguments(ctx.spec, ctx.arguments)
        if not validation.ok:
            raise ValueError(validation.error_message)
        ctx.arguments = validation.data
        return ctx

    def after_call(self, ctx: ToolCallContext, result: ToolResult) -> ToolResult:
        return result

    def on_error(self, ctx: ToolCallContext, error: Exception) -> ToolResult | None:
        if isinstance(error, ValueError):
            return ToolResult(
                text=f"Error validating tool '{ctx.spec.name}' arguments: {error}",
                is_error=True,
            )
        return None
