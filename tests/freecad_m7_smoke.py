from __future__ import annotations

import hashlib
import os
import shutil
import sys
import uuid
from pathlib import Path


project_root = Path(os.environ["AICAD_PROJECT_ROOT"])
sys.path.insert(0, str(project_root / "src"))

import FreeCAD as App

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry


for document_name in list(App.listDocuments()):
    App.closeDocument(document_name)

adapter = FreeCadAdapter()
registry = build_cad_tool_registry(adapter)

work_dir = project_root / ".runtime" / f"m7-smoke-{uuid.uuid4().hex[:8]}"
work_dir.mkdir(parents=True)
try:
    created = registry.execute(
        "cad.new_document", {"name": "PecaA"}, confirmed=True
    )
    assert created["name"] == "PecaA"
    assert created["active"] is True
    registry.execute(
        "cad.create_box",
        {"length": 10, "width": 10, "height": 10, "name": "CuboA"},
        confirmed=True,
    )

    registry.execute("cad.new_document", {"name": "PecaB"}, confirmed=True)
    listing = registry.execute("cad.list_documents")
    names = {item["name"] for item in listing["documents"]}
    assert {"PecaA", "PecaB"} <= names
    assert listing["active_document"] == "PecaB"

    duplicate_refused = False
    try:
        registry.execute("cad.new_document", {"name": "PecaA"}, confirmed=True)
    except ValueError:
        duplicate_refused = True
    assert duplicate_refused

    switched = registry.execute(
        "cad.set_active_document", {"document": "PecaA"}, confirmed=True
    )
    assert switched["name"] == "PecaA"
    summary = registry.execute("cad.get_document_summary")
    assert summary["name"] == "PecaA"
    assert any(item["name"] == "CuboA" for item in summary["objects"])

    unsaved_refused = False
    try:
        registry.execute("cad.save_document", {}, confirmed=True)
    except ValueError:
        unsaved_refused = True
    assert unsaved_refused

    destination = work_dir / "peca-a.FCStd"
    saved = registry.execute(
        "cad.save_document", {"destination": str(destination)}, confirmed=True
    )
    assert destination.is_file()
    payload = destination.read_bytes()
    assert saved["size_bytes"] == len(payload) > 0
    assert saved["sha256"] == hashlib.sha256(payload).hexdigest()

    resaved = registry.execute("cad.save_document", {}, confirmed=True)
    assert resaved["destination"] == str(destination)

    overwrite_refused = False
    try:
        registry.execute(
            "cad.save_document",
            {"destination": str(destination)},
            confirmed=True,
        )
    except FileExistsError:
        overwrite_refused = True
    assert overwrite_refused
finally:
    for document_name in list(App.listDocuments()):
        App.closeDocument(document_name)
    shutil.rmtree(work_dir, ignore_errors=True)

print("FREECAD_M7_SMOKE_OK")
