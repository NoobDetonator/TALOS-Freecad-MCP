from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


def check_json_schema(tool_name: str, schema: Mapping[str, Any]) -> None:
    """Fail during registry construction when a published schema is invalid."""

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"Invalid JSON Schema published by {tool_name}.") from exc


def _reject_non_finite(value: Any, path: str = "arguments") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} must contain only finite numbers.")
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _reject_non_finite(nested, f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, nested in enumerate(value):
            _reject_non_finite(nested, f"{path}[{index}]")


def _path(error: ValidationError, tool_name: str) -> str:
    return ".".join(str(item) for item in error.absolute_path) or tool_name


def _message(error: ValidationError, tool_name: str) -> str:
    subject = _path(error, tool_name)
    validator = error.validator
    if validator == "required":
        missing = sorted(set(error.validator_value) - set(error.instance))
        return f"Missing required arguments for {tool_name}: {', '.join(missing)}"
    if validator == "additionalProperties":
        allowed = set(error.schema.get("properties", {}))
        unexpected = sorted(set(error.instance) - allowed)
        return f"Unexpected arguments for {tool_name}: {', '.join(unexpected)}"
    if validator == "type":
        expected = error.validator_value
        if isinstance(expected, list):
            expected = " or ".join(expected)
        article = "an" if str(expected) in {"array", "object", "integer"} else "a"
        return f"{subject} must be {article} {expected}."
    if validator == "enum":
        # Echoing the values lets an agent correct the argument on the first
        # retry instead of re-reading the schema; enums here are small, but a
        # bound keeps a future large enum from flooding the message.
        allowed_values = list(error.validator_value)
        listed = ", ".join(str(item) for item in allowed_values[:12])
        if len(allowed_values) > 12:
            listed += ", …"
        return f"{subject} must be one of the allowed values: {listed}."
    if validator == "uniqueItems":
        return f"{subject} items must be unique."
    if validator == "minimum":
        return f"{subject} must be at least {error.validator_value}."
    if validator == "exclusiveMinimum":
        return f"{subject} must be greater than {error.validator_value}."
    if validator == "maximum":
        return f"{subject} must be at most {error.validator_value}."
    if validator == "exclusiveMaximum":
        return f"{subject} must be less than {error.validator_value}."
    if validator == "minItems":
        return f"{subject} requires at least {error.validator_value} items."
    if validator == "maxItems":
        return f"{subject} accepts at most {error.validator_value} items."
    if validator == "minLength":
        return f"{subject} is too short."
    if validator == "maxLength":
        return f"{subject} is too long."
    if validator == "pattern":
        return f"{subject} has an invalid format."
    return f"Arguments for {tool_name} do not match the published schema."


def validate_json_arguments(
    tool_name: str,
    schema: Mapping[str, Any],
    arguments: Mapping[str, Any],
) -> None:
    """Validate complete Draft 2020-12 JSON Schema, including nested values."""

    try:
        _reject_non_finite(arguments)
    except ValueError as exc:
        from talos.core.tool_registry import ToolInputError

        raise ToolInputError(str(exc)) from exc
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(arguments),
        key=lambda item: (
            tuple(str(part) for part in item.absolute_path),
            tuple(str(part) for part in item.absolute_schema_path),
        ),
    )
    if errors:
        from talos.core.tool_registry import ToolInputError

        raise ToolInputError(_message(errors[0], tool_name))


__all__ = ["check_json_schema", "validate_json_arguments"]
