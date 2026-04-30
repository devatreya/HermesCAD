from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _load_freecad_modules():
    try:
        import FreeCAD as App
        import Import
        import Mesh
        import Part
    except Exception as exc:  # pragma: no cover - depends on FreeCAD runtime
        raise RuntimeError(
            "FreeCAD Python modules are not available. Run this script from FreeCAD or `freecadcmd`."
        ) from exc
    return App, Part, Mesh, Import


def _export_preview(output_dir: Path) -> str:
    preview_path = output_dir / "preview.png"
    try:  # pragma: no cover - depends on FreeCAD GUI availability
        import FreeCADGui as Gui
    except Exception as exc:
        return f"Preview skipped because FreeCADGui is unavailable in this environment: {exc}"

    try:
        active_document = Gui.activeDocument()
        if active_document is None:
            return "Preview skipped because no active GUI document was available."
        view = active_document.activeView()
        view.viewAxonometric()
        Gui.SendMsgToActiveView("ViewFit")
        view.saveImage(str(preview_path), 1600, 1200, "White")
        return f"Preview exported to {preview_path.name}."
    except Exception as exc:
        return f"Preview skipped because image export failed: {exc}"


def _load_config_from_env() -> dict[str, object]:
    config_path = os.environ.get("HERMESCAD_FREECAD_CONFIG")
    if not config_path:
        raise RuntimeError(
            "No FreeCAD assembly config was provided. Set HERMESCAD_FREECAD_CONFIG or pass explicit CLI arguments."
        )

    path = Path(config_path).resolve()
    if not path.exists():
        raise RuntimeError(f"FreeCAD assembly config file was not found: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def _argv_without_injected_script_path() -> list[str]:
    forwarded = sys.argv[1:]
    if forwarded and forwarded[0].endswith(".py"):
        return forwarded[1:]
    return forwarded


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a FreeCAD assembly from generated HermesCAD part outputs.")
    parser.add_argument("--config", type=Path, help="Path to the assembly config JSON.")
    args, unknown = parser.parse_known_args(_argv_without_injected_script_path())
    if unknown:
        raise RuntimeError(f"Unexpected FreeCAD assembly arguments: {unknown}")
    if args.config:
        return args
    config = _load_config_from_env()
    return argparse.Namespace(config=Path(str(config["config_path"])))


def _build_rotation(App, placement: dict[str, float]):
    rotation = App.Rotation(App.Vector(0, 0, 1), float(placement.get("rz_deg", 0.0)))
    rotation = App.Rotation(App.Vector(0, 1, 0), float(placement.get("ry_deg", 0.0))).multiply(rotation)
    rotation = App.Rotation(App.Vector(1, 0, 0), float(placement.get("rx_deg", 0.0))).multiply(rotation)
    return rotation


def main() -> int:
    args = _parse_args()
    config_payload = json.loads(args.config.read_text(encoding="utf-8"))

    App, Part, Mesh, Import = _load_freecad_modules()
    output_dir = Path(str(config_payload["output_dir"])).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    document = App.newDocument(str(config_payload.get("assembly_name", "HermesCADAssembly")))
    part_objects = []
    placements_summary: list[dict[str, object]] = []

    for part_spec in config_payload.get("parts", []):
        step_path = Path(str(part_spec["step_path"])).resolve()
        if not step_path.exists():
            raise RuntimeError(f"Assembly part STEP file was not found: {step_path}")

        part_shape = Part.read(str(step_path))
        part_object = document.addObject("Part::Feature", str(part_spec["name"]))
        placement = dict(part_spec.get("placement", {}))
        part_object.Shape = part_shape
        part_object.Placement = App.Placement(
            App.Vector(
                float(placement.get("x_mm", 0.0)),
                float(placement.get("y_mm", 0.0)),
                float(placement.get("z_mm", 0.0)),
            ),
            _build_rotation(App, placement),
        )
        part_objects.append(part_object)
        placements_summary.append(
            {
                "name": part_spec["name"],
                "step_path": str(step_path),
                "placement": placement,
            }
        )

    document.recompute()

    fcstd_path = output_dir / "hermescad_assembly.FCStd"
    step_path = output_dir / "hermescad_assembly.step"
    stl_path = output_dir / "hermescad_assembly.stl"

    document.saveAs(str(fcstd_path))
    Import.export(part_objects, str(step_path))
    Mesh.export(part_objects, str(stl_path))

    preview_status = _export_preview(output_dir)
    result_path = output_dir / "assembly_result.json"
    result_payload = {
        "assembly_name": config_payload.get("assembly_name"),
        "description": config_payload.get("description"),
        "placements": placements_summary,
        "outputs": [
            str(fcstd_path.resolve()),
            str(step_path.resolve()),
            str(stl_path.resolve()),
        ],
        "preview_status": preview_status,
        "part_count": len(part_objects),
    }
    result_path.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
    print(json.dumps(result_payload, indent=2))
    return 0


if __name__ == "__main__" or (
    os.environ.get("HERMESCAD_FREECAD_CONFIG")
    and len(sys.argv) > 1
    and Path(sys.argv[1]).resolve() == Path(__file__).resolve()
):
    raise SystemExit(main())
