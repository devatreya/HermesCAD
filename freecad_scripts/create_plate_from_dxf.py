from __future__ import annotations

import argparse
import json
import math
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
    parser = argparse.ArgumentParser(description="Create a 2.5D model in FreeCAD from HermesCAD geometry.")
    parser.add_argument("--dxf", type=Path, help="Input DXF file.")
    parser.add_argument("--geometry-summary", type=Path, help="Path to geometry_summary.json.")
    parser.add_argument("--feature-plan", type=Path, help="Path to feature_plan.json.")
    parser.add_argument("--output-dir", type=Path, help="Job output directory.")
    parser.add_argument("--thickness-mm", type=float, help="Extrusion thickness in mm.")
    parser.add_argument("--chamfer-mm", type=float, default=0.0, help="Optional chamfer size in mm.")
    args, unknown = parser.parse_known_args(_argv_without_injected_script_path())

    if unknown:
        raise RuntimeError(f"Unexpected FreeCAD script arguments: {unknown}")

    if args.dxf and args.geometry_summary and args.feature_plan and args.output_dir and args.thickness_mm is not None:
        return args

    config = _load_config_from_env()
    return argparse.Namespace(
        dxf=Path(str(config["dxf"])),
        geometry_summary=Path(str(config["geometry_summary"])),
        feature_plan=Path(str(config["feature_plan"])),
        output_dir=Path(str(config["output_dir"])),
        thickness_mm=float(config["thickness_mm"]),
        chamfer_mm=float(config.get("chamfer_mm", 0.0) or 0.0),
    )


def _vector(App, point: dict[str, float]) -> object:
    return App.Vector(float(point["x"]), float(point["y"]), 0.0)


def _distance_point_to_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if math.isclose(dx, 0.0, abs_tol=1e-9) and math.isclose(dy, 0.0, abs_tol=1e-9):
        return math.hypot(px - x1, py - y1)
    projection = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    projection = max(0.0, min(1.0, projection))
    closest_x = x1 + projection * dx
    closest_y = y1 + projection * dy
    return math.hypot(px - closest_x, py - closest_y)


def _build_edge_from_segment(App, Part, segment: dict[str, object]):
    kind = str(segment["kind"])
    if kind == "line":
        return Part.makeLine(_vector(App, segment["start"]), _vector(App, segment["end"]))

    if kind == "arc":
        center = segment.get("center")
        radius = float(segment["radius"])
        start_angle_deg = float(segment["start_angle_deg"])
        sweep_angle_deg = float(segment["sweep_angle_deg"])
        if center is None:
            raise RuntimeError("Arc segment was missing a center point.")
        midpoint_angle_deg = start_angle_deg + sweep_angle_deg / 2.0
        midpoint = {
            "x": float(center["x"]) + radius * math.cos(math.radians(midpoint_angle_deg)),
            "y": float(center["y"]) + radius * math.sin(math.radians(midpoint_angle_deg)),
        }
        return Part.Arc(
            _vector(App, segment["start"]),
            _vector(App, midpoint),
            _vector(App, segment["end"]),
        ).toShape()

    if kind == "circle":
        center = segment.get("center")
        radius = float(segment["radius"])
        if center is None:
            raise RuntimeError("Circle segment was missing a center point.")
        return Part.makeCircle(radius, _vector(App, center), App.Vector(0, 0, 1))

    raise RuntimeError(f"Unsupported segment kind for FreeCAD wire generation: {kind}")


def _build_wire_from_contour(App, Part, contour: dict[str, object]):
    segments = contour.get("segments", [])
    if not segments:
        raise RuntimeError(f"Contour `{contour.get('contour_id')}` had no segments.")
    edges = [_build_edge_from_segment(App, Part, segment) for segment in segments]
    wire = Part.Wire(edges)
    if not wire.isClosed():
        raise RuntimeError(f"Contour `{contour.get('contour_id')}` did not build a closed wire.")
    return wire


def _build_face_from_contour(App, Part, contour: dict[str, object]):
    wire = _build_wire_from_contour(App, Part, contour)
    return Part.Face(wire)


