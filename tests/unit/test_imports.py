from importlib import import_module
from pathlib import Path
import runpy
from types import SimpleNamespace


def test_freecad_facing_modules_import_without_freecad_installed() -> None:
    import_module("talos.adapters.freecad_adapter")
    import_module("talos.runtime")
    import_module("talos.ui.talos_panel")
    import_module("talos.orchestration")
    import_module("talos.orchestration.plans")
    import_module("talos.orchestration.plan_service")
    import_module("talos.orchestration.recipes")
    import_module("talos.core.tool_results")
    import_module("talos.core.context")
    import_module("talos.core.mechanical_tools")
    import_module("talos.core.tool_selector")
    import_module("talos.core.visual_cache")
    import_module("talos.evaluation.benchmark")


def test_freecad_workbench_registration_is_idempotent(monkeypatch) -> None:
    workbenches = {}

    def add_workbench(workbench) -> None:
        name = type(workbench).__name__
        if name in workbenches:
            raise KeyError(f"{name!r} already exists")
        workbenches[name] = workbench

    freecad_gui = SimpleNamespace(
        addWorkbench=add_workbench,
        listWorkbenches=lambda: dict(workbenches),
    )
    monkeypatch.setitem(__import__("sys").modules, "FreeCADGui", freecad_gui)
    init_gui = Path(__file__).resolve().parents[2] / "src" / "freecad" / "Talos" / "InitGui.py"

    for _ in range(2):
        runpy.run_path(str(init_gui), init_globals={"Workbench": object})

    assert list(workbenches) == ["TalosWorkbench"]
