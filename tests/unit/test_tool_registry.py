import pytest

from aicad.core.tool_registry import (
    ToolConfirmationRequired,
    ToolInputError,
    ToolRegistry,
    ToolRisk,
    ToolSpec,
    build_default_registry,
)


def test_default_registry_has_unique_tools() -> None:
    names = [spec.name for spec in build_default_registry().list_specs()]
    assert len(names) == len(set(names))
    assert "cad.create_box" in names


def test_registry_executes_connected_handler() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test.add",
            description="Add two numbers.",
            risk=ToolRisk.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "left": {"type": "number"},
                    "right": {"type": "number"},
                },
                "required": ["left", "right"],
                "additionalProperties": False,
            },
        ),
        handler=lambda left, right: left + right,
    )
    assert registry.execute("test.add", {"left": 2, "right": 3}) == 5


def test_registry_rejects_duplicate_names() -> None:
    registry = ToolRegistry()
    spec = ToolSpec("test.duplicate", "Duplicate", ToolRisk.READ, {})
    registry.register(spec)
    with pytest.raises(ValueError):
        registry.register(spec)


def test_registry_validates_arguments_before_calling_handler() -> None:
    registry = build_default_registry()
    registry.bind("cad.create_box", lambda **arguments: arguments)
    with pytest.raises(ToolInputError):
        registry.execute(
            "cad.create_box",
            {"length": 10, "width": 20, "height": -1},
            confirmed=True,
        )
    with pytest.raises(ToolInputError):
        registry.execute(
            "cad.create_box",
            {"length": 10, "width": 20, "height": 30, "python": "print(1)"},
            confirmed=True,
        )


def test_registry_requires_confirmation_for_modifications() -> None:
    registry = build_default_registry()
    registry.bind("cad.undo", lambda: {"undone": True})
    with pytest.raises(ToolConfirmationRequired):
        registry.execute("cad.undo")
    assert registry.execute("cad.undo", confirmed=True) == {"undone": True}
