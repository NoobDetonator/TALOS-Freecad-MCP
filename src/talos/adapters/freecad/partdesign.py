from __future__ import annotations

from typing import Any

from talos.core.partdesign_registry import (
    FeatureDefinition,
    feature_by_tool,
    feature_by_type,
)
from talos.core.semantic_refs import (
    EdgeSelector,
    FaceSelector,
    axis_vector,
    parse_edge_selector,
    parse_face_selector,
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
        document = app.ActiveDocument or app.newDocument("TalosDocument")
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

    # --- semantic reference resolution ---------------------------------------

    @classmethod
    def _tip_feature(cls, body: Any) -> Any:
        tip = getattr(body, "Tip", None)
        if tip is None:
            raise ValueError("The body has no features to reference yet.")
        return tip

    @staticmethod
    def _face_normal(face: Any) -> Any:
        # Face.normalAt already returns the outward-oriented normal: on a box,
        # the bottom face reports -Z even though its Orientation is Reversed.
        return face.normalAt(0, 0)

    @classmethod
    def _resolve_face(
        cls, body: Any, selector: FaceSelector
    ) -> tuple[Any, str, Any]:
        """Resolve one face selector on the body tip shape or fail as stale."""

        tip = cls._tip_feature(body)
        shape = cls._shape_or_error(tip)
        faces = list(shape.Faces)
        if selector.kind == "named_face":
            index = int(str(selector.name)[4:]) - 1
            if not 0 <= index < len(faces):
                raise ValueError(
                    f"The face reference {selector.name} is stale: the body "
                    f"has {len(faces)} faces."
                )
            return tip, str(selector.name), faces[index]

        candidates: list[tuple[float, int, Any]] = []
        for position, face in enumerate(faces):
            if type(face.Surface).__name__ != "Plane":
                continue
            if selector.normal is not None:
                wanted = axis_vector(selector.normal)
                normal = cls._face_normal(face)
                alignment = (
                    normal.x * wanted[0]
                    + normal.y * wanted[1]
                    + normal.z * wanted[2]
                )
                if alignment < 0.999:
                    continue
            candidates.append((float(face.Area), position, face))
        if not candidates:
            raise ValueError(
                "No planar face matches the selector; the reference is stale "
                "or the direction is wrong."
            )
        candidates.sort(key=lambda item: (-item[0], item[1]))
        if (
            len(candidates) > 1
            and candidates[1][0] > candidates[0][0] * (1 - 1e-6)
        ):
            raise ValueError(
                "The face selector is ambiguous: multiple planar faces share "
                "the largest area. Narrow it with a normal direction."
            )
        area, position, face = candidates[0]
        return tip, f"Face{position + 1}", face

    @classmethod
    def _resolve_edges(
        cls, body: Any, selector: EdgeSelector
    ) -> tuple[Any, list[str]]:
        """Resolve one edge selector to element names on the body tip shape."""

        tip = cls._tip_feature(body)
        shape = cls._shape_or_error(tip)
        edges = list(shape.Edges)
        names: list[str] = []
        if selector.kind == "named_edges":
            for name in selector.names:
                index = int(name[4:]) - 1
                if not 0 <= index < len(edges):
                    raise ValueError(
                        f"The edge reference {name} is stale: the body has "
                        f"{len(edges)} edges."
                    )
            names = list(selector.names)
        elif selector.kind == "circular_edges":
            for position, edge in enumerate(edges):
                curve = getattr(edge, "Curve", None)
                if type(curve).__name__ != "Circle" or not edge.Closed:
                    continue
                diameter = 2.0 * float(curve.Radius)
                if abs(diameter - float(selector.diameter)) <= selector.tolerance:
                    names.append(f"Edge{position + 1}")
        elif selector.kind == "face_boundary":
            _, _, face = cls._resolve_face(body, selector.face)
            for position, edge in enumerate(edges):
                if any(edge.isSame(candidate) for candidate in face.Edges):
                    names.append(f"Edge{position + 1}")
        else:
            raise ValueError("Unsupported edge selector kind.")
        if not names:
            raise ValueError(
                "No edge matches the selector; the reference is stale or the "
                "parameters do not describe this body."
            )
        return tip, names

    def resolve_body_reference(
        self,
        body: str | None = None,
        face: dict[str, Any] | None = None,
        edges: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Preview what the semantic selectors resolve to, without mutating."""

        if face is None and edges is None:
            raise ValueError("Provide a face or an edges selector to resolve.")
        target_body = self._body_or_error(body)
        result: dict[str, Any] = {"body": target_body.Name, "valid": True}
        if face is not None:
            tip, face_name, resolved = self._resolve_face(
                target_body, parse_face_selector(face)
            )
            center = resolved.CenterOfMass
            normal = self._face_normal(resolved)
            result["face"] = {
                "feature": tip.Name,
                "name": face_name,
                "area_mm2": float(resolved.Area),
                "center_mm": [float(center.x), float(center.y), float(center.z)],
                "normal": [float(normal.x), float(normal.y), float(normal.z)],
            }
        if edges is not None:
            tip, names = self._resolve_edges(
                target_body, parse_edge_selector(edges)
            )
            result["edges"] = {
                "feature": tip.Name,
                "names": names,
                "count": len(names),
            }
        return result

    # --- face sketch and dressups --------------------------------------------

    def create_face_sketch(
        self,
        face: dict[str, Any],
        body: str | None = None,
        name: str = "AISketch",
    ) -> dict[str, Any]:
        target_body = self._body_or_error(body)
        document = self._active_document()
        checked_name = self._ensure_new_name(document, name)
        tip, face_name, _ = self._resolve_face(
            target_body, parse_face_selector(face)
        )

        def create(document: Any) -> Any:
            sketch = target_body.newObject(
                "Sketcher::SketchObject", checked_name
            )
            support_property = (
                "AttachmentSupport"
                if hasattr(sketch, "AttachmentSupport")
                else "Support"
            )
            setattr(sketch, support_property, [(tip, face_name)])
            sketch.MapMode = "FlatFace"
            return sketch

        sketch = self._run_transaction(
            f"create face sketch {checked_name}", create, allow_null_shape=True
        )
        return {
            "name": sketch.Name,
            "label": sketch.Label,
            "body": target_body.Name,
            "face": face_name,
            "feature": tip.Name,
            "valid": True,
        }

    def _add_dressup(
        self,
        freecad_type: str,
        size_property: str,
        size_value: float,
        edges: dict[str, Any],
        body: str | None,
        name: str,
    ) -> dict[str, Any]:
        checked_size = self._positive_values(size_value)[0]
        target_body = self._body_or_error(body)
        document = self._active_document()
        checked_name = self._ensure_new_name(document, name)
        tip, edge_names = self._resolve_edges(
            target_body, parse_edge_selector(edges)
        )

        def create(document: Any) -> Any:
            feature = target_body.newObject(freecad_type, checked_name)
            feature.Base = (tip, edge_names)
            setattr(feature, size_property, checked_size)
            target_body.Tip = feature
            return feature

        feature = self._run_transaction(
            f"add {freecad_type} {checked_name}", create
        )
        result = self._feature_result(target_body, feature)
        result["edges"] = edge_names
        return result

    def add_fillet_feature(
        self,
        edges: dict[str, Any],
        radius: float,
        body: str | None = None,
        name: str = "AIFillet",
    ) -> dict[str, Any]:
        return self._add_dressup(
            "PartDesign::Fillet", "Radius", radius, edges, body, name
        )

    def add_chamfer_feature(
        self,
        edges: dict[str, Any],
        size: float,
        body: str | None = None,
        name: str = "AIChamfer",
    ) -> dict[str, Any]:
        return self._add_dressup(
            "PartDesign::Chamfer", "Size", size, edges, body, name
        )

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
            if arguments.get("through_all"):
                # Pocket exposes the depth mode as Type; Hole as DepthType.
                depth_property = (
                    "DepthType" if hasattr(feature, "DepthType") else "Type"
                )
                setattr(feature, depth_property, "ThroughAll")
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