def _fuse_shapes(shapes: list[object]):
    if not shapes:
        return None
    result = shapes[0]
    for shape in shapes[1:]:
        result = result.fuse(shape)
    return result


def _hole_contour_geometry(contour: dict[str, object]) -> tuple[tuple[float, float], float]:
    segments = contour.get("segments", [])
    if not segments:
        raise RuntimeError(f"Hole contour `{contour.get('contour_id')}` had no segments.")
    segment = segments[0]
    center = segment.get("center")
    radius = segment.get("radius")
    if center is None or radius is None:
        raise RuntimeError(f"Hole contour `{contour.get('contour_id')}` was missing center or radius metadata.")
    return (float(center["x"]), float(center["y"])), float(radius)


def _build_region_solid(
    App,
    Part,
    contour_id: str,
    contour_by_id: dict[str, dict[str, object]],
    thickness_mm: float,
    z_offset_mm: float = 0.0,
):
    contour = contour_by_id[contour_id]
    base_face = _build_face_from_contour(App, Part, contour)
    if z_offset_mm:
        base_face.translate(App.Vector(0, 0, z_offset_mm))
    solid = base_face.extrude(App.Vector(0, 0, thickness_mm))
    for child_id in contour.get("child_contour_ids", []):
        child_solid = _build_region_solid(App, Part, child_id, contour_by_id, thickness_mm, z_offset_mm)
        solid = solid.cut(child_solid)
    return solid


def _build_thread_groove_cut_solid(
    App,
    Part,
    *,
    center_x: float,
    center_y: float,
    z_offset_mm: float,
    depth_mm: float,
    major_diameter_mm: float,
    tap_drill_mm: float,
    thread_pitch_mm: float,
):
    major_radius_mm = major_diameter_mm / 2.0
    minor_radius_mm = tap_drill_mm / 2.0
    if major_radius_mm <= minor_radius_mm:
        raise RuntimeError("Thread major diameter must be larger than the tap-drill diameter.")
    if thread_pitch_mm <= 0:
        raise RuntimeError("Thread pitch must be positive.")

    # Use a slightly overlapping circular helical groove for robust booleans in headless FreeCAD.
    groove_radius_mm = max((major_radius_mm - minor_radius_mm) * 0.7, 0.08)
    path_radius_mm = minor_radius_mm + groove_radius_mm * 0.55
    helix = Part.makeHelix(thread_pitch_mm, depth_mm, path_radius_mm)
    helix.translate(App.Vector(center_x, center_y, z_offset_mm))
    helix_wire = Part.Wire(helix.Edges)
    profile_edge = Part.makeCircle(
        groove_radius_mm,
        App.Vector(center_x + path_radius_mm, center_y, z_offset_mm),
        App.Vector(0, 1, 0),
    )
    profile_wire = Part.Wire([profile_edge])
    thread_cut = helix_wire.makePipeShell([profile_wire], True, True)
    if thread_cut.isNull():
        raise RuntimeError("FreeCAD returned a null helical thread-cut shape.")
    return thread_cut


def _build_base_solid(App, Part, geometry: dict[str, object], thickness_mm: float):
    contours = geometry.get("contours", [])
    contour_by_id = {str(contour["contour_id"]): contour for contour in contours}
    root_ids = [
        str(contour["contour_id"])
        for contour in contours
        if contour.get("parent_contour_id") is None and contour.get("role") == "outer_profile"
    ]
    if not root_ids:
        raise RuntimeError("No top-level outer profile contours were available for contour-driven model generation.")

    solids = []
    for contour_id in root_ids:
        base_face = _build_face_from_contour(App, Part, contour_by_id[contour_id])
        solids.append(base_face.extrude(App.Vector(0, 0, thickness_mm)))
    fused = _fuse_shapes(solids)
    if fused is None:
        raise RuntimeError("Contour-driven model generation did not produce a solid.")
    return fused


