from __future__ import annotations

import pytest

from aicad.core.partdesign_registry import (
    PARTDESIGN_FEATURES,
    editable_property_union,
    feature_by_tool,
    feature_by_type,
)
from aicad.core.schema_validation import check_json_schema, validate_json_arguments
from aicad.core.tool_registry import (
    ToolInputError,
    ToolRisk,
    build_default_registry,
)


def test_registry_rows_are_unique_and_complete() -> None:
    tool_names = [definition.tool_name for definition in PARTDESIGN_FEATURES]
    freecad_types = [definition.freecad_type for definition in PARTDESIGN_FEATURES]

    assert len(set(tool_names)) == len(PARTDESIGN_FEATURES)
    assert len(set(freecad_types)) == len(PARTDESIGN_FEATURES)
    for definition in PARTDESIGN_FEATURES:
        assert definition.freecad_type.startswith("PartDesign::")
        assert definition.profile in {"sketch", "features"}
        assert definition.default_name
        assert "{" in definition.description  # embedded JSON call example


def test_generated_schemas_are_valid_and_closed() -> None:
    for definition in PARTDESIGN_FEATURES:
        schema = definition.input_schema()
        check_json_schema(definition.tool_name, schema)
        assert schema["additionalProperties"] is False
        if definition.profile == "sketch":
            assert "sketch" in schema["required"]
        else:
            assert "features" in schema["properties"]


def test_pad_schema_validates_arguments_like_a_handwritten_tool() -> None:
    schema = feature_by_tool("cad.add_pad").input_schema()

    validate_json_arguments(
        "cad.add_pad", schema, {"sketch": "Base", "length": 8.5}
    )
    with pytest.raises(ToolInputError):
        validate_json_arguments(
            "cad.add_pad", schema, {"sketch": "Base", "length": 0}
        )
    with pytest.raises(ToolInputError):
        validate_json_arguments(
            "cad.add_pad",
            schema,
            {"sketch": "Base", "length": 5, "surprise": True},
        )


def test_catalog_exposes_every_registered_feature_as_a_tool() -> None:
    registry = build_default_registry()
    for definition in PARTDESIGN_FEATURES:
        spec = registry.get_spec(definition.tool_name)
        assert spec.family == "partdesign"
        assert spec.risk is ToolRisk.MODIFY
        assert spec.compensatable is True
        assert spec.input_schema == definition.input_schema()

    status_spec = registry.get_spec("cad.get_sketch_status")
    assert status_spec.risk is ToolRisk.READ


def test_lookup_helpers_reject_unknown_entries() -> None:
    assert feature_by_type("PartDesign::Pad").tool_name == "cad.add_pad"
    with pytest.raises(KeyError):
        feature_by_tool("cad.add_teleporter")
    with pytest.raises(KeyError):
        feature_by_type("PartDesign::Teleporter")


def test_editable_union_only_contains_registered_scalars() -> None:
    union = editable_property_union()
    scalars = {
        prop.argument
        for definition in PARTDESIGN_FEATURES
        for prop in definition.properties
    }

    assert set(union) == scalars
    assert "sketch" not in union
    assert "features" not in union
