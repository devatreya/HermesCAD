from __future__ import annotations

import argparse
import json
import os
import re
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


def _activate_document_view(document) -> None:
    try:  # pragma: no cover - depends on FreeCAD GUI availability
        import FreeCAD as App
        import FreeCADGui as Gui
    except Exception:
        return

    try:
        App.setActiveDocument(document.Name)
    except Exception:
        pass

    try:
        Gui.setActiveDocument(document.Name)
    except Exception:
        pass

    try:
        gui_document = Gui.activeDocument()
    except Exception:
        gui_document = None

    if gui_document is None and hasattr(Gui, "getDocument"):
        try:
            gui_document = Gui.getDocument(document.Name)
        except Exception:
            gui_document = None

    if gui_document is None:
        return

    for document_object in getattr(document, "Objects", []):
        view_object = getattr(document_object, "ViewObject", None)
        if view_object is None:
            continue
        try:
            view_object.Visibility = True
        except Exception:
            pass
        try:
            view_object.DisplayMode = "Shaded"
        except Exception:
            pass

    try:
        view = gui_document.activeView()
        if view is not None:
            view.viewAxonometric()
            view.fitAll()
    except Exception:
        pass

    try:
        Gui.updateGui()
    except Exception:
        pass


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


def _load_fasteners_module():
    try:
        import FastenersCmd
    except Exception as exc:  # pragma: no cover - depends on FreeCAD addon availability
        return None, f"Fasteners workbench was unavailable in this FreeCAD environment: {exc}"
    return FastenersCmd, None


def _sanitize_object_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    sanitized = sanitized.strip("_")
    return sanitized or "HermesCADFastener"


def _format_length_token(length_mm: float) -> str:
    rounded = round(length_mm)
    if abs(length_mm - rounded) < 1e-6:
        return str(int(rounded))
    return f"{length_mm:g}"


def _set_fastener_length(fastener_object, length_mm: float) -> None:
    if not hasattr(fastener_object, "Length"):
        return

    length_token = _format_length_token(length_mm)
    current_length = getattr(fastener_object, "Length")
    if isinstance(current_length, str):
        length_options = list(fastener_object.getEnumerationsOfProperty("Length"))
        if length_token in length_options:
            fastener_object.Length = length_token
            return
        if "Custom" in length_options and hasattr(fastener_object, "LengthCustom"):
            fastener_object.Length = "Custom"
            fastener_object.LengthCustom = float(length_mm)
            return
        raise RuntimeError(
            f"Requested fastener length `{length_mm:g}` mm was not available for this fastener type and no custom length was supported."
        )

    fastener_object.Length = float(length_mm)


def _build_fastener_placement(App, part_object, local_bbox, hole_center: dict[str, object], head_side: str, offset_mm: float):
    local_z = float(local_bbox.ZMax if head_side == "positive_z" else local_bbox.ZMin)
    offset_mm = float(offset_mm)
    if head_side == "positive_z":
        local_base = App.Vector(float(hole_center["x_mm"]), float(hole_center["y_mm"]), local_z + offset_mm)
        local_rotation = App.Rotation()
    else:
        local_base = App.Vector(float(hole_center["x_mm"]), float(hole_center["y_mm"]), local_z - offset_mm)
        local_rotation = App.Rotation(App.Vector(1, 0, 0), 180.0)

    world_base = part_object.Placement.multVec(local_base)
    world_rotation = part_object.Placement.Rotation.multiply(local_rotation)
    return App.Placement(world_base, world_rotation)