def _apply_feature_operations(
    App,
    Part,
    solid,
    geometry: dict[str, object],
    feature_plan: dict[str, object],
    base_thickness_mm: float,
):
    contours = geometry.get("contours", [])
    contour_by_id = {str(contour["contour_id"]): contour for contour in contours}
    operation_summaries: list[str] = []

    for operation in feature_plan.get("operations", []):
        contour_ids = [str(contour_id) for contour_id in operation.get("contour_ids", [])]
        if not contour_ids:
            continue

        operation_kind = str(operation["kind"])
        depth_mm = float(operation["depth_mm"])
        parameters = operation.get("parameters", {})
        combine_mode = "cut"
        if operation_kind == "through_cut":
            z_offset_mm = 0.0
            extrusion_depth_mm = base_thickness_mm
            cut_solids = [
                _build_region_solid(
                    App,
                    Part,
                    contour_id=contour_id,
                    contour_by_id=contour_by_id,
                    thickness_mm=extrusion_depth_mm,
                    z_offset_mm=z_offset_mm,
                )
                for contour_id in contour_ids
            ]
        elif operation_kind == "clearance_hole":
            major_diameter_mm = float(parameters["major_diameter_mm"])
            major_radius_mm = major_diameter_mm / 2.0
            cut_solids = []
            for contour_id in contour_ids:
                contour = contour_by_id[contour_id]
                center, pilot_radius_mm = _hole_contour_geometry(contour)
                if major_radius_mm <= pilot_radius_mm:
                    continue
                cut_solids.append(
                    Part.makeCylinder(
                        major_radius_mm,
                        base_thickness_mm,
                        App.Vector(center[0], center[1], 0.0),
                        App.Vector(0, 0, 1),
                    )
                )
        elif operation_kind in {"pocket_cut", "blind_hole"}:
            extrusion_depth_mm = depth_mm
            z_offset_mm = base_thickness_mm - depth_mm
            cut_solids = [
                _build_region_solid(
                    App,
                    Part,
                    contour_id=contour_id,
                    contour_by_id=contour_by_id,
                    thickness_mm=extrusion_depth_mm,
                    z_offset_mm=z_offset_mm,
                )
                for contour_id in contour_ids
            ]
        elif operation_kind == "boss_add":
            combine_mode = "fuse"
            z_offset_mm = base_thickness_mm
            cut_solids = [
                _build_region_solid(
                    App,
                    Part,
                    contour_id=contour_id,
                    contour_by_id=contour_by_id,
                    thickness_mm=depth_mm,
                    z_offset_mm=z_offset_mm,
                )
                for contour_id in contour_ids
            ]
        elif operation_kind == "counterbore_hole":
            major_diameter_mm = float(parameters["major_diameter_mm"])
            major_radius_mm = major_diameter_mm / 2.0
            z_offset_mm = base_thickness_mm - depth_mm
            cut_solids = []
            for contour_id in contour_ids:
                contour = contour_by_id[contour_id]
                center, pilot_radius_mm = _hole_contour_geometry(contour)
                pilot_diameter_override_mm = parameters.get("pilot_diameter_mm")
                if pilot_diameter_override_mm is not None:
                    pilot_radius_mm = max(pilot_radius_mm, float(pilot_diameter_override_mm) / 2.0)
                if major_radius_mm <= pilot_radius_mm:
                    continue
                cut_solids.append(
                    Part.makeCylinder(
                        major_radius_mm,
                        depth_mm,
                        App.Vector(center[0], center[1], z_offset_mm),
                        App.Vector(0, 0, 1),
                    )
                )
        elif operation_kind == "threaded_hole":
            major_diameter_mm = float(parameters["major_diameter_mm"])
            tap_drill_mm = float(parameters["tap_drill_mm"])
            thread_pitch_mm = float(parameters["thread_pitch_mm"])
            z_offset_mm = base_thickness_mm - depth_mm
            thread_cut_solids = []
            for contour_id in contour_ids:
                contour = contour_by_id[contour_id]
                center, detected_radius_mm = _hole_contour_geometry(contour)
                detected_diameter_mm = detected_radius_mm * 2.0
                if detected_diameter_mm > tap_drill_mm + 0.15:
                    raise RuntimeError(
                        f"Cannot model a threaded hole on contour `{contour_id}` because the detected pilot diameter "
                        f"({detected_diameter_mm:g} mm) is already larger than the tap-drill diameter ({tap_drill_mm:g} mm)."
                    )
                pilot_hole = Part.makeCylinder(
                    tap_drill_mm / 2.0,
                    depth_mm,
                    App.Vector(center[0], center[1], z_offset_mm),
                    App.Vector(0, 0, 1),
                )
                solid = solid.cut(pilot_hole)
                thread_cut_solids.append(
                    _build_thread_groove_cut_solid(
                        App,
                        Part,
                        center_x=center[0],
                        center_y=center[1],
                        z_offset_mm=z_offset_mm,
                        depth_mm=depth_mm,
                        major_diameter_mm=major_diameter_mm,
                        tap_drill_mm=tap_drill_mm,
                        thread_pitch_mm=thread_pitch_mm,
                    )
                )
            cut_solids = thread_cut_solids
        elif operation_kind == "countersink_hole":
            major_diameter_mm = float(parameters["major_diameter_mm"])
            major_radius_mm = major_diameter_mm / 2.0
            transition_overlap_mm = min(0.05, max(0.01, depth_mm * 0.05))
            cut_solids = []
            for contour_id in contour_ids:
                contour = contour_by_id[contour_id]
                center, pilot_radius_mm = _hole_contour_geometry(contour)
                pilot_diameter_override_mm = parameters.get("pilot_diameter_mm")
                if pilot_diameter_override_mm is not None:
                    pilot_radius_mm = max(pilot_radius_mm, float(pilot_diameter_override_mm) / 2.0)
                if major_radius_mm <= pilot_radius_mm:
                    continue
                cone_depth_mm = min(base_thickness_mm, depth_mm + transition_overlap_mm)
                z_offset_mm = base_thickness_mm - cone_depth_mm
                minor_radius_mm = max(0.0, pilot_radius_mm - transition_overlap_mm)
                cut_solids.append(
                    Part.makeCone(
                        minor_radius_mm,
                        major_radius_mm,
                        cone_depth_mm,
                        App.Vector(center[0], center[1], z_offset_mm),
                        App.Vector(0, 0, 1),
                    )
                )
        else:
            raise RuntimeError(f"Unsupported feature operation kind: {operation_kind}")
        cut_shape = _fuse_shapes(cut_solids)
        if cut_shape is None:
            continue
        if combine_mode == "fuse":
            solid = solid.fuse(cut_shape)
        else:
            solid = solid.cut(cut_shape)
            if operation_kind == "threaded_hole":
                solid = solid.removeSplitter()
        operation_summaries.append(
            f"{operation.get('operation_id', 'op')}:{operation_kind}:{operation.get('target_kind', 'unknown')}:{len(contour_ids)} contour(s) at {depth_mm:g} mm"
        )

    return solid, operation_summaries


