from __future__ import annotations

from talos.core.partdesign_registry import (
    PARTDESIGN_FEATURES,
    editable_property_union,
)
from talos.core.semantic_refs import (
    EDGE_SELECTOR_SCHEMA,
    FACE_SELECTOR_SCHEMA,
)
from talos.core.tool_catalog.schemas import (
    NAME,
    OBJECT_RESULT,
    REFERENCE,
    _object_schema,
    _spec,
)
from talos.core.tool_registry import ToolRisk, ToolSpec


FEATURE_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "body": {"type": "string"},
        "feature_type": {"type": "string"},
        "volume_mm3": {"type": "number"},
        "valid": {"type": "boolean"},
    },
    "required": ["name", "label", "body", "feature_type", "valid"],
}

SKETCH_STATUS_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "fully_constrained": {"type": "boolean"},
        "degrees_of_freedom": {"type": ["integer", "null"]},
        "solver_status": {"type": "integer"},
        "has_conflicts": {"type": ["boolean", "null"]},
        "has_redundancies": {"type": ["boolean", "null"]},
        "underconstrained_geometry": {
            "type": "array",
            "items": {"type": "integer"},
        },
        "geometry_count": {"type": "integer"},
        "constraint_count": {"type": "integer"},
    },
    "required": [
        "name",
        "label",
        "fully_constrained",
        "degrees_of_freedom",
        "solver_status",
        "underconstrained_geometry",
        "geometry_count",
        "constraint_count",
    ],
}


def _feature_tool_specs() -> tuple[ToolSpec, ...]:
    """Generate one tool per whitelisted feature from the neutral registry."""

    return tuple(
        _spec(
            definition.tool_name,
            definition.description,
            ToolRisk.MODIFY,
            definition.input_schema(),
            family="partdesign",
            aliases=definition.aliases,
            tags=definition.tags,
            examples=definition.examples,
            order=definition.canonical_order,
            output_schema=FEATURE_RESULT,
        )
        for definition in PARTDESIGN_FEATURES
    )


