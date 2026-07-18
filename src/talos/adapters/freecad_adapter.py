from __future__ import annotations

from talos.adapters.freecad.base import FreeCadAdapterBase
from talos.adapters.freecad.assembly import AssemblyMixin
from talos.adapters.freecad.bearings import BearingMixin
from talos.adapters.freecad.context import ContextReadsMixin
from talos.adapters.freecad.documents import DocumentMixin
from talos.adapters.freecad.edits import EditMixin
from talos.adapters.freecad.export import ExportMixin
from talos.adapters.freecad.features import FeatureMixin
from talos.adapters.freecad.mechanical import MechanicalMixin
from talos.adapters.freecad.objects import ObjectMixin
from talos.adapters.freecad.parameters import ParameterMixin
from talos.adapters.freecad.partdesign import PartDesignMixin
from talos.adapters.freecad.patterns import PatternMixin
from talos.adapters.freecad.primitives import PrimitiveMixin
from talos.adapters.freecad.sketches import SketchMixin
from talos.adapters.freecad.sketch_constraints import SketchConstraintMixin
from talos.adapters.freecad.sketch_geometry import SketchGeometryMixin
from talos.adapters.freecad.sweeps import SweepMixin


class FreeCadAdapter(
    ContextReadsMixin,
    PrimitiveMixin,
    ObjectMixin,
    EditMixin,
    SketchMixin,
    SketchGeometryMixin,
    SketchConstraintMixin,
    PartDesignMixin,
    ParameterMixin,
    FeatureMixin,
    SweepMixin,
    PatternMixin,
    MechanicalMixin,
    BearingMixin,
    AssemblyMixin,
    DocumentMixin,
    ExportMixin,
    FreeCadAdapterBase,
):
    """Small, explicit boundary around FreeCAD's Python API.

    Each domain lives in one mixin under :mod:`talos.adapters.freecad`;
    the shared validation and transaction core lives in
    :class:`FreeCadAdapterBase`.
    """


__all__ = ["FreeCadAdapter"]
