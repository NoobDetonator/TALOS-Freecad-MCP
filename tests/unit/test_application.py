from typing import Any

from aicad.application import build_cad_tool_registry


class FakeCadAdapter:
    def get_document_summary(self) -> dict[str, Any]:
        return {"active": False}

    def get_selection(self) -> dict[str, Any]:
        return {"selection": []}

    def create_box(
        self, length: float, width: float, height: float, name: str = "AIBox"
    ) -> dict[str, Any]:
        return {"name": name, "dimensions": [length, width, height]}

    def validate_document(self) -> dict[str, Any]:
        return {"valid": True, "errors": []}

    def undo(self) -> dict[str, bool]:
        return {"undone": True}


def test_application_connects_every_shared_tool_to_one_adapter() -> None:
    registry = build_cad_tool_registry(FakeCadAdapter())
    assert all(registry.has_handler(spec.name) for spec in registry.list_specs())
    result = registry.execute(
        "cad.create_box",
        {"length": 1, "width": 2, "height": 3, "name": "TestBox"},
        confirmed=True,
    )
    assert result == {"name": "TestBox", "dimensions": [1, 2, 3]}
