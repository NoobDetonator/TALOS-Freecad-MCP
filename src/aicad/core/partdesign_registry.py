"""Governed-reflection registry for parametric Part Design features.

One declarative row per whitelisted PartDesign type replaces a hand-written
tool: the row generates the JSON schema, the capability card and the argument
allowlist the adapter enforces. Nothing outside this registry can be created
through the generic feature path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


NAME_SCHEMA = {
    "type": "string",
    "minLength": 1,
    "maxLength": 64,
    "pattern": "^[A-Za-z][A-Za-z0-9_-]*$",
}
REFERENCE_SCHEMA = {"type": "string", "minLength": 1, "maxLength": 256}


@dataclass(frozen=True, slots=True)
class FeatureProperty:
    """One scalar argument mapped onto a whitelisted FreeCAD property."""

    argument: str
    freecad_property: str
    schema: dict[str, Any]
    required: bool = False


@dataclass(frozen=True, slots=True)
class FeatureAxisChoice:
    """One enum argument resolved by the adapter to a geometric reference."""

    argument: str
    choices: tuple[str, ...]
    kind: str  # "sketch_axis" | "origin_axis" | "origin_plane"
    required: bool = False
    default: str | None = None


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    tool_name: str
    freecad_type: str
    title: str
    description: str
    profile: str  # "sketch" | "features"
    default_name: str
    properties: tuple[FeatureProperty, ...] = ()
    axis: FeatureAxisChoice | None = None
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    canonical_order: int = 1000
    extra_arguments: dict[str, dict[str, Any]] = field(default_factory=dict)

    def input_schema(self) -> dict[str, Any]:
        """Generate the complete JSON input schema for this feature tool."""

        schema_properties: dict[str, Any] = {}
        required: list[str] = []
        if self.profile == "sketch":
            schema_properties["sketch"] = dict(REFERENCE_SCHEMA)
            required.append("sketch")
        else:
            schema_properties["features"] = {
                "type": "array",
                "items": dict(REFERENCE_SCHEMA),
                "minItems": 1,
                "maxItems": 16,
                "uniqueItems": True,
            }
        schema_properties["body"] = dict(REFERENCE_SCHEMA)
        for prop in self.properties:
            schema_properties[prop.argument] = dict(prop.schema)
            if prop.required:
                required.append(prop.argument)
        if self.axis is not None:
            schema_properties[self.axis.argument] = {
                "type": "string",
                "enum": list(self.axis.choices),
            }
            if self.axis.required:
                required.append(self.axis.argument)
        for argument, fragment in self.extra_arguments.items():
            schema_properties[argument] = dict(fragment)
        schema_properties["name"] = dict(NAME_SCHEMA)
        return {
            "type": "object",
            "properties": schema_properties,
            "required": required,
            "additionalProperties": False,
        }

    def scalar_allowlist(self) -> dict[str, FeatureProperty]:
        return {prop.argument: prop for prop in self.properties}


_MM_POSITIVE = {"type": "number", "exclusiveMinimum": 0, "maximum": 10000}
_ANGLE = {"type": "number", "exclusiveMinimum": 0, "maximum": 360}
_BOOL = {"type": "boolean"}


PARTDESIGN_FEATURES: tuple[FeatureDefinition, ...] = (
    FeatureDefinition(
        tool_name="cad.add_pad",
        freecad_type="PartDesign::Pad",
        title="Pad paramétrico",
        description=(
            "Extrude a closed Body sketch into a parametric PartDesign::Pad. "
            "The pad stays linked to the sketch: editing the sketch or the pad "
            "length recomputes the solid, and inner sketch circles become "
            "holes. Example: {\"sketch\": \"Sketch\", \"length\": 8, "
            "\"midplane\": false}."
        ),
        profile="sketch",
        default_name="AIPad",
        properties=(
            FeatureProperty("length", "Length", _MM_POSITIVE, required=True),
            FeatureProperty("midplane", "Midplane", _BOOL),
            FeatureProperty("reversed", "Reversed", _BOOL),
        ),
        aliases=("pad", "extrusão paramétrica", "parametric extrude"),
        tags=("partdesign", "body", "extrudar", "extrude", "paramétrico"),
        examples=(
            "Faça um pad de 8 mm do sketch da base.",
            "Pad the base sketch by 8 mm.",
        ),
        canonical_order=520,
    ),
    FeatureDefinition(
        tool_name="cad.add_pocket",
        freecad_type="PartDesign::Pocket",
        title="Pocket paramétrico",
        description=(
            "Cut a closed Body sketch into the solid as a parametric "
            "PartDesign::Pocket. Use through_all to cut through the whole "
            "body regardless of length. The cut runs OPPOSITE the sketch "
            "plane normal: from a sketch on the XY origin plane with the "
            "material padded above it, set reversed=true to cut into the "
            "solid. Example: {\"sketch\": \"PocketSketch\", \"length\": 5, "
            "\"through_all\": true, \"reversed\": true}."
        ),
        profile="sketch",
        default_name="AIPocket",
        properties=(
            FeatureProperty("length", "Length", _MM_POSITIVE, required=True),
            FeatureProperty("midplane", "Midplane", _BOOL),
            FeatureProperty("reversed", "Reversed", _BOOL),
        ),
        extra_arguments={"through_all": dict(_BOOL)},
        aliases=("pocket", "cavidade", "rebaixo", "corte paramétrico"),
        tags=("partdesign", "body", "cortar", "cut", "furar"),
        examples=(
            "Abra um pocket de 5 mm com o sketch do rebaixo.",
            "Pocket the recess sketch 5 mm deep.",
        ),
        canonical_order=521,
    ),
    FeatureDefinition(
        tool_name="cad.add_revolution",
        freecad_type="PartDesign::Revolution",
        title="Revolução paramétrica",
        description=(
            "Revolve a closed Body sketch around one of its own axes into a "
            "parametric PartDesign::Revolution. The profile must not cross "
            "the axis. Example: {\"sketch\": \"Profile\", \"angle\": 360, "
            "\"axis\": \"vertical\"}."
        ),
        profile="sketch",
        default_name="AIRevolution",
        properties=(
            FeatureProperty("angle", "Angle", _ANGLE, required=True),
            FeatureProperty("midplane", "Midplane", _BOOL),
            FeatureProperty("reversed", "Reversed", _BOOL),
        ),
        axis=FeatureAxisChoice(
            argument="axis",
            choices=("vertical", "horizontal"),
            kind="sketch_axis",
            default="vertical",
        ),
        aliases=("revolução", "revolve", "torneado", "lathe"),
        tags=("partdesign", "body", "revolucionar", "eixo", "axis"),
        examples=(
            "Revolucione o perfil 360 graus no eixo vertical.",
            "Revolve the profile 360 degrees around the vertical axis.",
        ),
        canonical_order=522,
    ),
    FeatureDefinition(
        tool_name="cad.add_groove",
        freecad_type="PartDesign::Groove",
        title="Groove paramétrico",
        description=(
            "Revolve a closed Body sketch around one of its own axes and "
            "REMOVE the swept material as a parametric PartDesign::Groove — "
            "the subtractive counterpart of cad.add_revolution. Example: "
            "{\"sketch\": \"GrooveProfile\", \"angle\": 360, \"axis\": "
            "\"vertical\"}."
        ),
        profile="sketch",
        default_name="AIGroove",
        properties=(
            FeatureProperty("angle", "Angle", _ANGLE, required=True),
            FeatureProperty("midplane", "Midplane", _BOOL),
            FeatureProperty("reversed", "Reversed", _BOOL),
        ),
        axis=FeatureAxisChoice(
            argument="axis",
            choices=("vertical", "horizontal"),
            kind="sketch_axis",
            default="vertical",
        ),
        aliases=("groove", "canal", "ranhura torneada"),
        tags=("partdesign", "body", "canal", "remover", "revolução"),
        examples=(
            "Abra um canal revolucionando o perfil da ranhura.",
            "Cut a groove by revolving the slot profile.",
        ),
        canonical_order=523,
    ),
    FeatureDefinition(
        tool_name="cad.add_linear_pattern",
        freecad_type="PartDesign::LinearPattern",
        title="Padrão linear paramétrico",
        description=(
            "Repeat existing Body features along a Body origin axis as a "
            "parametric PartDesign::LinearPattern. length is the TOTAL span "
            "from the first to the last occurrence. Defaults to the tip "
            "feature when features is omitted. Example: {\"direction\": "
            "\"x\", \"length\": 40, \"occurrences\": 4}."
        ),
        profile="features",
        default_name="AILinearPattern",
        properties=(
            FeatureProperty("length", "Length", _MM_POSITIVE, required=True),
            FeatureProperty(
                "occurrences",
                "Occurrences",
                {"type": "integer", "minimum": 2, "maximum": 64},
                required=True,
            ),
        ),
        axis=FeatureAxisChoice(
            argument="direction",
            choices=("x", "y", "z"),
            kind="origin_axis",
            required=True,
        ),
        aliases=("padrão linear paramétrico", "linear pattern", "repetir em linha"),
        tags=("partdesign", "body", "padrão", "pattern", "repetição"),
        examples=(
            "Repita o furo 4 vezes ao longo de X em 40 mm.",
            "Pattern the hole 4 times along X over 40 mm.",
        ),
        canonical_order=524,
    ),
    FeatureDefinition(
        tool_name="cad.add_polar_pattern",
        freecad_type="PartDesign::PolarPattern",
        title="Padrão polar paramétrico",
        description=(
            "Repeat existing Body features around a Body origin axis as a "
            "parametric PartDesign::PolarPattern. angle is the TOTAL sweep "
            "of the pattern. Defaults to the tip feature when features is "
            "omitted. Example: {\"axis\": \"z\", \"angle\": 360, "
            "\"occurrences\": 6}."
        ),
        profile="features",
        default_name="AIPolarPattern",
        properties=(
            FeatureProperty("angle", "Angle", _ANGLE, required=True),
            FeatureProperty(
                "occurrences",
                "Occurrences",
                {"type": "integer", "minimum": 2, "maximum": 128},
                required=True,
            ),
        ),
        axis=FeatureAxisChoice(
            argument="axis",
            choices=("x", "y", "z"),
            kind="origin_axis",
            default="z",
        ),
        aliases=("padrão polar paramétrico", "polar pattern", "repetir em círculo"),
        tags=("partdesign", "body", "padrão", "circular", "flange"),
        examples=(
            "Repita o furo 6 vezes ao redor do eixo Z.",
            "Pattern the hole 6 times around the Z axis.",
        ),
        canonical_order=525,
    ),
    FeatureDefinition(
        tool_name="cad.add_mirrored_pattern",
        freecad_type="PartDesign::Mirrored",
        title="Espelhamento paramétrico",
        description=(
            "Mirror existing Body features across a Body origin plane as a "
            "parametric PartDesign::Mirrored. Defaults to the tip feature "
            "when features is omitted. Example: {\"plane\": \"yz\"}."
        ),
        profile="features",
        default_name="AIMirrored",
        axis=FeatureAxisChoice(
            argument="plane",
            choices=("xy", "xz", "yz"),
            kind="origin_plane",
            required=True,
        ),
        aliases=("espelhar paramétrico", "mirrored", "simetria"),
        tags=("partdesign", "body", "espelho", "mirror", "simetria"),
        examples=(
            "Espelhe o rasgo no plano YZ.",
            "Mirror the slot across the YZ plane.",
        ),
        canonical_order=526,
    ),
)


_BY_TOOL = {definition.tool_name: definition for definition in PARTDESIGN_FEATURES}
_BY_TYPE = {definition.freecad_type: definition for definition in PARTDESIGN_FEATURES}
if len(_BY_TOOL) != len(PARTDESIGN_FEATURES) or len(_BY_TYPE) != len(
    PARTDESIGN_FEATURES
):
    raise RuntimeError("The Part Design feature registry contains duplicates.")


def feature_by_tool(tool_name: str) -> FeatureDefinition:
    if tool_name not in _BY_TOOL:
        raise KeyError(f"Unknown Part Design feature tool: {tool_name}")
    return _BY_TOOL[tool_name]


def feature_by_type(freecad_type: str) -> FeatureDefinition:
    if freecad_type not in _BY_TYPE:
        raise KeyError(f"Unsupported Part Design feature type: {freecad_type}")
    return _BY_TYPE[freecad_type]


def editable_property_union() -> dict[str, dict[str, Any]]:
    """Union of every scalar argument, for the cad.edit_feature input schema.

    The adapter still enforces the exact per-type allowlist at execution;
    this union only bounds the static schema.
    """

    union: dict[str, dict[str, Any]] = {}
    for definition in PARTDESIGN_FEATURES:
        for prop in definition.properties:
            union.setdefault(prop.argument, dict(prop.schema))
    return union
