from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Mapping
from typing import Any, Callable

from aicad.core.schema_validation import check_json_schema, validate_json_arguments


class ToolRisk(StrEnum):
    READ = "read"
    MODIFY = "modify"
    EXPORT = "export"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    risk: ToolRisk
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    compensatable: bool = False
    family: str = "general"
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    essential: bool = False
    canonical_order: int = 1000


class ToolInputError(ValueError):
    """Raised before a handler runs when tool arguments do not match its schema."""


class ToolConfirmationRequired(PermissionError):
    """Raised when a risky tool is called without an explicit confirmation."""


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(
        self, spec: ToolSpec, handler: Callable[..., Any] | None = None
    ) -> None:
        if spec.name in self._specs:
            raise ValueError(f"Tool already registered: {spec.name}")
        check_json_schema(spec.name, spec.input_schema)
        if spec.output_schema is not None:
            check_json_schema(f"{spec.name} output", spec.output_schema)
        self._specs[spec.name] = spec
        if handler is not None:
            self._handlers[spec.name] = handler

    def list_specs(self) -> tuple[ToolSpec, ...]:
        return tuple(self._specs.values())

    def get_spec(self, name: str) -> ToolSpec:
        if name not in self._specs:
            raise KeyError(f"Unknown tool: {name}")
        return self._specs[name]

    def bind(self, name: str, handler: Callable[..., Any]) -> None:
        self.get_spec(name)
        if name in self._handlers:
            raise ValueError(f"Tool already has a connected handler: {name}")
        self._handlers[name] = handler

    def has_handler(self, name: str) -> bool:
        self.get_spec(name)
        return name in self._handlers

    def execute(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        confirmed: bool = False,
    ) -> Any:
        spec = self.get_spec(name)
        if name not in self._handlers:
            raise RuntimeError(f"Tool has no connected handler: {name}")
        if spec.risk is not ToolRisk.READ and not confirmed:
            raise ToolConfirmationRequired(
                f"Tool requires explicit confirmation: {name}"
            )
        checked_arguments = self.validate_arguments(name, arguments)
        return self._handlers[name](**checked_arguments)

    def validate_arguments(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate one call without executing or requiring a connected handler."""

        spec = self.get_spec(name)
        if arguments is None:
            checked_arguments: dict[str, Any] = {}
        elif isinstance(arguments, Mapping):
            checked_arguments = dict(arguments)
        else:
            raise ToolInputError(f"Arguments for {name} must be an object.")
        validate_json_arguments(spec.name, spec.input_schema, checked_arguments)
        return checked_arguments



def build_default_registry() -> ToolRegistry:
    """Build the provider-neutral catalog without importing a CAD backend."""

    from aicad.core.tool_catalog import default_tool_specs

    registry = ToolRegistry()
    for spec in default_tool_specs():
        registry.register(spec)
    return registry