def _build_bbox_fallback_solid(App, Part, geometry: dict[str, object], thickness_mm: float):
    bbox = geometry.get("bounding_box", {})
    hole_candidates = geometry.get("hole_candidates", [])
    min_x = float(bbox["min_x"])
    min_y = float(bbox["min_y"])
    width = float(bbox["width"])
    height = float(bbox["height"])

    if width <= 0 or height <= 0:
        raise RuntimeError("Bounding box was invalid, so the fallback plate model could not be created.")

    plate_face = Part.makePlane(width, height, App.Vector(min_x, min_y, 0))
    solid = plate_face.extrude(App.Vector(0, 0, thickness_mm))

    for hole in hole_candidates:
        cylinder = Part.makeCylinder(
            float(hole["radius"]),
            thickness_mm,
            App.Vector(float(hole["center_x"]), float(hole["center_y"]), 0),
            App.Vector(0, 0, 1),
        )
        solid = solid.cut(cylinder)
    return solid


def _point_near_outer_boundary(
    point_xy: tuple[float, float],
    outer_contours: list[dict[str, object]],
    tolerance: float,
) -> bool:
    for contour in outer_contours:
        sampled_points = contour.get("sampled_points", [])
        if len(sampled_points) < 2:
            continue
        for index in range(len(sampled_points) - 1):
            start = sampled_points[index]
            end = sampled_points[index + 1]
            start_tuple = (float(start["x"]), float(start["y"]))
            end_tuple = (float(end["x"]), float(end["y"]))
            if _distance_point_to_segment(point_xy, start_tuple, end_tuple) <= tolerance:
                return True
    return False


