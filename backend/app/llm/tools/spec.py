from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

from app.llm.schemas import ToolDefinition, ToolParameterProperty, ToolParameters, ToolRuntimeContext


@dataclass(slots=True)
class ToolParameterSpec:
    name: str
    type: str
    description: str = ""
    required: bool = False
    enum: list[Any] | None = None
    items: dict[str, Any] | None = None
    default: Any | None = None


@dataclass(slots=True)
class ToolExecutionPolicy:
    timeout_seconds: int = 30
    retry_enabled: bool = False
    max_retries: int = 0
    retry_backoff_seconds: float = 0.0
    allow_parallel: bool = True


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: list[ToolParameterSpec]
    executor: Callable[..., object]
    args_model: type[BaseModel] | None = None
    availability_resolver: Callable[[ToolRuntimeContext], bool] | None = None
    visibility: str = "global"
    tags: list[str] = field(default_factory=list)
    policy: ToolExecutionPolicy = field(default_factory=ToolExecutionPolicy)

    def to_definition(self) -> ToolDefinition:
        properties = {
            item.name: ToolParameterProperty(
                type=item.type,
                description=item.description,
                enum=item.enum,
                items=item.items,
                default=item.default,
            )
            for item in self.parameters
        }
        required = [item.name for item in self.parameters if item.required]
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=ToolParameters(properties=properties, required=required),
        )

    def to_legacy_config(self) -> dict[str, Any]:
        required = [item.name for item in self.parameters if item.required]
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                item.name: {
                    "type": item.type,
                    "description": item.description,
                    "enum": item.enum,
                    "items": item.items,
                    "default": item.default,
                }
                for item in self.parameters
            },
            "required": required,
            "executor": self.executor,
            "availability_resolver": self.availability_resolver,
        }


def tool_spec_from_legacy(
    *,
    name: str,
    description: str,
    parameters: dict[str, dict[str, Any]],
    required: list[str],
    executor: Callable[..., object],
    availability_resolver: Callable[[ToolRuntimeContext], bool] | None = None,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        parameters=[
            ToolParameterSpec(
                name=param_name,
                type=str(config.get("type", "string")),
                description=str(config.get("description", "")),
                required=param_name in required,
                enum=config.get("enum"),
                items=config.get("items"),
                default=config.get("default"),
            )
            for param_name, config in parameters.items()
        ],
        executor=executor,
        availability_resolver=availability_resolver,
    )
