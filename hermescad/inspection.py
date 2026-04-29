from __future__ import annotations

import json
from pathlib import Path

import ezdxf

from .models import BoundingBox, GeometrySummary, HoleCandidate

INSUNITS_MAP = {
    0: None,
    1: "Inches",
    2: "Feet",
    4: "Millimeters",
    5: "Centimeters",
    6: "Meters",
}


def _update_bounds(bounds: dict[str, float], points: list[tuple[float, float]]) -> None:
    for x_value, y_value in points:
        bounds["min_x"] = min(bounds["min_x"], float(x_value))
        bounds["min_y"] = min(bounds["min_y"], float(y_value))
        bounds["max_x"] = max(bounds["max_x"], float(x_value))
        bounds["max_y"] = max(bounds["max_y"], float(y_value))


def _bbox_from_bounds(bounds: dict[str, float]) -> BoundingBox:
    if bounds["min_x"] == float("inf"):
        return BoundingBox()
    return BoundingBox(
        min_x=bounds["min_x"],
        min_y=bounds["min_y"],
        max_x=bounds["max_x"],
        max_y=bounds["max_y"],
        width=bounds["max_x"] - bounds["min_x"],
        height=bounds["max_y"] - bounds["min_y"],
    )


def inspect_dxf_file(
    source_file: Path,
    output_dir: Path,
    effective_input_file: Path | None = None,
) -> GeometrySummary:
    source_file = source_file.resolve()
    effective_input_file = (effective_input_file or source_file).resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        document = ezdxf.readfile(effective_input_file)
    except Exception as exc:
        raise RuntimeError(f"Failed to read DXF file `{effective_input_file}`: {exc}") from exc

    modelspace = document.modelspace()
    bounds = {
        "min_x": float("inf"),
        "min_y": float("inf"),
        "max_x": float("-inf"),
        "max_y": float("-inf"),
    }
    entity_counts: dict[str, int] = {}
    hole_candidates: list[HoleCandidate] = []
    notes: list[str] = []

    for entity in modelspace:
        entity_type = entity.dxftype()
        entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

        if entity_type == "LINE":
            _update_bounds(
                bounds,
                [
                    (entity.dxf.start.x, entity.dxf.start.y),
                    (entity.dxf.end.x, entity.dxf.end.y),
                ],
            )
        elif entity_type == "LWPOLYLINE":
            points = [(point[0], point[1]) for point in entity.get_points("xy")]
            _update_bounds(bounds, points)
        elif entity_type == "POLYLINE":
            points: list[tuple[float, float]] = []
            vertices = getattr(entity, "vertices", None)
            if callable(vertices):
                points = [(vertex.dxf.location.x, vertex.dxf.location.y) for vertex in vertices()]
            elif vertices is not None:
                points = [(vertex.dxf.location.x, vertex.dxf.location.y) for vertex in vertices]
            if points:
                _update_bounds(bounds, points)
        elif entity_type == "CIRCLE":
            center_x = float(entity.dxf.center.x)
            center_y = float(entity.dxf.center.y)
            radius = float(entity.dxf.radius)
            _update_bounds(
                bounds,
                [
                    (center_x - radius, center_y - radius),
                    (center_x + radius, center_y + radius),
                ],
            )
            hole_candidates.append(
                HoleCandidate(
                    center_x=center_x,
                    center_y=center_y,
                    radius=radius,
                    diameter=radius * 2.0,
                )
            )
        elif entity_type == "ARC":
            center_x = float(entity.dxf.center.x)
            center_y = float(entity.dxf.center.y)
            radius = float(entity.dxf.radius)
            _update_bounds(
                bounds,
                [
                    (center_x - radius, center_y - radius),
                    (center_x + radius, center_y + radius),
                ],
            )
        else:
            notes.append(f"Entity type `{entity_type}` is preserved in counts but not specially analysed.")

    insunits_value = int(document.header.get("$INSUNITS", 0) or 0)
    geometry_summary = GeometrySummary(
        source_file=str(source_file),
        effective_input_file=str(effective_input_file),
        file_type="dxf",
        units=INSUNITS_MAP.get(insunits_value),
        entity_counts=entity_counts,
        bounding_box=_bbox_from_bounds(bounds),
        hole_candidates=hole_candidates,
        warnings=[],
        notes=notes,
    )

    if geometry_summary.units is None:
        geometry_summary.warnings.append(
            "DXF units were not embedded in the file. HermesCAD should confirm units unless the request text is explicit."
        )

    geometry_summary_path = output_dir / "geometry_summary.json"
    geometry_summary.geometry_summary_path = str(geometry_summary_path)
    geometry_summary_path.write_text(
        json.dumps(geometry_summary.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return geometry_summary

