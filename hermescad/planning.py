from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .models import FeatureOperation, FeaturePlan, GeometrySummary

HOLE_DEPTH_PATTERNS = [
    re.compile(r"(?:blind\s+)?holes?(?:\s+\w+){0,5}\s+(\d+(?:\.\d+)?)\s*mm\s*deep", re.IGNORECASE),
    re.compile(r"(?:blind\s+)?holes?(?:\s+\w+){0,5}\s+depth\s+of\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
]
SLOT_DEPTH_PATTERNS = [
    re.compile(r"slots?(?:\s+\w+){0,5}\s+(\d+(?:\.\d+)?)\s*mm\s*deep", re.IGNORECASE),
    re.compile(r"slots?(?:\s+\w+){0,5}\s+depth\s+of\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
]
CUTOUT_DEPTH_PATTERNS = [
    re.compile(
        r"(?:windows?|cutouts?|internal\s+cutouts?)(?:\s+\w+){0,5}\s+(\d+(?:\.\d+)?)\s*mm\s*deep",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:windows?|cutouts?|internal\s+cutouts?)(?:\s+\w+){0,5}\s+depth\s+of\s+(\d+(?:\.\d+)?)\s*mm",
        re.IGNORECASE,
    ),
]
POCKET_DEPTH_PATTERNS = [
    re.compile(r"pockets?(?:\s+\w+){0,5}\s+(\d+(?:\.\d+)?)\s*mm\s*deep", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*mm\s*deep\s+pockets?", re.IGNORECASE),
    re.compile(r"pockets?(?:\s+\w+){0,5}\s+depth\s+of\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
]
COUNTERBORE_DIAMETER_PATTERNS = [
    re.compile(r"counterbores?(?:\s+\w+){0,6}\s+(\d+(?:\.\d+)?)\s*mm\s*(?:major\s+diameter|diameter|dia)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*mm\s*(?:major\s+diameter|diameter|dia)\s*counterbores?", re.IGNORECASE),
]
COUNTERBORE_DEPTH_PATTERNS = [
    re.compile(r"counterbores?(?:\s+\w+){0,6}\s+(\d+(?:\.\d+)?)\s*mm\s*deep", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*mm\s*deep\s*counterbores?", re.IGNORECASE),
]
COUNTERSINK_DIAMETER_PATTERNS = [
    re.compile(r"countersinks?(?:\s+\w+){0,6}\s+(\d+(?:\.\d+)?)\s*mm\s*(?:major\s+diameter|diameter|dia)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*mm\s*(?:major\s+diameter|diameter|dia)\s*countersinks?", re.IGNORECASE),
]
COUNTERSINK_ANGLE_PATTERNS = [
    re.compile(r"countersinks?(?:\s+\w+){0,6}\s+(\d+(?:\.\d+)?)\s*(?:degree|degrees)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:degree|degrees)\s*countersinks?", re.IGNORECASE),
]
BOSS_HEIGHT_PATTERNS = [
    re.compile(r"(?:boss(?:es)?|islands?|pads?)(?:\s+\w+){0,6}\s+(\d+(?:\.\d+)?)\s*mm\s*(?:high|tall)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*mm\s*(?:high|tall)\s*(?:boss(?:es)?|islands?|pads?)", re.IGNORECASE),
    re.compile(r"raise(?:\s+\w+){0,8}\s+(?:the\s+)?(?:boss(?:es)?|islands?|pads?)(?:\s+\w+){0,4}\s+by\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
]
INSTRUCTION_CLAUSE_SPLIT_PATTERN = re.compile(r"[.;\n]+|\band\s+(?=(?:make|add|cut|drill)\b)", re.IGNORECASE)
METRIC_SCREW_PATTERN = re.compile(r"\b(M\d+(?:\.\d+)?)\b", re.IGNORECASE)

METRIC_SCREW_PRESETS: dict[str, dict[str, float]] = {
    "M3": {
        "major_diameter_mm": 3.0,
        "tap_drill_mm": 2.5,
        "thread_pitch_mm": 0.5,
        "clearance_mm": 3.4,
        "socket_head_counterbore_diameter_mm": 5.5,
        "socket_head_counterbore_depth_mm": 3.0,
        "countersink_major_diameter_mm": 6.0,
        "countersink_angle_deg": 90.0,
    },
    "M4": {
        "major_diameter_mm": 4.0,
        "tap_drill_mm": 3.3,
        "thread_pitch_mm": 0.7,
        "clearance_mm": 4.5,
        "socket_head_counterbore_diameter_mm": 7.0,
        "socket_head_counterbore_depth_mm": 4.0,
        "countersink_major_diameter_mm": 8.0,
        "countersink_angle_deg": 90.0,
    },
    "M5": {
        "major_diameter_mm": 5.0,
        "tap_drill_mm": 4.2,
        "thread_pitch_mm": 0.8,
        "clearance_mm": 5.5,
        "socket_head_counterbore_diameter_mm": 8.5,
        "socket_head_counterbore_depth_mm": 5.0,
        "countersink_major_diameter_mm": 10.0,
        "countersink_angle_deg": 90.0,
    },
    "M6": {
        "major_diameter_mm": 6.0,
        "tap_drill_mm": 5.0,
        "thread_pitch_mm": 1.0,
        "clearance_mm": 6.6,
        "socket_head_counterbore_diameter_mm": 10.0,
        "socket_head_counterbore_depth_mm": 6.0,
        "countersink_major_diameter_mm": 12.0,
        "countersink_angle_deg": 90.0,
    },
    "M8": {
        "major_diameter_mm": 8.0,
        "tap_drill_mm": 6.8,
        "thread_pitch_mm": 1.25,
        "clearance_mm": 9.0,
        "socket_head_counterbore_diameter_mm": 13.0,
        "socket_head_counterbore_depth_mm": 8.0,
        "countersink_major_diameter_mm": 16.0,
        "countersink_angle_deg": 90.0,
    },
}


def _extract_measurement(text: str, patterns: list[re.Pattern[str]]) -> float | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


def _split_instruction_clauses(text: str) -> list[str]:
    clauses = []
    for clause in INSTRUCTION_CLAUSE_SPLIT_PATTERN.split(text):
        cleaned = clause.strip(" ,")
        if cleaned:
            clauses.append(cleaned)
    return clauses


def _normalize_metric_screw_size(raw_size: str) -> str:
    return raw_size.upper().replace(" ", "")


def _detect_hole_selector(clause: str) -> str:
    lowered = clause.lower()
    if "corner hole" in lowered:
        return "corner"
    if "centre hole" in lowered or "center hole" in lowered or "middle hole" in lowered:
        return "center"
    if "top hole" in lowered:
        return "top"
    if "bottom hole" in lowered:
        return "bottom"
    if "left hole" in lowered:
        return "left"
    if "right hole" in lowered:
        return "right"
    if "largest hole" in lowered:
        return "largest"
    if "smallest hole" in lowered:
        return "smallest"
    return "all"


def _detect_contour_selector(clause: str) -> str:
    lowered = clause.lower()
    if "corner" in lowered:
        return "corner"
    if "centre" in lowered or "center" in lowered or "central" in lowered or "middle" in lowered:
        return "center"
    if "top" in lowered or "upper" in lowered:
        return "top"
    if "bottom" in lowered or "lower" in lowered:
        return "bottom"
    if "left" in lowered:
        return "left"
    if "right" in lowered:
        return "right"
    if "largest" in lowered or re.search(r"\blarge\b", lowered):
        return "largest"
    if "smallest" in lowered or re.search(r"\bsmall\b", lowered):
        return "smallest"
    return "all"


def _dedupe_contour_ids(contour_ids: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for contour_id in contour_ids:
        if contour_id not in seen:
            seen.add(contour_id)
            deduped.append(contour_id)
    return deduped


def _hole_selection_tolerance(geometry_summary: GeometrySummary) -> float:
    bbox = geometry_summary.bounding_box
    span = max(bbox.width or 0.0, bbox.height or 0.0, 1.0)
    return max(0.5, span * 0.02)


def _contour_selection_tolerance(geometry_summary: GeometrySummary) -> float:
    bbox = geometry_summary.bounding_box
    span = max(bbox.width or 0.0, bbox.height or 0.0, 1.0)
    return max(1.0, span * 0.05)


def _select_hole_contour_ids(
    geometry_summary: GeometrySummary,
    selector: str,
) -> list[str]:
    holes = [hole for hole in geometry_summary.hole_candidates if hole.contour_id]
    if not holes:
        return []

    if selector == "all":
        return [str(hole.contour_id) for hole in holes if hole.contour_id]

    if selector == "largest":
        max_diameter = max(hole.diameter for hole in holes)
        return [
            str(hole.contour_id)
            for hole in holes
            if hole.contour_id and math.isclose(hole.diameter, max_diameter, abs_tol=1e-6)
        ]

    if selector == "smallest":
        min_diameter = min(hole.diameter for hole in holes)
        return [
            str(hole.contour_id)
            for hole in holes
            if hole.contour_id and math.isclose(hole.diameter, min_diameter, abs_tol=1e-6)
        ]

    if selector == "center":
        center_x = sum(hole.center_x for hole in holes) / len(holes)
        center_y = sum(hole.center_y for hole in holes) / len(holes)
        nearest = min(
            holes,
            key=lambda hole: math.hypot(hole.center_x - center_x, hole.center_y - center_y),
        )
        return [str(nearest.contour_id)] if nearest.contour_id else []

    tolerance = _hole_selection_tolerance(geometry_summary)
    x_values = [hole.center_x for hole in holes]
    y_values = [hole.center_y for hole in holes]
    min_x = min(x_values)
    max_x = max(x_values)
    min_y = min(y_values)
    max_y = max(y_values)

    if selector == "top":
        return [
            str(hole.contour_id)
            for hole in holes
            if hole.contour_id and hole.center_y >= max_y - tolerance
        ]
    if selector == "bottom":
        return [
            str(hole.contour_id)
            for hole in holes
            if hole.contour_id and hole.center_y <= min_y + tolerance
        ]
    if selector == "left":
        return [
            str(hole.contour_id)
            for hole in holes
            if hole.contour_id and hole.center_x <= min_x + tolerance
        ]
    if selector == "right":
        return [
            str(hole.contour_id)
            for hole in holes
            if hole.contour_id and hole.center_x >= max_x - tolerance
        ]
    if selector == "corner":
        top_ids = set(_select_hole_contour_ids(geometry_summary, "top"))
        bottom_ids = set(_select_hole_contour_ids(geometry_summary, "bottom"))
        left_ids = set(_select_hole_contour_ids(geometry_summary, "left"))
        right_ids = set(_select_hole_contour_ids(geometry_summary, "right"))
        corner_ids = (top_ids | bottom_ids) & (left_ids | right_ids)
        return [str(hole.contour_id) for hole in holes if hole.contour_id and str(hole.contour_id) in corner_ids]

    return [str(hole.contour_id) for hole in holes if hole.contour_id]


def _selected_hole_diameters(
    contour_ids: list[str],
    hole_diameter_by_id: dict[str, float],
) -> list[float]:
    return [hole_diameter_by_id[contour_id] for contour_id in contour_ids if contour_id in hole_diameter_by_id]


def _select_contour_ids(
    geometry_summary: GeometrySummary,
    candidate_ids: list[str],
    selector: str,
) -> list[str]:
    contour_by_id = {contour.contour_id: contour for contour in geometry_summary.contours}
    candidates = [contour_by_id[contour_id] for contour_id in candidate_ids if contour_id in contour_by_id]
    if not candidates:
        return []

    if selector == "all":
        return [contour.contour_id for contour in candidates]

    if selector == "largest":
        max_area = max(abs(contour.area) for contour in candidates)
        return [
            contour.contour_id
            for contour in candidates
            if math.isclose(abs(contour.area), max_area, abs_tol=1e-6)
        ]

    if selector == "smallest":
        min_area = min(abs(contour.area) for contour in candidates)
        return [
            contour.contour_id
            for contour in candidates
            if math.isclose(abs(contour.area), min_area, abs_tol=1e-6)
        ]

    centers: dict[str, tuple[float, float]] = {}
    for contour in candidates:
        bbox = contour.bounding_box
        if None in {bbox.min_x, bbox.max_x, bbox.min_y, bbox.max_y}:
            continue
        centers[contour.contour_id] = (
            float(bbox.min_x + bbox.max_x) / 2.0,
            float(bbox.min_y + bbox.max_y) / 2.0,
        )

    if not centers:
        return [contour.contour_id for contour in candidates]

    if selector == "center":
        bbox = geometry_summary.bounding_box
        if None in {bbox.min_x, bbox.max_x, bbox.min_y, bbox.max_y}:
            center_x = sum(point[0] for point in centers.values()) / len(centers)
            center_y = sum(point[1] for point in centers.values()) / len(centers)
        else:
            center_x = float(bbox.min_x + bbox.max_x) / 2.0
            center_y = float(bbox.min_y + bbox.max_y) / 2.0
        nearest_id = min(
            centers,
            key=lambda contour_id: math.hypot(centers[contour_id][0] - center_x, centers[contour_id][1] - center_y),
        )
        return [nearest_id]

    tolerance = _contour_selection_tolerance(geometry_summary)
    x_values = [center[0] for center in centers.values()]
    y_values = [center[1] for center in centers.values()]
    min_x = min(x_values)
    max_x = max(x_values)
    min_y = min(y_values)
    max_y = max(y_values)

    if selector == "top":
        return [contour_id for contour_id, center in centers.items() if center[1] >= max_y - tolerance]
    if selector == "bottom":
        return [contour_id for contour_id, center in centers.items() if center[1] <= min_y + tolerance]
    if selector == "left":
        return [contour_id for contour_id, center in centers.items() if center[0] <= min_x + tolerance]
    if selector == "right":
        return [contour_id for contour_id, center in centers.items() if center[0] >= max_x - tolerance]
    if selector == "corner":
        top_ids = set(_select_contour_ids(geometry_summary, candidate_ids, "top"))
        bottom_ids = set(_select_contour_ids(geometry_summary, candidate_ids, "bottom"))
        left_ids = set(_select_contour_ids(geometry_summary, candidate_ids, "left"))
        right_ids = set(_select_contour_ids(geometry_summary, candidate_ids, "right"))
        corner_ids = (top_ids | bottom_ids) & (left_ids | right_ids)
        return [contour.contour_id for contour in candidates if contour.contour_id in corner_ids]

    return [contour.contour_id for contour in candidates]


def _coerce_depth(
    requested_depth_mm: float,
    base_thickness_mm: float,
    target_kind: str,
) -> tuple[str, float, list[str]]:
    notes: list[str] = []
    if requested_depth_mm <= 0:
        raise ValueError("Feature depth must be positive.")
    if requested_depth_mm >= base_thickness_mm:
        notes.append(
            f"Requested {target_kind} depth {requested_depth_mm:g} mm reaches or exceeds the base thickness, so it was treated as a through-cut."
        )
        return "through_cut", base_thickness_mm, notes
    if target_kind == "holes":
        return "blind_hole", requested_depth_mm, notes
    return "pocket_cut", requested_depth_mm, notes


def _append_operation(
    plan: FeaturePlan,
    *,
    target_kind: str,
    contour_ids: list[str],
    base_thickness_mm: float,
    requested_depth_mm: float,
    kind_override: str | None = None,
    parameters: dict[str, object] | None = None,
) -> None:
    if not contour_ids:
        plan.warnings.append(
            f"The request described `{target_kind}`, but no matching contour targets were found in the geometry summary."
        )
        return

    if kind_override is None:
        operation_kind, effective_depth_mm, notes = _coerce_depth(
            requested_depth_mm=requested_depth_mm,
            base_thickness_mm=base_thickness_mm,
            target_kind=target_kind,
        )
    else:
        if requested_depth_mm <= 0:
            raise ValueError("Feature depth must be positive.")
        if requested_depth_mm > base_thickness_mm:
            raise ValueError("Feature depth cannot exceed the base thickness.")
        operation_kind = kind_override
        effective_depth_mm = requested_depth_mm
        notes = []
    plan.operations.append(
        FeatureOperation(
            operation_id=f"op_{len(plan.operations) + 1:03d}",
            kind=operation_kind,
            target_kind=target_kind,
            contour_ids=contour_ids,
            depth_mm=effective_depth_mm,
            parameters=parameters or {},
            notes=notes,
        )
    )


def _append_metric_screw_operations(
    plan: FeaturePlan,
    *,
    instruction_text: str,
    geometry_summary: GeometrySummary,
    thickness_mm: float,
    hole_ids: list[str],
    hole_diameter_by_id: dict[str, float],
    blocked_hole_ids: set[str] | None = None,
) -> None:
    if not hole_ids:
        return

    blocked_hole_ids = blocked_hole_ids or set()
    screw_defaults_used = False
    for clause in _split_instruction_clauses(instruction_text):
        lowered = clause.lower()
        if "hole" not in lowered:
            continue

        size_match = METRIC_SCREW_PATTERN.search(clause)
        has_screw_context = any(
            token in lowered
            for token in [
                "clearance",
                "screw hole",
                "screw holes",
                "socket head",
                "shcs",
                "counterbore",
                "counterbored",
                "countersunk",
                "flat head",
            ]
        )
        if not size_match or not has_screw_context:
            continue

        screw_size = _normalize_metric_screw_size(size_match.group(1))
        preset = METRIC_SCREW_PRESETS.get(screw_size)
        if preset is None:
            plan.warnings.append(
                f"Metric screw-hole preset `{screw_size}` is not available. HermesCAD currently supports {', '.join(sorted(METRIC_SCREW_PRESETS))}."
            )
            continue

        selector = _detect_hole_selector(clause)
        target_ids = _dedupe_contour_ids(_select_hole_contour_ids(geometry_summary, selector))
        if not target_ids:
            plan.warnings.append(
                f"The request described `{selector}` screw-hole targets, but HermesCAD could not resolve matching circular hole contours."
            )
            continue

        blocked_target_ids = [contour_id for contour_id in target_ids if contour_id in blocked_hole_ids]
        if blocked_target_ids:
            plan.warnings.append(
                f"The `{selector}` screw-hole preset overlapped with blind-hole targets. HermesCAD skipped the screw-hole preset on those holes instead of overriding the requested hole depth."
            )
            target_ids = [contour_id for contour_id in target_ids if contour_id not in blocked_hole_ids]
        if not target_ids:
            continue

        selected_diameters = _selected_hole_diameters(target_ids, hole_diameter_by_id)
        if not selected_diameters:
            plan.warnings.append(
                f"HermesCAD could not resolve the existing circular-hole diameters for the `{selector}` screw-hole targets."
            )
            continue

        max_selected_diameter = max(selected_diameters)
        if max_selected_diameter > preset["clearance_mm"] + 1e-6:
            plan.warnings.append(
                f"The `{selector}` holes are already larger than the requested {screw_size} clearance diameter. HermesCAD will keep the existing pilot-hole diameter and only apply compatible head-form features."
            )
        effective_pilot_diameter_mm = max(max_selected_diameter, preset["clearance_mm"])
        screw_defaults_used = True

        _append_operation(
            plan,
            target_kind="holes",
            contour_ids=target_ids,
            base_thickness_mm=thickness_mm,
            requested_depth_mm=thickness_mm,
            kind_override="clearance_hole",
            parameters={
                "major_diameter_mm": preset["clearance_mm"],
                "screw_size": screw_size,
                "selector": selector,
            },
        )

        if "socket head" in lowered or "shcs" in lowered or "counterbored" in lowered:
            _append_operation(
                plan,
                target_kind="holes",
                contour_ids=target_ids,
                base_thickness_mm=thickness_mm,
                requested_depth_mm=preset["socket_head_counterbore_depth_mm"],
                kind_override="counterbore_hole",
                parameters={
                    "major_diameter_mm": preset["socket_head_counterbore_diameter_mm"],
                    "pilot_diameter_mm": effective_pilot_diameter_mm,
                    "screw_size": screw_size,
                    "selector": selector,
                },
            )
            plan.notes.append(
                f"{screw_size} socket-head screw defaults were applied to the `{selector}` holes: {preset['clearance_mm']:g} mm clearance, {preset['socket_head_counterbore_diameter_mm']:g} mm counterbore diameter, {preset['socket_head_counterbore_depth_mm']:g} mm counterbore depth."
            )
            continue

        if "countersunk" in lowered or "flat head" in lowered:
            major_radius_mm = preset["countersink_major_diameter_mm"] / 2.0
            pilot_radius_mm = effective_pilot_diameter_mm / 2.0
            half_angle_rad = math.radians(preset["countersink_angle_deg"] / 2.0)
            if major_radius_mm <= pilot_radius_mm or math.isclose(math.tan(half_angle_rad), 0.0, abs_tol=1e-9):
                plan.warnings.append(
                    f"{screw_size} countersunk screw defaults could not be applied safely to the `{selector}` holes."
                )
                continue
            countersink_depth_mm = (major_radius_mm - pilot_radius_mm) / math.tan(half_angle_rad)
            if countersink_depth_mm > thickness_mm:
                plan.warnings.append(
                    f"{screw_size} countersunk screw defaults would exceed the base thickness on the `{selector}` holes, so the countersink was skipped."
                )
                continue
            _append_operation(
                plan,
                target_kind="holes",
                contour_ids=target_ids,
                base_thickness_mm=thickness_mm,
                requested_depth_mm=countersink_depth_mm,
                kind_override="countersink_hole",
                parameters={
                    "major_diameter_mm": preset["countersink_major_diameter_mm"],
                    "included_angle_deg": preset["countersink_angle_deg"],
                    "pilot_diameter_mm": effective_pilot_diameter_mm,
                    "screw_size": screw_size,
                    "selector": selector,
                },
            )
            plan.notes.append(
                f"{screw_size} countersunk screw defaults were applied to the `{selector}` holes: {preset['clearance_mm']:g} mm clearance, {preset['countersink_major_diameter_mm']:g} mm countersink diameter at {preset['countersink_angle_deg']:g} degrees."
            )
            continue

        if "clearance" in lowered or "screw hole" in lowered or "screw holes" in lowered:
            plan.notes.append(
                f"{screw_size} clearance-hole defaults were applied to the `{selector}` holes at {preset['clearance_mm']:g} mm."
            )

    if screw_defaults_used:
        plan.warnings.append(
            "Metric screw-hole presets use approximate demo-default clearance and head dimensions. Review all screw-hole outputs before fabrication."
        )


def _append_metric_thread_operations(
    plan: FeaturePlan,
    *,
    instruction_text: str,
    geometry_summary: GeometrySummary,
    thickness_mm: float,
    hole_diameter_by_id: dict[str, float],
) -> tuple[set[str], set[str]]:
    assigned_hole_ids: set[str] = set()
    blocked_hole_ids: set[str] = set()
    thread_defaults_used = False

    for clause in _split_instruction_clauses(instruction_text):
        lowered = clause.lower()
        if "hole" not in lowered:
            continue
        if not any(token in lowered for token in ["thread", "threaded", "tapped", "tap drill"]):
            continue

        size_match = METRIC_SCREW_PATTERN.search(clause)
        if not size_match:
            plan.warnings.append(
                "Threaded-hole instructions were detected, but HermesCAD requires an explicit metric screw size such as M4, M5, M6, or M8."
            )
            continue

        screw_size = _normalize_metric_screw_size(size_match.group(1))
        preset = METRIC_SCREW_PRESETS.get(screw_size)
        if preset is None:
            plan.warnings.append(
                f"Metric threaded-hole preset `{screw_size}` is not available. HermesCAD currently supports {', '.join(sorted(METRIC_SCREW_PRESETS))}."
            )
            continue

        selector = _detect_hole_selector(clause)
        target_ids = _dedupe_contour_ids(_select_hole_contour_ids(geometry_summary, selector))
        if not target_ids:
            plan.warnings.append(
                f"The request described `{selector}` threaded-hole targets, but HermesCAD could not resolve matching circular hole contours."
            )
            continue

        requested_depth_mm = _extract_measurement(clause, HOLE_DEPTH_PATTERNS)
        if requested_depth_mm is None or "through" in lowered:
            effective_depth_mm = thickness_mm
            depth_notes: list[str] = []
        else:
            _, effective_depth_mm, depth_notes = _coerce_depth(
                requested_depth_mm=requested_depth_mm,
                base_thickness_mm=thickness_mm,
                target_kind="holes",
            )

        tap_drill_mm = float(preset["tap_drill_mm"])
        valid_target_ids: list[str] = []
        oversized_target_ids: list[str] = []
        for contour_id in target_ids:
            existing_diameter_mm = hole_diameter_by_id.get(contour_id)
            if existing_diameter_mm is None:
                continue
            if existing_diameter_mm > tap_drill_mm + 0.15:
                oversized_target_ids.append(contour_id)
                continue
            valid_target_ids.append(contour_id)

        if oversized_target_ids:
            plan.warnings.append(
                f"The `{selector}` holes are already larger than the {screw_size} tap-drill diameter ({tap_drill_mm:g} mm), so HermesCAD skipped threaded modeling on those hole targets."
            )
        if not valid_target_ids:
            continue

        operation_notes = list(depth_notes)
        operation_notes.append(
            "HermesCAD models internal threads as approximate helical groove cuts around the tap-drill hole, not as manufacturing-certified thread geometry."
        )
        plan.operations.append(
            FeatureOperation(
                operation_id=f"op_{len(plan.operations) + 1:03d}",
                kind="threaded_hole",
                target_kind="holes",
                contour_ids=valid_target_ids,
                depth_mm=effective_depth_mm,
                parameters={
                    "major_diameter_mm": preset["major_diameter_mm"],
                    "tap_drill_mm": tap_drill_mm,
                    "thread_pitch_mm": preset["thread_pitch_mm"],
                    "screw_size": screw_size,
                    "selector": selector,
                },
                notes=operation_notes,
            )
        )
        thread_defaults_used = True
        assigned_hole_ids.update(valid_target_ids)
        blocked_hole_ids.update(valid_target_ids)
        plan.notes.append(
            f"{screw_size} threaded-hole defaults were applied to the `{selector}` holes: {tap_drill_mm:g} mm tap drill with {preset['thread_pitch_mm']:g} mm pitch."
        )

    if thread_defaults_used:
        plan.warnings.append(
            "Modeled threaded holes use approximate helical grooves for demo geometry and still require engineering review before fabrication."
        )

    return assigned_hole_ids, blocked_hole_ids


def _clause_mentions_any(clause: str, keywords: list[str]) -> bool:
    lowered = clause.lower()
    return any(keyword in lowered for keyword in keywords)


def _append_targeted_hole_operations(
    plan: FeaturePlan,
    *,
    instruction_text: str,
    geometry_summary: GeometrySummary,
    thickness_mm: float,
    hole_ids: list[str],
) -> tuple[set[str], set[str]]:
    assigned_hole_ids: set[str] = set()
    blocked_hole_ids: set[str] = set()

    for clause in _split_instruction_clauses(instruction_text):
        lowered = clause.lower()
        if "hole" not in lowered:
            continue
        if any(
            token in lowered
            for token in [
                "socket head",
                "shcs",
                "counterbore",
                "countersink",
                "flat head",
                "thread",
                "threaded",
                "tapped",
                "tap drill",
            ]
        ):
            continue

        selector = _detect_hole_selector(clause)
        hole_depth = _extract_measurement(clause, HOLE_DEPTH_PATTERNS)
        clause_requests_through = "through" in lowered

        if hole_depth is None and not clause_requests_through:
            continue

        target_ids = _dedupe_contour_ids(
            _select_hole_contour_ids(
                geometry_summary,
                selector,
            )
        )
        target_ids = [contour_id for contour_id in target_ids if contour_id not in assigned_hole_ids]

        if hole_depth is not None:
            target_depth_kind, _, _ = _coerce_depth(
                requested_depth_mm=hole_depth,
                base_thickness_mm=thickness_mm,
                target_kind="holes",
            )
            _append_operation(
                plan,
                target_kind="holes",
                contour_ids=target_ids,
                base_thickness_mm=thickness_mm,
                requested_depth_mm=hole_depth,
                parameters={"selector": selector},
            )
            assigned_hole_ids.update(target_ids)
            if target_depth_kind == "blind_hole":
                blocked_hole_ids.update(target_ids)
            continue

        if clause_requests_through:
            _append_operation(
                plan,
                target_kind="holes",
                contour_ids=target_ids,
                base_thickness_mm=thickness_mm,
                requested_depth_mm=thickness_mm,
                parameters={"selector": selector},
            )
            assigned_hole_ids.update(target_ids)

    return assigned_hole_ids, blocked_hole_ids


def _append_targeted_region_operations(
    plan: FeaturePlan,
    *,
    instruction_text: str,
    geometry_summary: GeometrySummary,
    thickness_mm: float,
    slot_contour_ids: list[str],
    cutout_contour_ids: list[str],
    island_contour_ids: list[str],
) -> tuple[set[str], set[str], set[str]]:
    assigned_slot_ids: set[str] = set()
    assigned_cutout_ids: set[str] = set()
    assigned_island_ids: set[str] = set()

    for clause in _split_instruction_clauses(instruction_text):
        selector = _detect_contour_selector(clause)
        slot_depth = _extract_measurement(clause, SLOT_DEPTH_PATTERNS)
        cutout_depth = _extract_measurement(clause, CUTOUT_DEPTH_PATTERNS)
        pocket_depth = _extract_measurement(clause, POCKET_DEPTH_PATTERNS)
        boss_height = _extract_measurement(clause, BOSS_HEIGHT_PATTERNS)
        clause_requests_through = "through" in clause.lower()

        if slot_depth is not None and _clause_mentions_any(clause, ["slot"]):
            target_ids = _dedupe_contour_ids(
                _select_contour_ids(
                    geometry_summary,
                    [contour_id for contour_id in slot_contour_ids if contour_id not in assigned_slot_ids],
                    selector,
                )
            )
            _append_operation(
                plan,
                target_kind="slots",
                contour_ids=target_ids,
                base_thickness_mm=thickness_mm,
                requested_depth_mm=slot_depth,
                parameters={"selector": selector},
            )
            assigned_slot_ids.update(target_ids)

        if clause_requests_through and _clause_mentions_any(clause, ["slot"]):
            target_ids = _dedupe_contour_ids(
                _select_contour_ids(
                    geometry_summary,
                    [contour_id for contour_id in slot_contour_ids if contour_id not in assigned_slot_ids],
                    selector,
                )
            )
            _append_operation(
                plan,
                target_kind="slots",
                contour_ids=target_ids,
                base_thickness_mm=thickness_mm,
                requested_depth_mm=thickness_mm,
                parameters={"selector": selector},
            )
            assigned_slot_ids.update(target_ids)

        cutout_target_depth = cutout_depth if cutout_depth is not None else pocket_depth
        if cutout_target_depth is not None and _clause_mentions_any(clause, ["window", "cutout", "pocket"]):
            target_ids = _dedupe_contour_ids(
                _select_contour_ids(
                    geometry_summary,
                    [contour_id for contour_id in cutout_contour_ids if contour_id not in assigned_cutout_ids],
                    selector,
                )
            )
            _append_operation(
                plan,
                target_kind="cutouts",
                contour_ids=target_ids,
                base_thickness_mm=thickness_mm,
                requested_depth_mm=cutout_target_depth,
                parameters={"selector": selector},
            )
            assigned_cutout_ids.update(target_ids)

        if clause_requests_through and _clause_mentions_any(clause, ["window", "cutout", "pocket"]):
            target_ids = _dedupe_contour_ids(
                _select_contour_ids(
                    geometry_summary,
                    [contour_id for contour_id in cutout_contour_ids if contour_id not in assigned_cutout_ids],
                    selector,
                )
            )
            _append_operation(
                plan,
                target_kind="cutouts",
                contour_ids=target_ids,
                base_thickness_mm=thickness_mm,
                requested_depth_mm=thickness_mm,
                parameters={"selector": selector},
            )
            assigned_cutout_ids.update(target_ids)

        if boss_height is not None and _clause_mentions_any(clause, ["island", "boss", "pad"]):
            target_ids = _dedupe_contour_ids(
                _select_contour_ids(
                    geometry_summary,
                    [contour_id for contour_id in island_contour_ids if contour_id not in assigned_island_ids],
                    selector,
                )
            )
            _append_operation(
                plan,
                target_kind="islands",
                contour_ids=target_ids,
                base_thickness_mm=thickness_mm,
                requested_depth_mm=boss_height,
                kind_override="boss_add",
                parameters={"selector": selector},
            )
            assigned_island_ids.update(target_ids)

    return assigned_slot_ids, assigned_cutout_ids, assigned_island_ids


def write_feature_plan(path: Path, plan: FeaturePlan) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    plan.feature_plan_path = str(path)
    path.write_text(json.dumps(plan.model_dump(mode="json"), indent=2), encoding="utf-8")
    return path


def build_feature_plan(
    instruction_text: str,
    geometry_summary: GeometrySummary,
    *,
    thickness_mm: float,
    chamfer_mm: float | None = None,
) -> FeaturePlan:
    plan = FeaturePlan(
        base_thickness_mm=thickness_mm,
        chamfer_mm=chamfer_mm,
    )

    cutout_ids = list(geometry_summary.cutout_ids)
    slot_contour_ids = [
        contour_id
        for contour_id in geometry_summary.slot_candidate_ids
        if contour_id not in geometry_summary.outer_profile_ids
    ]
    non_slot_cutout_ids = [contour_id for contour_id in cutout_ids if contour_id not in slot_contour_ids]
    hole_ids = list(geometry_summary.hole_contour_ids)
    island_ids = list(geometry_summary.island_ids)
    hole_diameter_by_id = {hole.contour_id: hole.diameter for hole in geometry_summary.hole_candidates if hole.contour_id}

    hole_depth_override = _extract_measurement(instruction_text, HOLE_DEPTH_PATTERNS)
    slot_depth_override = _extract_measurement(instruction_text, SLOT_DEPTH_PATTERNS)
    cutout_depth_override = _extract_measurement(instruction_text, CUTOUT_DEPTH_PATTERNS)
    generic_pocket_depth = _extract_measurement(instruction_text, POCKET_DEPTH_PATTERNS)
    counterbore_diameter_mm = _extract_measurement(instruction_text, COUNTERBORE_DIAMETER_PATTERNS)
    counterbore_depth_mm = _extract_measurement(instruction_text, COUNTERBORE_DEPTH_PATTERNS)
    countersink_diameter_mm = _extract_measurement(instruction_text, COUNTERSINK_DIAMETER_PATTERNS)
    countersink_angle_deg = _extract_measurement(instruction_text, COUNTERSINK_ANGLE_PATTERNS)

    hole_depth_mm = hole_depth_override if hole_depth_override is not None else thickness_mm
    slot_depth_mm = slot_depth_override
    cutout_depth_mm = cutout_depth_override

    if generic_pocket_depth is not None:
        if slot_depth_mm is None and slot_contour_ids:
            slot_depth_mm = generic_pocket_depth
        if cutout_depth_mm is None and non_slot_cutout_ids:
            cutout_depth_mm = generic_pocket_depth

    threaded_hole_ids, threaded_blocked_hole_ids = _append_metric_thread_operations(
        plan,
        instruction_text=instruction_text,
        geometry_summary=geometry_summary,
        thickness_mm=thickness_mm,
        hole_diameter_by_id=hole_diameter_by_id,
    )
    assigned_hole_ids, blocked_hole_ids = _append_targeted_hole_operations(
        plan,
        instruction_text=instruction_text,
        geometry_summary=geometry_summary,
        thickness_mm=thickness_mm,
        hole_ids=hole_ids,
    )
    assigned_hole_ids.update(threaded_hole_ids)
    blocked_hole_ids.update(threaded_blocked_hole_ids)

    remaining_hole_ids = [contour_id for contour_id in hole_ids if contour_id not in assigned_hole_ids]
    if remaining_hole_ids:
        remaining_hole_depth_mm = thickness_mm if assigned_hole_ids else hole_depth_mm
        _append_operation(
            plan,
            target_kind="holes",
            contour_ids=remaining_hole_ids,
            base_thickness_mm=thickness_mm,
            requested_depth_mm=remaining_hole_depth_mm,
        )

    _append_metric_screw_operations(
        plan,
        instruction_text=instruction_text,
        geometry_summary=geometry_summary,
        thickness_mm=thickness_mm,
        hole_ids=hole_ids,
        hole_diameter_by_id=hole_diameter_by_id,
        blocked_hole_ids=blocked_hole_ids | threaded_blocked_hole_ids,
    )

    assigned_slot_ids, assigned_cutout_ids, assigned_island_ids = _append_targeted_region_operations(
        plan,
        instruction_text=instruction_text,
        geometry_summary=geometry_summary,
        thickness_mm=thickness_mm,
        slot_contour_ids=slot_contour_ids,
        cutout_contour_ids=non_slot_cutout_ids,
        island_contour_ids=island_ids,
    )

    if counterbore_diameter_mm is not None or counterbore_depth_mm is not None:
        if counterbore_diameter_mm is None or counterbore_depth_mm is None:
            plan.warnings.append(
                "Counterbore instructions were detected, but both counterbore diameter and depth are required for HermesCAD to model them safely."
            )
        else:
            _append_operation(
                plan,
                target_kind="holes",
                contour_ids=hole_ids,
                base_thickness_mm=thickness_mm,
                requested_depth_mm=counterbore_depth_mm,
                kind_override="counterbore_hole",
                parameters={"major_diameter_mm": counterbore_diameter_mm},
            )

    if countersink_diameter_mm is not None or countersink_angle_deg is not None:
        if countersink_diameter_mm is None or countersink_angle_deg is None:
            plan.warnings.append(
                "Countersink instructions were detected, but both countersink major diameter and included angle are required for HermesCAD to model them safely."
            )
        else:
            if not hole_ids:
                plan.warnings.append(
                    "Countersink instructions were detected, but no circular hole contours were available to countersink."
                )
            else:
                pilot_diameters = [hole_diameter_by_id[contour_id] for contour_id in hole_ids if contour_id in hole_diameter_by_id]
                if not pilot_diameters:
                    plan.warnings.append(
                        "Countersink instructions were detected, but HermesCAD could not resolve the pilot hole diameters from the inspected geometry."
                    )
                else:
                    pilot_radius_mm = min(pilot_diameters) / 2.0
                    major_radius_mm = countersink_diameter_mm / 2.0
                    if major_radius_mm <= pilot_radius_mm:
                        plan.warnings.append(
                            "Countersink major diameter was not larger than the detected pilot holes, so the countersink operation was skipped."
                        )
                    else:
                        half_angle_rad = math.radians(countersink_angle_deg / 2.0)
                        if half_angle_rad <= 0 or math.isclose(math.tan(half_angle_rad), 0.0, abs_tol=1e-9):
                            plan.warnings.append(
                                "Countersink angle was invalid, so the countersink operation was skipped."
                            )
                        else:
                            countersink_depth_mm = (major_radius_mm - pilot_radius_mm) / math.tan(half_angle_rad)
                            if countersink_depth_mm > thickness_mm:
                                plan.warnings.append(
                                    "Requested countersink would exceed the base thickness, so the countersink operation was skipped."
                                )
                            else:
                                _append_operation(
                                    plan,
                                    target_kind="holes",
                                    contour_ids=hole_ids,
                                    base_thickness_mm=thickness_mm,
                                    requested_depth_mm=countersink_depth_mm,
                                    kind_override="countersink_hole",
                                    parameters={
                                        "major_diameter_mm": countersink_diameter_mm,
                                        "included_angle_deg": countersink_angle_deg,
                                    },
                                )

    remaining_slot_ids = [contour_id for contour_id in slot_contour_ids if contour_id not in assigned_slot_ids]
    if remaining_slot_ids:
        _append_operation(
            plan,
            target_kind="slots",
            contour_ids=remaining_slot_ids,
            base_thickness_mm=thickness_mm,
            requested_depth_mm=slot_depth_mm if slot_depth_mm is not None else thickness_mm,
        )

    remaining_cutout_ids = [contour_id for contour_id in non_slot_cutout_ids if contour_id not in assigned_cutout_ids]
    if remaining_cutout_ids:
        _append_operation(
            plan,
            target_kind="cutouts",
            contour_ids=remaining_cutout_ids,
            base_thickness_mm=thickness_mm,
            requested_depth_mm=cutout_depth_mm if cutout_depth_mm is not None else thickness_mm,
        )

    if generic_pocket_depth is not None and not cutout_ids and not slot_contour_ids:
        plan.warnings.append(
            "The request described a pocket depth, but the inspected geometry did not include non-outer cutout contours that could be pocketed safely."
        )

    if _extract_measurement(instruction_text, BOSS_HEIGHT_PATTERNS) is not None and not island_ids:
        plan.warnings.append(
            "Boss or island-height instructions were detected, but the inspected geometry did not include preserved island contours that could be raised safely."
        )

    if geometry_summary.open_chain_count > 0:
        plan.warnings.append(
            "Open chains were detected in the DXF. HermesCAD only used closed contours for the feature plan."
        )

    plan.notes.append(
        "The feature plan starts from top-level outer profiles as the base solid, then applies ordered cut operations to nested contours."
    )
    if counterbore_diameter_mm is not None and counterbore_depth_mm is not None:
        plan.notes.append(
            f"Counterbore operations will enlarge targeted holes to {counterbore_diameter_mm:g} mm diameter for {counterbore_depth_mm:g} mm from the top face."
        )
    if countersink_diameter_mm is not None and countersink_angle_deg is not None:
        plan.notes.append(
            f"Countersink operations will use a {countersink_diameter_mm:g} mm major diameter at {countersink_angle_deg:g} degrees on the top face."
        )
    if assigned_island_ids:
        plan.notes.append(
            "Boss operations will add material on top of the existing base thickness using preserved island contours from the inspected geometry."
        )
    return plan