def _apply_top_edge_chamfer(solid, geometry: dict[str, object], thickness_mm: float, chamfer_mm: float):
    if chamfer_mm <= 0:
        return solid, "Chamfer skipped because the requested chamfer size was not positive."

    outer_contours = [contour for contour in geometry.get("contours", []) if int(contour.get("nesting_depth", 0)) == 0]
    if not outer_contours:
        return solid, "Chamfer skipped because no top-level outer contours were available."

    boundary_tolerance = max(0.05, chamfer_mm * 0.25)
    top_edge_tolerance = 1e-6
    edges = []
    for edge in solid.Edges:
        vertices = edge.Vertexes
        if len(vertices) != 2:
            continue
        points = [vertex.Point for vertex in vertices]
        if not all(abs(point.z - thickness_mm) < top_edge_tolerance for point in points):
            continue
        midpoint = (
            (points[0].x + points[1].x) / 2.0,
            (points[0].y + points[1].y) / 2.0,
        )
        if _point_near_outer_boundary(midpoint, outer_contours, boundary_tolerance):
            edges.append(edge)

    if not edges:
        return solid, "Chamfer skipped because no suitable exterior top edges were identified."

    try:
        return solid.makeChamfer(chamfer_mm, edges), f"Applied {chamfer_mm:g} mm chamfer to exterior top edges."
    except Exception as exc:  # pragma: no cover - depends on FreeCAD geometry behavior
        return solid, f"Chamfer failed: {exc}"


def main() -> int:
    args = _parse_args()

    App, Part, Mesh, Import = _load_freecad_modules()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    geometry = json.loads(args.geometry_summary.read_text(encoding="utf-8"))
    feature_plan = json.loads(args.feature_plan.read_text(encoding="utf-8"))
    contours = geometry.get("contours", [])

    modeling_strategy = "bounding_box_fallback"
    operation_summaries: list[str] = []
    if contours and geometry.get("outer_profile_ids"):
        solid = _build_base_solid(App, Part, geometry, args.thickness_mm)
        solid, operation_summaries = _apply_feature_operations(
            App,
            Part,
            solid,
            geometry,
            feature_plan,
            args.thickness_mm,
        )
        modeling_strategy = "feature_plan_contour_regions"
    else:
        solid = _build_bbox_fallback_solid(App, Part, geometry, args.thickness_mm)

    chamfer_status = "Chamfer skipped."
    has_countersinks = any(operation.get("kind") == "countersink_hole" for operation in feature_plan.get("operations", []))
    if args.chamfer_mm and has_countersinks:
        chamfer_status = (
            "Chamfer skipped because countersink operations were present. "
            "HermesCAD currently avoids combining exterior chamfers with countersinks in the same run for robustness."
        )
    elif args.chamfer_mm:
        solid, chamfer_status = _apply_top_edge_chamfer(
            solid,
            geometry=geometry,
            thickness_mm=args.thickness_mm,
            chamfer_mm=args.chamfer_mm,
        )

    document = App.newDocument("HermesCAD")
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
        "feature_plan": str(args.feature_plan.resolve()),
        "outputs": [
            str(fcstd_path.resolve()),
            str(step_path.resolve()),
            str(stl_path.resolve()),
        ],
        "modeling_strategy": modeling_strategy,
        "closed_contours": int(geometry.get("closed_contour_count", 0) or 0),
        "outer_profiles": list(geometry.get("outer_profile_ids", [])),
        "cutouts": list(geometry.get("cutout_ids", [])),
        "holes": list(geometry.get("hole_contour_ids", [])),
        "operation_summaries": operation_summaries,
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