def partdesign_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the parametric Part Design tool specifications."""

    return (
        _spec(
            "cad.create_body",
            (
                "Create an empty PartDesign::Body, the container of a "
                "parametric feature tree. Professional models start here: "
                "sketches attach to the body origin planes and features "
                "chain inside the body. Example: {\"name\": \"MainBody\"}."
            ),
            ToolRisk.MODIFY,
            _object_schema({"name": NAME}, ()),
            family="partdesign",
            aliases=("body", "corpo", "árvore paramétrica", "parametric body"),
            tags=("partdesign", "body", "corpo", "paramétrico", "parametric"),
            examples=(
                "Crie um Body para a peça principal.",
                "Create a body called MainBody.",
            ),
            order=510,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_body_sketch",
            (
                "Create an empty sketch INSIDE a PartDesign::Body, attached "
                "to one of its origin planes (xy, xz or yz) with an optional "
                "offset along that plane's normal. Draw with the existing "
                "add_sketch_* tools, constrain it fully, then feed it to "
                "cad.add_pad or cad.add_pocket. Example: {\"body\": "
                "\"MainBody\", \"plane\": \"xy\", \"offset\": 0}."
            ),
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "body": REFERENCE,
                    "plane": {"type": "string", "enum": ["xy", "xz", "yz"]},
                    "offset": {
                        "type": "number",
                        "minimum": -10000,
                        "maximum": 10000,
                    },
                    "name": NAME,
                },
                ("plane",),
            ),
            family="partdesign",
            aliases=(
                "sketch no body",
                "esboço no corpo",
                "croqui paramétrico",
            ),
            tags=("partdesign", "body", "corpo", "anexar", "attach"),
            examples=(
                "Crie um sketch no plano XY do Body.",
                "Create a sketch on the body's XZ plane offset 10 mm.",
            ),
            order=511,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.set_sketch_datum",
            (
                "Change the value of one DRIVING dimensional constraint "
                "(distance, radius, diameter or angle) in a sketch, by "
                "constraint index or name. This is how a professional edits "
                "a model: change the dimension, let the tree recompute. "
                "Values are millimeters, or degrees for angles. Example: "
                "{\"sketch\": \"Sketch\", \"constraint\": \"width\", "
                "\"value\": 42.5}."
            ),
            ToolRisk.MODIFY,
            {
                "type": "object",
                "properties": {
                    "sketch": REFERENCE,
                    "constraint": {
                        "anyOf": [
                            {"type": "integer", "minimum": 0, "maximum": 4096},
                            {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 64,
                            },
                        ]
                    },
                    "value": {
                        "type": "number",
                        "minimum": -100000,
                        "maximum": 100000,
                    },
                },
                "required": ["sketch", "constraint", "value"],
                "additionalProperties": False,
            },
            family="partdesign",
            aliases=(
                "mudar cota",
                "editar dimensão",
                "set dimension",
                "change constraint value",
            ),
            tags=("partdesign", "sketch", "cota", "dimensão", "dimension", "editar"),
            examples=(
                "Mude a cota width do sketch para 42.5 mm.",
                "Set the base sketch radius constraint to 6 mm.",
            ),
            order=512,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.get_sketch_status",
            (
                "Report whether a sketch is fully constrained, its remaining "
                "degrees of freedom, solver conflicts or redundancies, and "
                "which geometry is still under-constrained. A professional "
                "sketch reaches 0 degrees of freedom before it drives a "
                "feature. Example: {\"sketch\": \"Sketch\"}."
            ),
            ToolRisk.READ,
            _object_schema({"sketch": REFERENCE}, ("sketch",)),
            family="partdesign",
            aliases=(
                "graus de liberdade",
                "degrees of freedom",
                "sketch restrito",
                "fully constrained",
            ),
            tags=("partdesign", "sketch", "restrições", "constraints", "dof"),
            examples=(
                "O sketch da base está totalmente restrito?",
                "How many degrees of freedom remain in the sketch?",
            ),
            order=513,
            output_schema=SKETCH_STATUS_RESULT,
        ),
        _spec(
            "cad.edit_feature",
            (
                "Edit whitelisted parameters of an existing parametric "
                "PartDesign feature (pad length, pocket depth, pattern "
                "occurrences...) and recompute the tree. Only properties "
                "valid for that feature type are accepted. Example: "
                "{\"feature\": \"AIPad\", \"properties\": {\"length\": 12}}."
            ),
            ToolRisk.MODIFY,
            {
                "type": "object",
                "properties": {
                    "feature": REFERENCE,
                    "properties": {
                        "type": "object",
                        "properties": editable_property_union(),
                        "additionalProperties": False,
                        "minProperties": 1,
                    },
                },
                "required": ["feature", "properties"],
                "additionalProperties": False,
            },
            family="partdesign",
            aliases=(
                "editar feature",
                "mudar parâmetro da feature",
                "edit pad length",
            ),
            tags=("partdesign", "editar", "edit", "parâmetro", "recompute"),
            examples=(
                "Aumente o comprimento do pad para 12 mm.",
                "Change the pocket depth to 3 mm.",
            ),
            order=514,
            output_schema=FEATURE_RESULT,
        ),
        _spec(
            "cad.resolve_body_reference",
            (
                "Preview what a semantic face or edge selector resolves to on "
                "the current Body tip, without mutating anything. Use before "
                "cad.create_face_sketch, cad.add_fillet or cad.add_chamfer to "
                "confirm the target. A selector that matches nothing fails as "
                "stale instead of guessing. Example: {\"face\": {\"kind\": "
                "\"largest_planar_face\", \"normal\": \"+z\"}}."
            ),
            ToolRisk.READ,
            {
                "type": "object",
                "properties": {
                    "body": REFERENCE,
                    "face": FACE_SELECTOR_SCHEMA,
                    "edges": EDGE_SELECTOR_SCHEMA,
                },
                "anyOf": [{"required": ["face"]}, {"required": ["edges"]}],
                "additionalProperties": False,
            },
            family="partdesign",
            aliases=(
                "resolver referência",
                "qual face",
                "resolve face",
                "preview selector",
            ),
            tags=("partdesign", "referência", "reference", "topologia"),
            examples=(
                "Qual é a maior face plana superior do corpo?",
                "Which edges match diameter 6 on this body?",
            ),
            order=515,
            output_schema={
                "type": "object",
                "properties": {
                    "body": {"type": "string"},
                    "face": {"type": "object"},
                    "edges": {"type": "object"},
                    "valid": {"type": "boolean"},
                },
                "required": ["body", "valid"],
            },
        ),
        _spec(
            "cad.create_face_sketch",
            (
                "Create an empty sketch attached to a SOLID FACE of the Body "
                "resolved by a semantic selector — the professional way to "
                "chain features on existing geometry. The sketch stays glued "
                "to that face when dimensions change. Example: {\"face\": "
                "{\"kind\": \"largest_planar_face\", \"normal\": \"+z\"}, "
                "\"name\": \"BossSketch\"}."
            ),
            ToolRisk.MODIFY,
            {
                "type": "object",
                "properties": {
                    "face": FACE_SELECTOR_SCHEMA,
                    "body": REFERENCE,
                    "name": NAME,
                },
                "required": ["face"],
                "additionalProperties": False,
            },
            family="partdesign",
            aliases=(
                "sketch na face",
                "esboço na face",
                "sketch on face",
                "desenhar sobre a face",
            ),
            tags=("partdesign", "face", "anexar", "attach", "topo"),
            examples=(
                "Crie um sketch na face superior do corpo.",
                "Sketch on the largest top face to add a boss.",
            ),
            order=516,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.add_fillet",
            (
                "Round Body edges selected semantically (circular_edges by "
                "diameter, face_boundary or named_edges) with a parametric "
                "PartDesign::Fillet. Keep the radius well under the smallest "
                "neighbouring dimension. Example: {\"edges\": {\"kind\": "
                "\"circular_edges\", \"diameter\": 8}, \"radius\": 1.5}."
            ),
            ToolRisk.MODIFY,
            {
                "type": "object",
                "properties": {
                    "edges": EDGE_SELECTOR_SCHEMA,
                    "radius": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 1000,
                    },
                    "body": REFERENCE,
                    "name": NAME,
                },
                "required": ["edges", "radius"],
                "additionalProperties": False,
            },
            family="partdesign",
            aliases=(
                "filete paramétrico",
                "arredondar arestas do corpo",
                "fillet body edges",
            ),
            tags=("partdesign", "filete", "fillet", "raio", "arredondar"),
            examples=(
                "Arredonde as bordas do furo de 8 mm com raio 1.5.",
                "Fillet the top face boundary with radius 2.",
            ),
            order=517,
            output_schema=FEATURE_RESULT,
        ),
        _spec(
            "cad.add_chamfer",
            (
                "Chamfer Body edges selected semantically (circular_edges by "
                "diameter, face_boundary or named_edges) with a parametric "
                "PartDesign::Chamfer at 45 degrees by size millimeters. "
                "Example: {\"edges\": {\"kind\": \"face_boundary\", \"face\": "
                "{\"kind\": \"largest_planar_face\", \"normal\": \"+z\"}}, "
                "\"size\": 1}."
            ),
            ToolRisk.MODIFY,
            {
                "type": "object",
                "properties": {
                    "edges": EDGE_SELECTOR_SCHEMA,
                    "size": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 1000,
                    },
                    "body": REFERENCE,
                    "name": NAME,
                },
                "required": ["edges", "size"],
                "additionalProperties": False,
            },
            family="partdesign",
            aliases=(
                "chanfro paramétrico",
                "quebrar arestas do corpo",
                "chamfer body edges",
            ),
            tags=("partdesign", "chanfro", "chamfer", "quebra", "bisel"),
            examples=(
                "Chanfre o contorno da face superior com 1 mm.",
                "Chamfer the hole edges of diameter 8 by 0.5.",
            ),
            order=518,
            output_schema=FEATURE_RESULT,
        ),
    ) + _feature_tool_specs()
