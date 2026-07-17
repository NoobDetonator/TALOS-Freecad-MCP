from __future__ import annotations

import math
import os
import sys
from pathlib import Path


project_root = Path(os.environ["AICAD_PROJECT_ROOT"])
sys.path.insert(0, str(project_root / "src"))

import FreeCAD as App

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry


for document_name in list(App.listDocuments()):
    App.closeDocument(document_name)

document = App.newDocument("PartDesignSmoke")
document.UndoMode = 1
adapter = FreeCadAdapter()
registry = build_cad_tool_registry(adapter)


def modify(name: str, arguments: dict):
    return registry.execute(name, arguments, confirmed=True)


def read(name: str, arguments: dict):
    return registry.execute(name, arguments)


def close(expected: float, actual: float, tolerance: float = 0.01) -> bool:
    return abs(actual - expected) <= abs(expected) * tolerance


# --- Body and attached base sketch ---------------------------------------

body = modify("cad.create_body", {"name": "MainBody"})
assert body["valid"] is True

base_sketch = modify(
    "cad.create_body_sketch",
    {"body": "MainBody", "plane": "xy", "name": "BaseSketch"},
)
assert base_sketch["body"] == "MainBody"
assert base_sketch["plane"] == "xy"

rectangle = modify(
    "cad.add_sketch_rectangle",
    {"sketch": "BaseSketch", "x": -30, "y": -20, "width": 60, "height": 40},
)
assert rectangle["closed_wire_count"] == 1

# --- Sketch status before and after dimensioning --------------------------

status = read("cad.get_sketch_status", {"sketch": "BaseSketch"})
assert status["fully_constrained"] is False
assert status["solver_status"] == 0
assert status["geometry_count"] == 4
if status["degrees_of_freedom"] is not None:
    assert status["degrees_of_freedom"] > 0
assert status["underconstrained_geometry"]

modify(
    "cad.add_sketch_dimensional_constraint",
    {
        "sketch": "BaseSketch",
        "constraint_type": "length",
        "geometry": 0,
        "value": 60,
    },
)
after_width = read("cad.get_sketch_status", {"sketch": "BaseSketch"})
if (
    status["degrees_of_freedom"] is not None
    and after_width["degrees_of_freedom"] is not None
):
    assert after_width["degrees_of_freedom"] < status["degrees_of_freedom"]

# --- Parametric pad -------------------------------------------------------

pad = modify("cad.add_pad", {"sketch": "BaseSketch", "length": 10})
assert pad["feature_type"] == "PartDesign::Pad"
assert pad["body"] == "MainBody"
assert close(60 * 40 * 10, pad["volume_mm3"]), pad["volume_mm3"]

# --- Through-all pocket from a second attached sketch ---------------------

modify(
    "cad.create_body_sketch",
    {"body": "MainBody", "plane": "xy", "name": "HoleSketch"},
)
modify(
    "cad.add_sketch_circle",
    {"sketch": "HoleSketch", "center_x": 10, "center_y": 10, "radius": 5},
)
radius_constraint = modify(
    "cad.add_sketch_dimensional_constraint",
    {
        "sketch": "HoleSketch",
        "constraint_type": "radius",
        "geometry": 0,
        "value": 5,
    },
)


def hole_area(radius: float) -> float:
    return math.pi * radius * radius


pocket = modify(
    "cad.add_pocket",
    {"sketch": "HoleSketch", "length": 1, "through_all": True, "reversed": True},
)
assert close(60 * 40 * 10 - hole_area(5) * 10, pocket["volume_mm3"]), pocket[
    "volume_mm3"
]

# --- Edit the pad by dimension: the whole tree recomputes -----------------

edited = modify(
    "cad.edit_feature", {"feature": "AIPad", "properties": {"length": 20}}
)
assert close(60 * 40 * 20 - hole_area(5) * 20, edited["volume_mm3"]), edited[
    "volume_mm3"
]

# --- Change the hole radius by datum: unique solution, deterministic ------

datum = modify(
    "cad.set_sketch_datum",
    {
        "sketch": "HoleSketch",
        "constraint": radius_constraint["added_constraint"],
        "value": 4,
    },
)
assert datum["constraint_type"] == "Radius"
after_datum = read("cad.measure_object", {"object": "MainBody"})
assert close(60 * 40 * 20 - hole_area(4) * 20, after_datum["volume_mm3"]), (
    after_datum["volume_mm3"]
)

# --- Linear pattern of the pocket along X ---------------------------------

pattern = modify(
    "cad.add_linear_pattern",
    {
        "features": ["AIPocket"],
        "direction": "x",
        "length": 15,
        "occurrences": 2,
    },
)
assert close(60 * 40 * 20 - 2 * hole_area(4) * 20, pattern["volume_mm3"]), (
    pattern["volume_mm3"]
)

# --- Mirrored pattern of the pocket across XZ -----------------------------

mirrored = modify(
    "cad.add_mirrored_pattern",
    {"features": ["AIPocket"], "plane": "xz"},
)
assert mirrored["volume_mm3"] < pattern["volume_mm3"], mirrored["volume_mm3"]

# --- Revolution in a second body around the sketch vertical axis ----------

modify("cad.create_body", {"name": "RingBody"})
modify(
    "cad.create_body_sketch",
    {"body": "RingBody", "plane": "xz", "name": "RingProfile"},
)
modify(
    "cad.add_sketch_rectangle",
    {"sketch": "RingProfile", "x": 10, "y": 0, "width": 4, "height": 6},
)
revolution = modify(
    "cad.add_revolution",
    {
        "body": "RingBody",
        "sketch": "RingProfile",
        "angle": 360,
        "axis": "vertical",
    },
)
ring_expected = 2 * math.pi * 12 * (4 * 6)
assert close(ring_expected, revolution["volume_mm3"]), revolution["volume_mm3"]

# --- Guard rails ----------------------------------------------------------

try:
    modify("cad.add_pad", {"sketch": "RingProfile", "length": 5, "body": "MainBody"})
    raise AssertionError("A sketch outside the body must be rejected.")
except ValueError:
    pass

try:
    modify(
        "cad.edit_feature",
        {"feature": "AIPad", "properties": {"angle": 90}},
    )
    raise AssertionError("A property outside the type allowlist must be rejected.")
except ValueError:
    pass

undo = modify("cad.undo", {})
assert undo["undone"] is True

print("FREECAD_PARTDESIGN_SMOKE_OK")
