"""Semantic face and edge selectors resolved against a Body at execution.

A selector names topology by geometric role ("the largest planar face whose
normal points +Z", "circular edges of diameter 6") instead of by internal
FreeCAD element names, which change when the feature tree recomputes. A
selector that cannot be revalidated fails as stale; it never silently picks a
different element.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


AXIS_DIRECTIONS = ("+x", "-x", "+y", "-y", "+z", "-z")
DEFAULT_DIAMETER_TOLERANCE_MM = 0.25

FACE_SELECTOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["largest_planar_face", "named_face"],
        },
        "normal": {"type": "string", "enum": list(AXIS_DIRECTIONS)},
        "name": {
            "type": "string",
            "pattern": "^Face[1-9][0-9]{0,4}$",
        },
    },
    "required": ["kind"],
    "additionalProperties": False,
}

EDGE_SELECTOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["circular_edges", "face_boundary", "named_edges"],
        },
        "diameter": {"type": "number", "exclusiveMinimum": 0, "maximum": 10000},
        "tolerance": {"type": "number", "exclusiveMinimum": 0, "maximum": 10},
        "face": FACE_SELECTOR_SCHEMA,
        "names": {
            "type": "array",
            "items": {
                "type": "string",
                "pattern": "^Edge[1-9][0-9]{0,4}$",
            },
            "minItems": 1,
            "maxItems": 64,
            "uniqueItems": True,
        },
    },
    "required": ["kind"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class FaceSelector:
    kind: str
    normal: str | None = None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class EdgeSelector:
    kind: str
    diameter: float | None = None
    tolerance: float = DEFAULT_DIAMETER_TOLERANCE_MM
    face: FaceSelector | None = None
    names: tuple[str, ...] = ()


def parse_face_selector(value: Any) -> FaceSelector:
    if not isinstance(value, dict):
        raise ValueError("A face selector must be an object.")
    kind = value.get("kind")
    if kind == "largest_planar_face":
        normal = value.get("normal")
        if normal is not None and normal not in AXIS_DIRECTIONS:
            allowed = ", ".join(AXIS_DIRECTIONS)
            raise ValueError(f"Face selector normal must be one of: {allowed}.")
        return FaceSelector(kind="largest_planar_face", normal=normal)
    if kind == "named_face":
        name = value.get("name")
        if not isinstance(name, str) or not name.startswith("Face"):
            raise ValueError("A named_face selector requires a FaceN name.")
        return FaceSelector(kind="named_face", name=name)
    raise ValueError("Unsupported face selector kind.")


def parse_edge_selector(value: Any) -> EdgeSelector:
    if not isinstance(value, dict):
        raise ValueError("An edge selector must be an object.")
    kind = value.get("kind")
    if kind == "circular_edges":
        diameter = value.get("diameter")
        if not isinstance(diameter, (int, float)) or isinstance(diameter, bool):
            raise ValueError("circular_edges requires a numeric diameter.")
        if diameter <= 0:
            raise ValueError("circular_edges requires a positive diameter.")
        tolerance = value.get("tolerance", DEFAULT_DIAMETER_TOLERANCE_MM)
        if (
            not isinstance(tolerance, (int, float))
            or isinstance(tolerance, bool)
            or tolerance <= 0
        ):
            raise ValueError("circular_edges tolerance must be positive.")
        return EdgeSelector(
            kind="circular_edges",
            diameter=float(diameter),
            tolerance=float(tolerance),
        )
    if kind == "face_boundary":
        face = value.get("face")
        if face is None:
            raise ValueError("face_boundary requires a nested face selector.")
        return EdgeSelector(kind="face_boundary", face=parse_face_selector(face))
    if kind == "named_edges":
        names = value.get("names")
        if (
            not isinstance(names, list)
            or not names
            or any(
                not isinstance(item, str) or not item.startswith("Edge")
                for item in names
            )
        ):
            raise ValueError("named_edges requires a list of EdgeN names.")
        if len(set(names)) != len(names):
            raise ValueError("named_edges names must be unique.")
        return EdgeSelector(kind="named_edges", names=tuple(names))
    raise ValueError("Unsupported edge selector kind.")


def axis_vector(direction: str) -> tuple[float, float, float]:
    """Unit vector for one of the six axis directions."""

    sign = 1.0 if direction[0] == "+" else -1.0
    axis = direction[1]
    return (
        (sign, 0.0, 0.0)
        if axis == "x"
        else (0.0, sign, 0.0) if axis == "y" else (0.0, 0.0, sign)
    )