def _insert_fasteners(document, App, config_payload: dict[str, object], part_objects_by_name, local_bboxes_by_name):
    fastener_specs = list(config_payload.get("fasteners", []))
    if not fastener_specs:
        return [], [], []

    FastenersCmd, import_error = _load_fasteners_module()
    if FastenersCmd is None:
        return [], [import_error or "Fasteners workbench was unavailable."], []

    fastener_objects = []
    fastener_warnings: list[str] = []
    fastener_summaries: list[dict[str, object]] = []

    for fastener_spec in fastener_specs:
        if not isinstance(fastener_spec, dict):
            fastener_warnings.append("Skipped a malformed fastener spec because it was not a JSON object.")
            continue

        source_part = str(fastener_spec.get("source_part", ""))
        standard = str(fastener_spec.get("standard", "ISO4762"))
        diameter = str(fastener_spec.get("diameter", ""))
        length_mm = float(fastener_spec.get("length_mm", 0.0))
        thread_mode = str(fastener_spec.get("thread_mode", "real")).lower()
        head_side = str(fastener_spec.get("head_side", "positive_z"))
        offset_mm = float(fastener_spec.get("offset_mm", 0.0))
        hole_centers = list(fastener_spec.get("hole_centers_local_mm", []))
        summary = {
            "name": fastener_spec.get("name"),
            "standard": standard,
            "diameter": diameter,
            "length_mm": length_mm,
            "source_part": source_part,
            "hole_selector": fastener_spec.get("hole_selector"),
            "inserted_count": 0,
        }

        part_object = part_objects_by_name.get(source_part)
        local_bbox = local_bboxes_by_name.get(source_part)
        if part_object is None or local_bbox is None:
            fastener_warnings.append(
                f"Fastener group `{fastener_spec.get('name', 'unnamed')}` referenced source part `{source_part}`, but that part was not available in the assembly document."
            )
            fastener_summaries.append(summary)
            continue

        if not hole_centers:
            fastener_warnings.append(
                f"Fastener group `{fastener_spec.get('name', 'unnamed')}` had no resolved hole centers, so no fastener bodies were inserted."
            )
            fastener_summaries.append(summary)
            continue

        inserted_count = 0
        for index, hole_center in enumerate(hole_centers, start=1):
            object_name = _sanitize_object_name(f"{fastener_spec.get('name', source_part)}_{index:02d}")
            fastener_object = None
            try:
                fastener_object = document.addObject("Part::FeaturePython", object_name)
                FastenersCmd.FSScrewObject(fastener_object, standard, None)
                fastener_object.Diameter = diameter
                document.recompute()
                _set_fastener_length(fastener_object, length_mm)
                if hasattr(fastener_object, "Thread"):
                    fastener_object.Thread = thread_mode == "real"
                document.recompute()
                fastener_object.Placement = _build_fastener_placement(
                    App,
                    part_object,
                    local_bbox,
                    hole_center,
                    head_side,
                    offset_mm,
                )
                fastener_object.Label = f"{fastener_spec.get('name', source_part)}_{index:02d}"
                inserted_count += 1
                fastener_objects.append(fastener_object)
            except Exception as exc:
                if fastener_object is not None:
                    try:
                        document.removeObject(fastener_object.Name)
                    except Exception:
                        pass
                fastener_warnings.append(
                    f"Failed to insert `{standard}` `{diameter}` fastener `{fastener_spec.get('name', source_part)}` at hole index {index}: {exc}"
                )
        summary["inserted_count"] = inserted_count
        fastener_summaries.append(summary)

    if fastener_objects:
        document.recompute()
    return fastener_objects, fastener_warnings, fastener_summaries


def main() -> int:
    args = _parse_args()
    config_payload = json.loads(args.config.read_text(encoding="utf-8"))

    App, Part, Mesh, Import = _load_freecad_modules()
    output_dir = Path(str(config_payload["output_dir"])).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    document = App.newDocument(str(config_payload.get("assembly_name", "HermesCADAssembly")))
    part_objects = []
    part_objects_by_name = {}
    local_bboxes_by_name = {}
    placements_summary: list[dict[str, object]] = []

    for part_spec in config_payload.get("parts", []):
        step_path = Path(str(part_spec["step_path"])).resolve()
        if not step_path.exists():
            raise RuntimeError(f"Assembly part STEP file was not found: {step_path}")

        part_shape = Part.read(str(step_path))
        part_object = document.addObject("Part::Feature", str(part_spec["name"]))
        local_bboxes_by_name[str(part_spec["name"])] = part_shape.BoundBox
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
        part_objects_by_name[str(part_spec["name"])] = part_object

    document.recompute()
    fastener_objects, fastener_warnings, fastener_summaries = _insert_fasteners(
        document,
        App,
        config_payload,
        part_objects_by_name,
        local_bboxes_by_name,
    )
    _activate_document_view(document)

    fcstd_path = output_dir / "hermescad_assembly.FCStd"
    step_path = output_dir / "hermescad_assembly.step"
    stl_path = output_dir / "hermescad_assembly.stl"
    export_objects = part_objects + fastener_objects

    document.saveAs(str(fcstd_path))
    Import.export(export_objects, str(step_path))
    Mesh.export(export_objects, str(stl_path))

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
        "fastener_count": len(fastener_objects),
        "fasteners": fastener_summaries,
        "fastener_warnings": fastener_warnings,
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
