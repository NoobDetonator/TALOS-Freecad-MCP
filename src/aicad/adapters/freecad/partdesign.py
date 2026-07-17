from __future__ import annotations

from typing import Any

from aicad.core.partdesign_registry import (
    FeatureDefinition,
    feature_by_tool,
    feature_by_type,
)


_ORIGIN_AXIS_ROLES = {"x": "X_Axis", "y": "Y_Axis", "z": "Z_Axis"}
_ORIGIN_PLANE_ROLES = {"xy": "XY_Plane", "xz": "XZ_Plane", "yz": "YZ_Plane"}
_SKETCH_AXIS_NAMES = {"vertical": "V_Axis", "horizontal": "H_Axis"}
_DISTANCE_CONSTRAINT_TYPES = {
    "Distance",
    "DistanceX",
    "DistanceY",
    "Radius",
    "Diameter",
}


class PartDesignMixin:
    """Parametric Body, sketch attachment and governed feature reflection."""

    # --- resolution helpers -------------------------------------------------

    @classmethod
    def _body_or_error(cls, reference: str | None) -> Any:
        document = cls._active_document()
        bodies = [
            item
            for item in document.Objects
            if item.TypeId == "PartDesign::Body"
        ]
        if reference:
            body = cls._resolve_document_object(reference)
            if body.TypeId != "PartDesign::Body":
                raise ValueError("The referenced object is not a PartDesign Body.")
            return body
        if len(bodies) == 1:
            return bodies[0]
        if not bodies:
            raise ValueError("No PartDesign Body exists; create one first.")
        names = ", ".join(item.Name for item in bodies)
        raise ValueError(f"Multiple bodies exist; specify one of: {names}.")

    @staticmethod
    def _origin_feature(body: Any, role: str) -> Any:
        origin = getattr(body, "Origin", None)
        features = getattr(origin, "OriginFeatures", ()) if origin else ()
        for item in features:
            if getattr(item, "Role", "") == role or item.Name.startswith(role):
                return item
        raise RuntimeError(f"The body origin does not provide {role}.")

    @classmethod
    def _sketch_in_body(cls, body: Any, reference: str) -> Any:
        sketch = cls._sketch_or_error(reference)
        if body.getObject(sketch.Name) is None:
            raise ValueError(
                "The sketch does not belong to the target body; create it "
                "with cad.create_body_sketch."
            )
        return sketch

    @classmethod
    def _features_in_body(
        cls, body: Any, references: list[str] | None
    ) -> list[Any]:
        if references:
            features = [cls._resolve_document_object(item) for item in references]
        else:
            tip = getattr(body, "Tip", None)
            if tip is None:
                raise ValueError("The body has no feature to transform yet.")
            features = [tip]
        for feature in features:
            if body.getObject(feature.Name) is None:
                raise ValueError(
                    f"{feature.Name} does not belong to the target body."
                )
            if not feature.TypeId.startswith("PartDesign::"):
                raise ValueError(
                    f"{feature.Name} is not a PartDesign feature."
                )
        return features

    @staticmethod
    def _feature_result(body: Any, feature: Any) -> dict[str, Any]:
        shape = getattr(body, "Shape", None)
        volume = (
            float(shape.Volume)
            if shape is not None and not shape.isNull()
            else 0.0
        )
        return {
            "name": feature.Name,
            "label": feature.Label,
            "body": body.Name,
            "feature_type": feature.TypeId,
            "volume_mm3": volume,
            "valid": True,
        }

    # --- body and sketch lifecycle ------------------------------------------

    def create_body(self, name: str = "AIBody") -> dict[str, Any]:
        app, _ = self._modules()
        document = app.ActiveDocument or app.newDocument("AICadDocument")
        self._ensure_undo(document)
        checked_name = self._ensure_new_name(document, name)

        def create(document: Any) -> Any:
            return document.addObject("PartDesign::Body", checked_name)

        body = self._run_transaction(
            f"create body {checked_name}", create, allow_null_shape=True
        )
        return {"name": body.Name, "label": body.Label, "valid": True}

    def create_body_sketch(
        self,
        plane: str,
        body: str | None = None,
        offset: float = 0.0,
        name: str = "AISketch",
    ) -> dict[str, Any]:
        app, _ = self._modules()
        role = _ORIGIN_PLANE_ROLES.get(str(plane).strip().lower())
        if role is None:
            raise ValueError("The sketch plane must be xy, xz or yz.")
        checked_offset = self._finite_float(offset)
        if checked_offset is None or abs(checked_offset) > 10000:
            raise ValueError("The sketch offset must be finite millimeters.")
        target_body = self._body_or_error(body)
        document = self._active_document()
        checked_name = self._ensure_new_name(document, name)
        plane_feature = self._origin_feature(target_body, role)

        def create(document: Any) -> Any:
            sketch = target_body.newObject(
                "Sketcher::SketchObject", checked_name
            )
            support_property = (
                "AttachmentSupport"
                if hasattr(sketch, "AttachmentSupport")
                else "Support"
            )
            setattr(sketch, support_property, [(plane_feature, "")])
            sketch.MapMode = "FlatFace"
            if checked_offset:
                sketch.AttachmentOffset = app.Placement(
                    app.Vector(0, 0, checked_offset), app.Rotation()
                )
            return sketch

        sketch = self._run_transaction(
            f"create body sketch {checked_name}", create, allow_null_shape=True
        )
        return {
            "name": sketch.Name,
            "label": sketch.Label,
            "body": target_body.Name,
            "plane": str(plane).strip().lower(),
            "offset_mm": checked_offset,
            "valid": True,
        }

    # --- dimension-driven editing -------------------------------------------

    def set_sketch_datum(
        self,
        sketch: str,
        constraint: int | str,
        value: float,
    ) -> dict[str, Any]:
        app, _ = self._modules()
        target = self._sketch_or_error(sketch)
        checked_value = self._finite_float(value)
        if checked_value is None:
            raise ValueError("The dimension value must be a finite number.")

        constraints = list(target.Constraints)
        if isinstance(constraint, bool):
            raise ValueError("The constraint selector must be an index or name.")
        if isinstance(constraint, int):
            index = self._constraint_index(target, constraint)
        else:
            wanted = str(constraint).strip()
            matches = [
                position
                for position, item in enumerate(constraints)
                if item.Name == wanted
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"The sketch has no unique constraint named {wanted}."
                )
            index = matches[0]

        constraint_type = str(constraints[index].Type)
        if constraint_type in _DISTANCE_CONSTRAINT_TYPES:
            quantity = app.Units.Quantity(f"{checked_value} mm")
        elif constraint_type == "Angle":
            quantity = app.Units.Quantity(f"{checked_value} deg")
        else:
            raise ValueError(
                f"Constraint {index} ({constraint_type}) is not a dimensional "
                "driving constraint."
            )

        def mutate(document: Any) -> Any:
            target.setDatum(index, quantity)
            return target

        self._run_transaction(
            f"set datum {index} on {target.Name}", mutate
        )
        return {
            "name": target.Name,
            "label": target.Label,
            "constraint_index": index,
            "constraint_type": constraint_type,
            "value": checked_value,
            "valid": True,
        }

    def get_sketch_status(self, sketch: str) -> dict[str, Any]:
        target = self._sketch_or_error(sketch)
        solver_status = int(target.solve())
        degrees_of_freedom: int | None = None
        getter = getattr(target, "getLastDoFs", None)
        if callable(getter):
            try:
                degrees_of_freedom = int(getter())
            except Exception:
                degrees_of_freedom = None

        def _last_flag(name: str) -> bool | None:
            flag = getattr(target, name, None)
            if callable(flag):
                try:
                    return bool(flag())
                except Exception:
                    return None
            return None

        underconstrained: list[int] = []
        dependent = getattr(target, "getGeometryWithDependentParameters", None)
        if callable(dependent):
            try:
                underconstrained = sorted(
                    {int(item[0]) for item in dependent()}
                )
            except Exception:
                underconstrained = []

        return {
            "name": target.Name,
            "label": target.Label,
            "fully_constrained": bool(
                getattr(target, "FullyConstrained", False)
            ),
            "degrees_of_freedom": degrees_of_freedom,
            "solver_status": solver_status,
            "has_conflicts": _last_flag("getLastHasConflicts"),
            "has_redundancies": _last_flag("getLastHasRedundancies"),
            "underconstrained_geometry": underconstrained,
            "geometry_count": int(target.GeometryCount),
            "constraint_count": len(target.Constraints),
        }

    # --- governed feature reflection ----------------------------------------

    def _apply_axis_argument(
        self,
        definition: FeatureDefinition,
        feature: Any,
        body: Any,
        profile_sketch: Any | None,
        arguments: dict[str, Any],
    ) -> None:
        choice_spec = definition.axis
        if choice_spec is None:
            return
        raw = arguments.get(choice_spec.argument, choice_spec.default)
        if raw is None:
            raise ValueError(f"{choice_spec.argument} is required.")
        choice = str(raw).strip().lower()
        if choice not in choice_spec.choices:
            allowed = ", ".join(choice_spec.choices)
            raise ValueError(
                f"{choice_spec.argument} must be one of: {allowed}."
            )
        if choice_spec.kind == "sketch_axis":
            if profile_sketch is None:
                raise RuntimeError("A sketch axis requires a sketch profile.")
            feature.ReferenceAxis = (
                profile_sketch,
                [_SKETCH_AXIS_NAMES[choice]],
            )
        elif choice_spec.kind == "origin_axis":
            axis_feature = self._origin_feature(
                body, _ORIGIN_AXIS_ROLES[choice]
            )
            if hasattr(feature, "Direction"):
                feature.Direction = (axis_feature, [""])
            else:
                feature.Axis = (axis_feature, [""])
        elif choice_spec.kind == "origin_plane":
            plane_feature = self._origin_feature(
                body, _ORIGIN_PLANE_ROLES[choice]
            )
            feature.MirrorPlane = (plane_feature, [""])
        else:
            raise RuntimeError(
                f"Unsupported axis kind: {choice_spec.kind}"
            )

    def create_partdesign_feature(
        self, tool_name: str, **arguments: Any
    ) -> dict[str, Any]:
        """Create one whitelisted parametric feature from its registry row."""

        definition = feature_by_tool(tool_name)
        body = self._body_or_error(arguments.get("body"))
        document = self._active_document()
        name = self._ensure_new_name(
            document, arguments.get("name", definition.default_name)
        )

        profile_sketch: Any | None = None
        transformed: list[Any] = []
        if definition.profile == "sketch":
            profile_sketch = self._sketch_in_body(body, arguments["sketch"])
        else:
            transformed = self._features_in_body(
                body, arguments.get("features")
            )

        def create(document: Any) -> Any:
            feature = body.newObject(definition.freecad_type, name)
            if profile_sketch is not None:
                feature.Profile = profile_sketch
            if transformed:
                transform_property = (
                    "TransformedFeatures"
                    if hasattr(feature, "TransformedFeatures")
                    else "Originals"
                )
                setattr(feature, transform_property, transformed)
            for prop in definition.properties:
                if prop.argument in arguments:
                    setattr(
                        feature,
                        prop.freecad_property,
                        arguments[prop.argument],
                    )
            if arguments.get("through_all") and hasattr(feature, "Type"):
                feature.Type = "ThroughAll"
            self._apply_axis_argument(
                definition, feature, body, profile_sketch, arguments
            )
            # body.newObject does not advance the tip for transform features
            # in FreeCAD 1.1, leaving the pattern computed but ignored by the
            # body shape; pin it explicitly so the result is always visible.
            body.Tip = feature
            if profile_sketch is not None:
                view = getattr(profile_sketch, "ViewObject", None)
                if view is not None:
                    view.Visibility = False
            return feature

        feature = self._run_transaction(
            f"add {definition.freecad_type} {name}", create
        )
        return self._feature_result(body, feature)

    def edit_feature(
        self, feature: str, properties: dict[str, Any]
    ) -> dict[str, Any]:
        target = self._resolve_document_object(feature)
        definition = feature_by_type(target.TypeId)
        allowlist = definition.scalar_allowlist()
        unknown = sorted(set(properties) - set(allowlist))
        if unknown:
            allowed = ", ".join(sorted(allowlist)) or "none"
            raise ValueError(
                f"{definition.freecad_type} does not accept: "
                f"{', '.join(unknown)}. Editable properties: {allowed}."
            )
        def mutate(document: Any) -> Any:
            for argument, value in properties.items():
                setattr(
                    target,
                    allowlist[argument].freecad_property,
                    value,
                )
            return target

        self._run_transaction(f"edit feature {target.Name}", mutate)
        document = self._active_document()
        owner = next(
            (
                item
                for item in document.Objects
                if item.TypeId == "PartDesign::Body"
                and item.getObject(target.Name) is not None
            ),
            target,
        )
        return self._feature_result(owner, target)
