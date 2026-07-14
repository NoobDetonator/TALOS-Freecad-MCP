from __future__ import annotations

from typing import Any


_PLANE_NORMALS = {
    "xy": (0.0, 0.0, 1.0),
    "yz": (1.0, 0.0, 0.0),
    "xz": (0.0, 1.0, 0.0),
}
_AXIS_DIRECTIONS = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


class PatternMixin:
    """Mirror and linear/polar feature patterns fused into one solid."""

    @staticmethod
    def _checked_pattern_count(count: Any) -> int:
        checked = int(count)
        if isinstance(count, bool) or checked != count or not 2 <= checked <= 64:
            raise ValueError("A pattern needs between 2 and 64 instances.")
        return checked

    def mirror_object(
        self,
        object: str,
        plane: str = "yz",
        name: str = "AIMirror",
    ) -> dict[str, Any]:
        if plane not in _PLANE_NORMALS:
            raise ValueError("The mirror plane must be 'xy', 'yz' or 'xz'.")
        source = self._resolve_document_object(object)
        source_shape = self._shape_or_error(source)
        if not source_shape.Solids:
            raise ValueError("Only solid objects can be mirrored.")
        app, _ = self._modules()

        def mirror(document: Any) -> Any:
            normal = app.Vector(*_PLANE_NORMALS[plane])
            shape = source.Shape.mirror(app.Vector(0, 0, 0), normal)
            if not shape.Solids:
                raise RuntimeError("The mirror did not produce a solid.")
            return self._derived_feature(document, name, shape, (source,), "mirror")

        result = self._run_transaction(f"mirror {source.Name}", mirror)
        return {
            "name": result.Name,
            "label": result.Label,
            "plane": plane,
            "volume_mm3": float(result.Shape.Volume),
            "valid": True,
        }

    def linear_pattern(
        self,
        object: str,
        count: int,
        spacing: float,
        direction: str = "x",
        name: str = "AILinearPattern",
    ) -> dict[str, Any]:
        checked_count = self._checked_pattern_count(count)
        checked_spacing = self._positive_values(spacing)[0]
        if direction not in _AXIS_DIRECTIONS:
            raise ValueError("The pattern direction must be 'x', 'y' or 'z'.")
        source = self._resolve_document_object(object)
        source_shape = self._shape_or_error(source)
        if not source_shape.Solids:
            raise ValueError("Only solid objects can be patterned.")
        app, _ = self._modules()
        step = _AXIS_DIRECTIONS[direction]

        def pattern(document: Any) -> Any:
            shape = source.Shape
            for index in range(1, checked_count):
                copy = source.Shape.copy()
                copy.translate(
                    app.Vector(
                        step[0] * checked_spacing * index,
                        step[1] * checked_spacing * index,
                        step[2] * checked_spacing * index,
                    )
                )
                shape = shape.fuse(copy)
            if not shape.Solids:
                raise RuntimeError("The linear pattern did not produce a solid.")
            return self._derived_feature(
                document, name, shape, (source,), "linear_pattern"
            )

        result = self._run_transaction(f"linear pattern {source.Name}", pattern)
        return {
            "name": result.Name,
            "label": result.Label,
            "instance_count": checked_count,
            "direction": direction,
            "spacing_mm": checked_spacing,
            "volume_mm3": float(result.Shape.Volume),
            "valid": True,
        }

    def polar_pattern(
        self,
        object: str,
        count: int,
        angle: float = 360.0,
        axis: str = "z",
        name: str = "AIPolarPattern",
    ) -> dict[str, Any]:
        checked_count = self._checked_pattern_count(count)
        checked_angle = self._finite_float(angle)
        if checked_angle is None or not 0 < checked_angle <= 360:
            raise ValueError("The polar angle must be within (0, 360].")
        if axis not in _AXIS_DIRECTIONS:
            raise ValueError("The pattern axis must be 'x', 'y' or 'z'.")
        source = self._resolve_document_object(object)
        source_shape = self._shape_or_error(source)
        if not source_shape.Solids:
            raise ValueError("Only solid objects can be patterned.")
        app, _ = self._modules()
        direction = app.Vector(*_AXIS_DIRECTIONS[axis])
        # A full turn steps by angle/count so the last copy does not fall on the
        # first; an arc spreads the copies across its two ends.
        step = checked_angle / checked_count if checked_angle == 360 else (
            checked_angle / (checked_count - 1)
        )

        def pattern(document: Any) -> Any:
            shape = source.Shape
            for index in range(1, checked_count):
                copy = source.Shape.copy()
                copy.rotate(app.Vector(0, 0, 0), direction, step * index)
                shape = shape.fuse(copy)
            if not shape.Solids:
                raise RuntimeError("The polar pattern did not produce a solid.")
            return self._derived_feature(
                document, name, shape, (source,), "polar_pattern"
            )

        result = self._run_transaction(f"polar pattern {source.Name}", pattern)
        return {
            "name": result.Name,
            "label": result.Label,
            "instance_count": checked_count,
            "axis": axis,
            "angle_deg": checked_angle,
            "volume_mm3": float(result.Shape.Volume),
            "valid": True,
        }
