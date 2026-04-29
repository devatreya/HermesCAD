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


def _apply_top_edge_chamfer(solid, bbox: dict[str, float], thickness_mm: float, chamfer_mm: float):
    if chamfer_mm <= 0:
        return solid, "Chamfer skipped because the requested chamfer size was not positive."

    tolerance = 1e-6
    min_x = float(bbox["min_x"])
    min_y = float(bbox["min_y"])
    max_x = float(bbox["max_x"])
    max_y = float(bbox["max_y"])

    edges = []
    for edge in solid.Edges:
        vertices = edge.Vertexes
        if len(vertices) != 2:
            continue
        points = [vertex.Point for vertex in vertices]
        if not all(abs(point.z - thickness_mm) < tolerance for point in points):
            continue
        if all(
            abs(point.x - min_x) < tolerance
            or abs(point.x - max_x) < tolerance
            or abs(point.y - min_y) < tolerance
            or abs(point.y - max_y) < tolerance
            for point in points
        ):
            edges.append(edge)

    if not edges:
        return solid, "Chamfer skipped because no suitable outer top edges were identified."

    try:
        return solid.makeChamfer(chamfer_mm, edges), f"Applied {chamfer_mm:g} mm chamfer to top outer edges."
    except Exception as exc:  # pragma: no cover - depends on FreeCAD geometry behavior
        return solid, f"Chamfer failed: {exc}"


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
            "No FreeCAD job config was provided. Set HERMESCAD_FREECAD_CONFIG or pass explicit CLI arguments."
        )

    path = Path(config_path).resolve()
    if not path.exists():
        raise RuntimeError(f"FreeCAD job config file was not found: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def _argv_without_injected_script_path() -> list[str]:
    forwarded = sys.argv[1:]
    if forwarded and forwarded[0].endswith(".py"):
        return forwarded[1:]
    return forwarded


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a simple plate model in FreeCAD from HermesCAD geometry.")
    parser.add_argument("--dxf", type=Path, help="Input DXF file.")
    parser.add_argument("--geometry-summary", type=Path, help="Path to geometry_summary.json.")
    parser.add_argument("--output-dir", type=Path, help="Job output directory.")
    parser.add_argument("--thickness-mm", type=float, help="Plate thickness in mm.")
    parser.add_argument("--chamfer-mm", type=float, default=0.0, help="Optional chamfer size in mm.")
    args, unknown = parser.parse_known_args(_argv_without_injected_script_path())

    if unknown:
        raise RuntimeError(f"Unexpected FreeCAD script arguments: {unknown}")

    if args.dxf and args.geometry_summary and args.output_dir and args.thickness_mm is not None:
        return args

    config = _load_config_from_env()
    return argparse.Namespace(
        dxf=Path(str(config["dxf"])),
        geometry_summary=Path(str(config["geometry_summary"])),
        output_dir=Path(str(config["output_dir"])),
        thickness_mm=float(config["thickness_mm"]),
        chamfer_mm=float(config.get("chamfer_mm", 0.0) or 0.0),
    )


def main() -> int:
    args = _parse_args()

    App, Part, Mesh, Import = _load_freecad_modules()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    geometry = json.loads(args.geometry_summary.read_text(encoding="utf-8"))
    bbox = geometry.get("bounding_box", {})
    hole_candidates = geometry.get("hole_candidates", [])
    min_x = float(bbox["min_x"])
    min_y = float(bbox["min_y"])
    width = float(bbox["width"])
    height = float(bbox["height"])

    if width <= 0 or height <= 0:
        print("Bounding box was invalid, so the MVP plate model could not be created.", file=sys.stderr)
        return 1

    document = App.newDocument("HermesCAD")
    plate_face = Part.makePlane(width, height, App.Vector(min_x, min_y, 0))
    solid = plate_face.extrude(App.Vector(0, 0, args.thickness_mm))

    for hole in hole_candidates:
        cylinder = Part.makeCylinder(
            float(hole["radius"]),
            args.thickness_mm,
            App.Vector(float(hole["center_x"]), float(hole["center_y"]), 0),
            App.Vector(0, 0, 1),
        )
        solid = solid.cut(cylinder)

    chamfer_status = "Chamfer skipped."
    if args.chamfer_mm:
        solid, chamfer_status = _apply_top_edge_chamfer(
            solid,
            bbox=bbox,
            thickness_mm=args.thickness_mm,
            chamfer_mm=args.chamfer_mm,
        )

    part_object = document.addObject("Part::Feature", "HermesCADPart")
    part_object.Shape = solid
    document.recompute()

    fcstd_path = output_dir / "hermescad_model.FCStd"
    step_path = output_dir / "hermescad_model.step"
    stl_path = output_dir / "hermescad_model.stl"

    document.saveAs(str(fcstd_path))
    Import.export([part_object], str(step_path))
    Mesh.export([part_object], str(stl_path))

    preview_status = _export_preview(output_dir)
    result_path = output_dir / "freecad_result.json"
    result = {
        "dxf_path": str(args.dxf.resolve()),
        "geometry_summary": str(args.geometry_summary.resolve()),
        "outputs": [
            str(fcstd_path.resolve()),
            str(step_path.resolve()),
            str(stl_path.resolve()),
        ],
        "chamfer_status": chamfer_status,
        "preview_status": preview_status,
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__" or (
    os.environ.get("HERMESCAD_FREECAD_CONFIG")
    and len(sys.argv) > 1
    and Path(sys.argv[1]).resolve() == Path(__file__).resolve()
):
    raise SystemExit(main())
