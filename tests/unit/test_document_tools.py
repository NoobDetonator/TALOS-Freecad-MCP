from pathlib import Path

import pytest

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.core.tool_registry import (
    ToolConfirmationRequired,
    ToolInputError,
    ToolRisk,
    build_default_registry,
)


def test_document_specs_declare_expected_risks() -> None:
    registry = build_default_registry()
    assert registry.get_spec("cad.list_documents").risk is ToolRisk.READ
    assert registry.get_spec("cad.new_document").risk is ToolRisk.MODIFY
    assert registry.get_spec("cad.set_active_document").risk is ToolRisk.MODIFY
    assert registry.get_spec("cad.save_document").risk is ToolRisk.EXPORT


def test_document_mutations_require_confirmation() -> None:
    registry = build_default_registry()
    registry.bind("cad.new_document", lambda **_: {"valid": True})
    registry.bind("cad.save_document", lambda **_: {"valid": True})
    with pytest.raises(ToolConfirmationRequired):
        registry.execute("cad.new_document", {"name": "Peca"})
    with pytest.raises(ToolConfirmationRequired):
        registry.execute("cad.save_document", {})


def test_document_arguments_are_validated() -> None:
    registry = build_default_registry()
    with pytest.raises(ToolInputError):
        registry.validate_arguments("cad.new_document", {"name": "1invalido"})
    with pytest.raises(ToolInputError):
        registry.validate_arguments("cad.set_active_document", {})
    with pytest.raises(ToolInputError):
        registry.validate_arguments(
            "cad.save_document", {"destination": "x.FCStd", "extra": 1}
        )


def test_new_document_validates_name_before_freecad() -> None:
    adapter = FreeCadAdapter()
    with pytest.raises(ValueError, match="invalid format"):
        adapter.new_document("nome com espaço")


def test_save_document_destination_is_checked_before_freecad(
    tmp_path: Path,
) -> None:
    adapter = FreeCadAdapter()
    with pytest.raises(ValueError, match="absolute"):
        adapter.save_document("relativo.FCStd")
    with pytest.raises(ValueError, match="end with"):
        adapter.save_document(str(tmp_path / "peca.txt"))
    existing = tmp_path / "peca.FCStd"
    existing.write_bytes(b"stub")
    with pytest.raises(FileExistsError):
        adapter.save_document(str(existing))
    with pytest.raises(RuntimeError, match="inside FreeCAD|No active CAD document"):
        adapter.save_document(str(tmp_path / "nova.FCStd"))
