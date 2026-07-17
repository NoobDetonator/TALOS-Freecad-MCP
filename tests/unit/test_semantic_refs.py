from __future__ import annotations

import pytest

from aicad.core.schema_validation import check_json_schema
from aicad.core.semantic_refs import (
    EDGE_SELECTOR_SCHEMA,
    FACE_SELECTOR_SCHEMA,
    axis_vector,
    parse_edge_selector,
    parse_face_selector,
)


def test_selector_schemas_are_valid_json_schema() -> None:
    check_json_schema("face selector", FACE_SELECTOR_SCHEMA)
    check_json_schema("edge selector", EDGE_SELECTOR_SCHEMA)


def test_face_selector_parsing() -> None:
    largest = parse_face_selector(
        {"kind": "largest_planar_face", "normal": "+z"}
    )
    assert largest.kind == "largest_planar_face"
    assert largest.normal == "+z"

    named = parse_face_selector({"kind": "named_face", "name": "Face3"})
    assert named.name == "Face3"

    with pytest.raises(ValueError):
        parse_face_selector({"kind": "largest_planar_face", "normal": "up"})
    with pytest.raises(ValueError):
        parse_face_selector({"kind": "named_face"})
    with pytest.raises(ValueError):
        parse_face_selector({"kind": "prettiest_face"})
    with pytest.raises(ValueError):
        parse_face_selector("Face3")


def test_edge_selector_parsing() -> None:
    circular = parse_edge_selector({"kind": "circular_edges", "diameter": 8})
    assert circular.diameter == 8
    assert circular.tolerance > 0

    boundary = parse_edge_selector(
        {
            "kind": "face_boundary",
            "face": {"kind": "largest_planar_face", "normal": "+z"},
        }
    )
    assert boundary.face is not None
    assert boundary.face.normal == "+z"

    named = parse_edge_selector(
        {"kind": "named_edges", "names": ["Edge2", "Edge5"]}
    )
    assert named.names == ("Edge2", "Edge5")

    with pytest.raises(ValueError):
        parse_edge_selector({"kind": "circular_edges"})
    with pytest.raises(ValueError):
        parse_edge_selector({"kind": "circular_edges", "diameter": -1})
    with pytest.raises(ValueError):
        parse_edge_selector({"kind": "face_boundary"})
    with pytest.raises(ValueError):
        parse_edge_selector({"kind": "named_edges", "names": []})
    with pytest.raises(ValueError):
        parse_edge_selector(
            {"kind": "named_edges", "names": ["Edge1", "Edge1"]}
        )


def test_axis_vectors_are_unit_length() -> None:
    assert axis_vector("+z") == (0.0, 0.0, 1.0)
    assert axis_vector("-x") == (-1.0, 0.0, 0.0)
    assert axis_vector("+y") == (0.0, 1.0, 0.0)
