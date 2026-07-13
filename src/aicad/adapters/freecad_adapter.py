from __future__ import annotations

import math
import re
from typing import Any


class FreeCadAdapter:
    """Small, explicit boundary around FreeCAD's Python API."""

    @staticmethod
    def _modules() -> tuple[Any, Any]:
        try:
            import FreeCAD as App
            import Part
        except ImportError as exc:
            raise RuntimeError("This operation must run inside FreeCAD.") from exc
        return App, Part

    @staticmethod
    def _error_states(item: Any) -> list[str]:
        states = [str(state) for state in item.State]
        error_words = ("error", "invalid", "failed", "exception")
        return [
            state for state in states if any(word in state.lower() for word in error_words)
        ]

    def get_document_summary(self) -> dict[str, Any]:
        app, _ = self._modules()
        document = app.ActiveDocument
        if document is None:
            return {"active": False, "name": None, "objects": []}
        return {
            "active": True,
            "name": document.Name,
            "label": document.Label,
            "objects": [
                {
                    "name": item.Name,
                    "label": item.Label,
                    "type_id": item.TypeId,
                    "has_error": bool(self._error_states(item)),
                }
                for item in document.Objects
            ],
        }

    def get_selection(self) -> dict[str, Any]:
        try:
            import FreeCADGui as Gui
        except ImportError as exc:
            raise RuntimeError("This operation must run inside FreeCAD GUI.") from exc

        selection = []
        for selected in Gui.Selection.getSelectionEx():
            item = selected.Object
            selection.append(
                {
                    "name": item.Name,
                    "label": item.Label,
                    "type_id": item.TypeId,
                    "subelements": list(selected.SubElementNames),
                }
            )
        return {"selection": selection}

    def create_box(
        self, length: float, width: float, height: float, name: str = "AIBox"
    ) -> dict[str, Any]:
        dimensions = (float(length), float(width), float(height))
        if any(not math.isfinite(value) or value <= 0 for value in dimensions):
            raise ValueError("All dimensions must be positive.")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name) is None:
            raise ValueError("The object name has an invalid format.")
        app, _ = self._modules()
        document = app.ActiveDocument or app.newDocument("AICadDocument")
        if document.UndoMode == 0:
            document.UndoMode = 1
        document.openTransaction(f"AI CAD: create {name}")
        try:
            box = document.addObject("Part::Box", name)
            box.Label = name
            box.Length, box.Width, box.Height = dimensions
            document.recompute()
            if box.Shape.isNull() or not box.Shape.isValid():
                raise RuntimeError("FreeCAD produced an invalid shape.")
            validation = self._validate_document(document)
            if not validation["valid"]:
                raise RuntimeError(
                    "FreeCAD document validation failed: "
                    + "; ".join(validation["errors"])
                )
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            document.recompute()
            raise
        return {
            "name": box.Name,
            "label": box.Label,
            "dimensions_mm": list(dimensions),
            "volume_mm3": float(box.Shape.Volume),
            "valid": True,
        }

    def _validate_document(self, document: Any) -> dict[str, Any]:
        if document is None:
            return {"valid": False, "errors": ["No active document."]}
        document.recompute()
        errors: list[str] = []
        for item in document.Objects:
            error_states = self._error_states(item)
            if error_states:
                errors.append(f"{item.Name}: {', '.join(error_states)}")
            shape = getattr(item, "Shape", None)
            if shape is not None and not shape.isNull() and not shape.isValid():
                errors.append(f"{item.Name}: invalid shape")
        return {"valid": not errors, "errors": errors}

    def validate_document(self) -> dict[str, Any]:
        app, _ = self._modules()
        return self._validate_document(app.ActiveDocument)

    def undo(self) -> dict[str, bool]:
        app, _ = self._modules()
        document = app.ActiveDocument
        if document is None or document.UndoCount == 0:
            return {"undone": False}
        document.undo()
        document.recompute()
        return {"undone": True}
