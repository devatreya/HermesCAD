from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import ezdxf
from ezdxf import edgeminer as em

from .models import (
    BoundingBox,
    ContourSummary,
    GeometrySegment,
    GeometrySummary,
    HoleCandidate,
    OpenChainSummary,
    Point2D,
)

INSUNITS_MAP = {
    0: None,
    1: "Inches",
    2: "Feet",
    4: "Millimeters",
    5: "Centimeters",
    6: "Meters",
}

DEFAULT_FLATTEN_TOLERANCE = 0.25
DEFAULT_GAP_TOLERANCE = 1e-6
LOOP_TIMEOUT_SECONDS = 10.0
ARC_SAMPLE_DEGREES = 12.0
CIRCLE_SAMPLE_COUNT = 48
ANNOTATION_ENTITY_TYPES = {
    "TEXT",
    "MTEXT",
    "DIMENSION",
    "MULTILEADER",
    "LEADER",
    "TOLERANCE",
    "HATCH",
    "INSERT",
}


@dataclass(frozen=True)
class _PrimitivePayload:
    kind: str
    source_entity_type: str
    start: tuple[float, float]
    end: tuple[float, float]
    approximated: bool = False
    center: tuple[float, float] | None = None
    radius: float | None = None
    start_angle_deg: float | None = None
    end_angle_deg: float | None = None
    sweep_angle_deg: float | None = None


def _angle_normalize(angle_deg: float) -> float:
    return angle_deg % 360.0


def _ccw_sweep(start_angle_deg: float, end_angle_deg: float) -> float:
    return (end_angle_deg - start_angle_deg) % 360.0


def _point_tuple(x_value: float, y_value: float) -> tuple[float, float]:
    return (float(x_value), float(y_value))


def _point_model(x_value: float, y_value: float) -> Point2D:
    return Point2D(x=float(x_value), y=float(y_value))


def _point_from_tuple(point: tuple[float, float]) -> Point2D:
    return _point_model(point[0], point[1])


def _points_close(point_a: tuple[float, float], point_b: tuple[float, float], tolerance: float = DEFAULT_GAP_TOLERANCE) -> bool:
    return math.isclose(point_a[0], point_b[0], abs_tol=tolerance) and math.isclose(
        point_a[1], point_b[1], abs_tol=tolerance
    )


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


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


def _bbox_from_points(points: list[Point2D]) -> BoundingBox:
    if not points:
        return BoundingBox()
    bounds = {
        "min_x": float("inf"),
        "min_y": float("inf"),
        "max_x": float("-inf"),
        "max_y": float("-inf"),
    }
    _update_bounds(bounds, [(point.x, point.y) for point in points])
    return _bbox_from_bounds(bounds)


def _segment_length(segment: GeometrySegment) -> float:
    if segment.kind == "line":
        return math.hypot(segment.end.x - segment.start.x, segment.end.y - segment.start.y)
    if segment.kind == "arc" and segment.radius is not None and segment.sweep_angle_deg is not None:
        return abs(math.radians(segment.sweep_angle_deg) * segment.radius)
    if segment.kind == "circle" and segment.radius is not None:
        return 2.0 * math.pi * segment.radius
    return 0.0


def _shoelace_area(points: list[Point2D]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for index in range(len(points) - 1):
        current = points[index]
        following = points[index + 1]
        total += current.x * following.y - following.x * current.y
    return total / 2.0


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
    if math.isclose(dx, 0.0, abs_tol=DEFAULT_GAP_TOLERANCE) and math.isclose(
        dy, 0.0, abs_tol=DEFAULT_GAP_TOLERANCE
    ):
        return math.hypot(px - x1, py - y1)
    projection = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    projection = max(0.0, min(1.0, projection))
    closest_x = x1 + projection * dx
    closest_y = y1 + projection * dy
    return math.hypot(px - closest_x, py - closest_y)


def _point_on_polygon_boundary(point: tuple[float, float], polygon: list[Point2D], tolerance: float = 1e-5) -> bool:
    if len(polygon) < 2:
        return False
    for index in range(len(polygon) - 1):
        start = (polygon[index].x, polygon[index].y)
        end = (polygon[index + 1].x, polygon[index + 1].y)
        if _distance_point_to_segment(point, start, end) <= tolerance:
            return True
    return False


def _point_in_polygon(point: tuple[float, float], polygon: list[Point2D]) -> bool:
    if len(polygon) < 4:
        return False
    if _point_on_polygon_boundary(point, polygon):
        return True

    x_value, y_value = point
    inside = False
    for index in range(len(polygon) - 1):
        point_a = polygon[index]
        point_b = polygon[index + 1]
        if ((point_a.y > y_value) != (point_b.y > y_value)) and (
            x_value
            < (point_b.x - point_a.x) * (y_value - point_a.y) / (point_b.y - point_a.y) + point_a.x
        ):
            inside = not inside
    return inside


def _find_polygon_interior_point(points: list[Point2D]) -> tuple[float, float] | None:
    if len(points) < 4:
        return None

    bbox = _bbox_from_points(points)
    candidate_y_values = []
    if bbox.min_y is not None and bbox.max_y is not None:
        candidate_y_values.append((bbox.min_y + bbox.max_y) / 2.0)

    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        if not math.isclose(start.y, end.y, abs_tol=DEFAULT_GAP_TOLERANCE):
            candidate_y_values.append((start.y + end.y) / 2.0)

    for y_value in candidate_y_values:
        intersections: list[float] = []
        for index in range(len(points) - 1):
            start = points[index]
            end = points[index + 1]
            if math.isclose(start.y, end.y, abs_tol=DEFAULT_GAP_TOLERANCE):
                continue
            min_y = min(start.y, end.y)
            max_y = max(start.y, end.y)
            if y_value < min_y or y_value >= max_y:
                continue
            x_value = start.x + (y_value - start.y) * (end.x - start.x) / (end.y - start.y)
            intersections.append(x_value)

        intersections.sort()
        for index in range(0, len(intersections) - 1, 2):
            left = intersections[index]
            right = intersections[index + 1]
            if right - left > DEFAULT_GAP_TOLERANCE:
                midpoint = (left + right) / 2.0
                candidate = (midpoint, y_value)
                if _point_in_polygon(candidate, points):
                    return candidate

    if bbox.min_x is not None and bbox.max_x is not None and bbox.min_y is not None and bbox.max_y is not None:
        midpoint = ((bbox.min_x + bbox.max_x) / 2.0, (bbox.min_y + bbox.max_y) / 2.0)
        if _point_in_polygon(midpoint, points):
            return midpoint
    return None


def _sample_arc_points(
    center: tuple[float, float],
    radius: float,
    start_angle_deg: float,
    sweep_angle_deg: float,
    include_start: bool = True,
) -> list[Point2D]:
    sweep = float(sweep_angle_deg)
    sample_count = max(2, int(math.ceil(abs(sweep) / ARC_SAMPLE_DEGREES)) + 1)
    points: list[Point2D] = []
    start_index = 0 if include_start else 1
    for step in range(start_index, sample_count):
        fraction = step / (sample_count - 1)
        angle_deg = start_angle_deg + sweep * fraction
        angle_rad = math.radians(angle_deg)
        x_value = center[0] + radius * math.cos(angle_rad)
        y_value = center[1] + radius * math.sin(angle_rad)
        points.append(_point_model(x_value, y_value))
    return points


def _sample_circle_points(center: tuple[float, float], radius: float) -> list[Point2D]:
    points: list[Point2D] = []
    for step in range(CIRCLE_SAMPLE_COUNT):
        angle_rad = 2.0 * math.pi * (step / CIRCLE_SAMPLE_COUNT)
        x_value = center[0] + radius * math.cos(angle_rad)
        y_value = center[1] + radius * math.sin(angle_rad)
        points.append(_point_model(x_value, y_value))
    if points:
        points.append(points[0])
    return points


def _payload_to_segment(payload: _PrimitivePayload, reverse: bool = False) -> GeometrySegment:
    if payload.kind == "line":
        start = payload.end if reverse else payload.start
        end = payload.start if reverse else payload.end
        return GeometrySegment(
            kind="line",
            start=_point_from_tuple(start),
            end=_point_from_tuple(end),
            source_entity_type=payload.source_entity_type,
            approximated=payload.approximated,
        )

    if payload.kind == "arc":
        if payload.center is None or payload.radius is None or payload.sweep_angle_deg is None:
            raise RuntimeError("Arc payload was missing center, radius, or sweep metadata.")
        if reverse:
            start = payload.end
            end = payload.start
            start_angle_deg = payload.end_angle_deg if payload.end_angle_deg is not None else 0.0
            end_angle_deg = payload.start_angle_deg if payload.start_angle_deg is not None else 0.0
            sweep_angle_deg = -float(payload.sweep_angle_deg)
        else:
            start = payload.start
            end = payload.end
            start_angle_deg = payload.start_angle_deg if payload.start_angle_deg is not None else 0.0
            end_angle_deg = payload.end_angle_deg if payload.end_angle_deg is not None else 0.0
            sweep_angle_deg = float(payload.sweep_angle_deg)
        return GeometrySegment(
            kind="arc",
            start=_point_from_tuple(start),
            end=_point_from_tuple(end),
            source_entity_type=payload.source_entity_type,
            approximated=payload.approximated,
            center=_point_from_tuple(payload.center),
            radius=float(payload.radius),
            start_angle_deg=float(start_angle_deg),
            end_angle_deg=float(end_angle_deg),
            sweep_angle_deg=float(sweep_angle_deg),
        )

    if payload.kind == "circle":
        if payload.center is None or payload.radius is None:
            raise RuntimeError("Circle payload was missing center or radius metadata.")
        return GeometrySegment(
            kind="circle",
            start=_point_from_tuple(payload.start),
            end=_point_from_tuple(payload.end),
            source_entity_type=payload.source_entity_type,
            approximated=payload.approximated,
            center=_point_from_tuple(payload.center),
            radius=float(payload.radius),
            start_angle_deg=0.0,
            end_angle_deg=360.0,
            sweep_angle_deg=360.0,
        )

    raise RuntimeError(f"Unsupported primitive payload kind: {payload.kind}")


def _segment_to_sampled_points(segment: GeometrySegment, include_start: bool) -> list[Point2D]:
    if segment.kind == "line":
        points = [segment.start, segment.end]
        return points if include_start else points[1:]
    if segment.kind == "arc":
        if segment.center is None or segment.radius is None or segment.start_angle_deg is None or segment.sweep_angle_deg is None:
            return [segment.start, segment.end] if include_start else [segment.end]
        return _sample_arc_points(
            center=(segment.center.x, segment.center.y),
            radius=float(segment.radius),
            start_angle_deg=float(segment.start_angle_deg),
            sweep_angle_deg=float(segment.sweep_angle_deg),
            include_start=include_start,
        )
    if segment.kind == "circle":
        if segment.center is None or segment.radius is None:
            return []
        points = _sample_circle_points((segment.center.x, segment.center.y), float(segment.radius))
        return points if include_start else points[1:]
    return []


def _make_line_edge(
    start: tuple[float, float],
    end: tuple[float, float],
    source_entity_type: str,
    approximated: bool = False,
) -> em.Edge | None:
    if _points_close(start, end):
        return None
    payload = _PrimitivePayload(
        kind="line",
        source_entity_type=source_entity_type,
        start=start,
        end=end,
        approximated=approximated,
    )
    return em.make_edge(start, end, payload=payload)


def _make_arc_edge(
    center: tuple[float, float],
    radius: float,
    start_angle_deg: float,
    end_angle_deg: float,
    source_entity_type: str,
    approximated: bool = False,
) -> em.Edge | None:
    radius = float(radius)
    if radius <= 0:
        return None

    start_angle_deg = _angle_normalize(float(start_angle_deg))
    end_angle_deg = _angle_normalize(float(end_angle_deg))
    sweep_angle_deg = _ccw_sweep(start_angle_deg, end_angle_deg)
    if math.isclose(sweep_angle_deg, 0.0, abs_tol=DEFAULT_GAP_TOLERANCE):
        sweep_angle_deg = 360.0

    start_rad = math.radians(start_angle_deg)
    end_rad = math.radians(start_angle_deg + sweep_angle_deg)
    start = _point_tuple(center[0] + radius * math.cos(start_rad), center[1] + radius * math.sin(start_rad))
    end = _point_tuple(center[0] + radius * math.cos(end_rad), center[1] + radius * math.sin(end_rad))

    payload = _PrimitivePayload(
        kind="arc",
        source_entity_type=source_entity_type,
        start=start,
        end=end,
        approximated=approximated,
        center=center,
        radius=radius,
        start_angle_deg=start_angle_deg,
        end_angle_deg=end_angle_deg,
        sweep_angle_deg=sweep_angle_deg,
    )
    return em.make_edge(start, end, length=abs(math.radians(sweep_angle_deg) * radius), payload=payload)


def _circle_contour(
    center: tuple[float, float],
    radius: float,
    contour_id: str,
    source_entity_type: str,
) -> ContourSummary:
    start = _point_tuple(center[0] + radius, center[1])
    segment = _payload_to_segment(
        _PrimitivePayload(
            kind="circle",
            source_entity_type=source_entity_type,
            start=start,
            end=start,
            center=center,
            radius=radius,
        )
    )
    sampled_points = _sample_circle_points(center, radius)
    area = math.pi * radius * radius
    perimeter = 2.0 * math.pi * radius
    return ContourSummary(
        contour_id=contour_id,
        source="circle",
        closed=True,
        source_entity_types=[source_entity_type],
        segment_types=["circle"],
        segments=[segment],
        sampled_points=sampled_points,
        bounding_box=_bbox_from_points(sampled_points),
        area=area,
        perimeter=perimeter,
        orientation="Counterclockwise",
        is_circle=True,
    )


def _contour_from_edges(edges: list[em.Edge], contour_id: str) -> ContourSummary:
    segments: list[GeometrySegment] = []
    sampled_points: list[Point2D] = []
    source_entity_types: list[str] = []
    segment_types: list[str] = []
    for edge in edges:
        payload = edge.payload
        if not isinstance(payload, _PrimitivePayload):
            raise RuntimeError("Encountered an edge without HermesCAD primitive metadata.")
        segment = _payload_to_segment(payload, reverse=edge.is_reverse)
        segments.append(segment)
        source_entity_types.append(segment.source_entity_type)
        segment_types.append(segment.kind)
        sampled_points.extend(_segment_to_sampled_points(segment, include_start=not sampled_points))

    if sampled_points and not _points_close(
        (sampled_points[0].x, sampled_points[0].y),
        (sampled_points[-1].x, sampled_points[-1].y),
    ):
        sampled_points.append(sampled_points[0])

    signed_area = _shoelace_area(sampled_points)
    orientation = "Counterclockwise" if signed_area > 0 else "Clockwise"
    if math.isclose(signed_area, 0.0, abs_tol=DEFAULT_GAP_TOLERANCE):
        orientation = "Degenerate"

    return ContourSummary(
        contour_id=contour_id,
        source="edge_loop",
        closed=True,
        source_entity_types=sorted(set(source_entity_types)),
        segment_types=segment_types,
        segments=segments,
        sampled_points=sampled_points,
        bounding_box=_bbox_from_points(sampled_points),
        area=abs(signed_area),
        perimeter=sum(_segment_length(segment) for segment in segments),
        orientation=orientation,
    )


def _open_chain_from_edges(edges: list[em.Edge], chain_id: str) -> OpenChainSummary:
    segments: list[GeometrySegment] = []
    sampled_points: list[Point2D] = []
    source_entity_types: list[str] = []
    segment_types: list[str] = []
    for edge in edges:
        payload = edge.payload
        if not isinstance(payload, _PrimitivePayload):
            continue
        segment = _payload_to_segment(payload, reverse=edge.is_reverse)
        segments.append(segment)
        source_entity_types.append(segment.source_entity_type)
        segment_types.append(segment.kind)
        sampled_points.extend(_segment_to_sampled_points(segment, include_start=not sampled_points))

    return OpenChainSummary(
        chain_id=chain_id,
        source_entity_types=sorted(set(source_entity_types)),
        segment_types=segment_types,
        segments=segments,
        sampled_points=sampled_points,
        bounding_box=_bbox_from_points(sampled_points),
        approximate_length=sum(_segment_length(segment) for segment in segments),
        start_point=sampled_points[0] if sampled_points else None,
        end_point=sampled_points[-1] if sampled_points else None,
    )


def _is_slot_candidate(contour: ContourSummary) -> bool:
    if contour.is_circle or contour.area <= 0.0:
        return False
    arc_segments = [
        segment
        for segment in contour.segments
        if segment.kind == "arc"
        and segment.radius is not None
        and segment.sweep_angle_deg is not None
        and 120.0 <= abs(segment.sweep_angle_deg) <= 240.0
    ]
    line_segments = [segment for segment in contour.segments if segment.kind == "line"]
    bbox = contour.bounding_box
    width = float(bbox.width or 0.0)
    height = float(bbox.height or 0.0)
    aspect_ratio = max(width, height) / max(min(width, height), DEFAULT_GAP_TOLERANCE)
    if len(arc_segments) == 2 and len(line_segments) >= 2 and aspect_ratio >= 1.5:
        radii = [float(segment.radius) for segment in arc_segments if segment.radius is not None]
        if radii and max(radii) - min(radii) <= max(radii) * 0.05:
            return True
    return False


def _bbox_area(bbox: BoundingBox) -> float:
    return max(float(bbox.width or 0.0), 0.0) * max(float(bbox.height or 0.0), 0.0)


def _is_axis_aligned_rectangle_contour(contour: ContourSummary) -> bool:
    if contour.is_circle or len(contour.segments) != 4:
        return False
    if any(segment.kind != "line" for segment in contour.segments):
        return False
    for segment in contour.segments:
        dx = abs(segment.end.x - segment.start.x)
        dy = abs(segment.end.y - segment.start.y)
        if dx > DEFAULT_GAP_TOLERANCE and dy > DEFAULT_GAP_TOLERANCE:
            return False
    bbox = contour.bounding_box
    if float(bbox.width or 0.0) <= DEFAULT_GAP_TOLERANCE or float(bbox.height or 0.0) <= DEFAULT_GAP_TOLERANCE:
        return False
    return True


def _is_degenerate_contour(contour: ContourSummary) -> bool:
    if contour.is_circle:
        return False
    bbox = contour.bounding_box
    width = float(bbox.width or 0.0)
    height = float(bbox.height or 0.0)
    return abs(contour.area) <= DEFAULT_GAP_TOLERANCE or width <= DEFAULT_GAP_TOLERANCE or height <= DEFAULT_GAP_TOLERANCE


def _drawing_has_annotations(entity_counts: dict[str, int], open_chain_count: int) -> bool:
    return open_chain_count >= 8 or any(entity_counts.get(entity_type, 0) > 0 for entity_type in ANNOTATION_ENTITY_TYPES)


def _detect_drawing_frame_contours(
    contours: list[ContourSummary],
    overall_bbox: BoundingBox,
    entity_counts: dict[str, int],
    open_chain_count: int,
) -> set[str]:
    if not contours or not _drawing_has_annotations(entity_counts, open_chain_count):
        return set()

    overall_area = _bbox_area(overall_bbox)
    if overall_area <= DEFAULT_GAP_TOLERANCE:
        return set()

    ignored_ids: set[str] = set()
    for contour in contours:
        if contour.role != "outer_profile":
            continue
        if not _is_axis_aligned_rectangle_contour(contour):
            continue
        contour_bbox_area = _bbox_area(contour.bounding_box)
        if contour_bbox_area < overall_area * 0.98:
            continue
        largest_other_area = max(
            (abs(other.area) for other in contours if other.contour_id != contour.contour_id),
            default=0.0,
        )
        if abs(contour.area) < max(largest_other_area * 4.0, 1000.0):
            continue
        significant_children = [
            child
            for child in contours
            if child.parent_contour_id == contour.contour_id and abs(child.area) > max(abs(contour.area) * 0.005, 10.0)
        ]
        if not significant_children:
            continue
        ignored_ids.add(contour.contour_id)
    return ignored_ids


def _is_likely_annotation_loop(contour: ContourSummary) -> bool:
    if contour.is_circle:
        return False
    source_types = set(contour.source_entity_types)
    if not source_types or not source_types.issubset({"LINE", "LWPOLYLINE", "POLYLINE"}):
        return False
    bbox = contour.bounding_box
    width = float(bbox.width or 0.0)
    height = float(bbox.height or 0.0)
    min_dim = min(width, height)
    max_dim = max(width, height)
    aspect_ratio = max_dim / max(min_dim, DEFAULT_GAP_TOLERANCE)
    if min_dim <= 1.0 and max_dim >= 10.0:
        return True
    if abs(contour.area) <= 25.0:
        return True
    if aspect_ratio >= 40.0 and min_dim <= 2.0:
        return True
    return False


def _exclude_annotation_loops(
    contours: list[ContourSummary],
    entity_counts: dict[str, int],
    open_chain_count: int,
) -> list[str]:
    if not _drawing_has_annotations(entity_counts, open_chain_count):
        return []

    excluded_ids: list[str] = []
    for contour in contours:
        if contour.role not in {"outer_profile", "cutout", "island"}:
            continue
        if not _is_likely_annotation_loop(contour):
            continue
        contour.parent_contour_id = None
        contour.child_contour_ids.clear()
        contour.nesting_depth = 0
        contour.role = "annotation_loop"
        contour.is_hole_candidate = False
        contour.is_slot_candidate = False
        note = "Detected as likely annotation geometry and excluded from part reconstruction."
        if note not in contour.notes:
            contour.notes.append(note)
        excluded_ids.append(contour.contour_id)
    return excluded_ids


def _classify_contours(contours: list[ContourSummary], ignored_ids: set[str] | None = None) -> None:
    if not contours:
        return

    ignored_ids = ignored_ids or set()

    contours_by_id = {contour.contour_id: contour for contour in contours}
    representative_points: dict[str, tuple[float, float]] = {}

    for contour in contours:
        contour.parent_contour_id = None
        contour.child_contour_ids.clear()
        contour.nesting_depth = 0
        contour.is_hole_candidate = False
        contour.is_slot_candidate = False
        if contour.contour_id in ignored_ids:
            contour.role = "drawing_frame"
            note = "Detected as likely drawing frame geometry and excluded from part reconstruction."
            if note not in contour.notes:
                contour.notes.append(note)
            continue
        if contour.is_circle and contour.segments and contour.segments[0].center is not None:
            center = contour.segments[0].center
            representative_points[contour.contour_id] = (center.x, center.y)
            continue
        interior_point = _find_polygon_interior_point(contour.sampled_points)
        if interior_point is not None:
            representative_points[contour.contour_id] = interior_point

    for contour in contours:
        if contour.contour_id in ignored_ids:
            continue
        parent: ContourSummary | None = None
        candidate_point = representative_points.get(contour.contour_id)
        if candidate_point is None:
            contour.notes.append("Could not compute a stable interior point for nesting classification.")
            continue
        for container in contours:
            if container.contour_id == contour.contour_id:
                continue
            if container.contour_id in ignored_ids:
                continue
            if container.area <= contour.area + DEFAULT_GAP_TOLERANCE:
                continue
            if _point_in_polygon(candidate_point, container.sampled_points):
                if parent is None or container.area < parent.area:
                    parent = container
        if parent is not None:
            contour.parent_contour_id = parent.contour_id

    for contour in contours:
        if contour.contour_id in ignored_ids:
            continue
        if contour.parent_contour_id:
            parent = contours_by_id[contour.parent_contour_id]
            parent.child_contour_ids.append(contour.contour_id)

    def assign_depth(contour: ContourSummary) -> int:
        if contour.parent_contour_id is None:
            contour.nesting_depth = 0
            return 0
        parent = contours_by_id[contour.parent_contour_id]
        contour.nesting_depth = assign_depth(parent) + 1
        return contour.nesting_depth

    for contour in contours:
        if contour.contour_id in ignored_ids:
            continue
        assign_depth(contour)

    for contour in contours:
        if contour.contour_id in ignored_ids:
            continue
        contour.child_contour_ids = sorted(contour.child_contour_ids)
        if _is_degenerate_contour(contour):
            contour.role = "degenerate"
            contour.is_hole_candidate = False
            contour.is_slot_candidate = False
            note = "Contour was closed but degenerate and excluded from part reconstruction."
            if note not in contour.notes:
                contour.notes.append(note)
            continue
        if contour.nesting_depth % 2 == 0:
            contour.role = "outer_profile" if contour.nesting_depth == 0 else "island"
        else:
            contour.role = "hole" if contour.is_circle else "cutout"
        contour.is_hole_candidate = contour.role == "hole"
        contour.is_slot_candidate = _is_slot_candidate(contour)


def _ingest_entity_geometry(
    entity,
    edge_primitives: list[em.Edge],
    contour_primitives: list[ContourSummary],
    bounds: dict[str, float],
    notes: list[str],
    source_entity_type: str | None = None,
) -> None:
    entity_type = entity.dxftype()
    source_type = source_entity_type or entity_type

    if entity_type == "LINE":
        start = _point_tuple(entity.dxf.start.x, entity.dxf.start.y)
        end = _point_tuple(entity.dxf.end.x, entity.dxf.end.y)
        edge = _make_line_edge(start, end, source_type)
        if edge is not None:
            edge_primitives.append(edge)
            _update_bounds(bounds, [start, end])
        return

    if entity_type == "ARC":
        center = _point_tuple(entity.dxf.center.x, entity.dxf.center.y)
        edge = _make_arc_edge(
            center=center,
            radius=float(entity.dxf.radius),
            start_angle_deg=float(entity.dxf.start_angle),
            end_angle_deg=float(entity.dxf.end_angle),
            source_entity_type=source_type,
        )
        if edge is not None:
            edge_primitives.append(edge)
            payload = edge.payload
            if isinstance(payload, _PrimitivePayload):
                _update_bounds(
                    bounds,
                    [(point.x, point.y) for point in _sample_arc_points(center, payload.radius or 0.0, payload.start_angle_deg or 0.0, payload.sweep_angle_deg or 0.0)],
                )
        return

    if entity_type == "CIRCLE":
        center = _point_tuple(entity.dxf.center.x, entity.dxf.center.y)
        radius = float(entity.dxf.radius)
        contour_primitives.append(_circle_contour(center, radius, contour_id="", source_entity_type=source_type))
        _update_bounds(
            bounds,
            [
                (center[0] - radius, center[1] - radius),
                (center[0] + radius, center[1] + radius),
            ],
        )
        return

    if entity_type in {"LWPOLYLINE", "POLYLINE"}:
        try:
            virtual_entities = list(entity.virtual_entities())
        except Exception as exc:
            notes.append(f"Failed to decompose `{entity_type}` into virtual edges: {exc}")
            return
        for virtual_entity in virtual_entities:
            _ingest_entity_geometry(
                virtual_entity,
                edge_primitives=edge_primitives,
                contour_primitives=contour_primitives,
                bounds=bounds,
                notes=notes,
                source_entity_type=source_type,
            )
        return

    if entity_type in {"ELLIPSE", "SPLINE"}:
        try:
            points = [(_point_tuple(point.x, point.y)) for point in entity.flattening(DEFAULT_FLATTEN_TOLERANCE)]
        except Exception as exc:
            notes.append(f"Failed to flatten `{entity_type}` for contour analysis: {exc}")
            return
        if len(points) < 2:
            notes.append(f"`{entity_type}` did not produce enough points for contour analysis.")
            return
        _update_bounds(bounds, points)
        notes.append(
            f"`{entity_type}` was approximated as line segments with flatten tolerance {DEFAULT_FLATTEN_TOLERANCE:g}."
        )
        for index in range(len(points) - 1):
            edge = _make_line_edge(points[index], points[index + 1], source_type, approximated=True)
            if edge is not None:
                edge_primitives.append(edge)
        closed = bool(getattr(entity, "closed", False))
        if closed and not _points_close(points[0], points[-1]):
            edge = _make_line_edge(points[-1], points[0], source_type, approximated=True)
            if edge is not None:
                edge_primitives.append(edge)
        return

    notes.append(f"Entity type `{entity_type}` is preserved in counts but not specially analysed.")


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
    notes: list[str] = []
    warnings: list[str] = []
    edge_primitives: list[em.Edge] = []
    contour_primitives: list[ContourSummary] = []

    for entity in modelspace:
        entity_type = entity.dxftype()
        entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
        _ingest_entity_geometry(entity, edge_primitives, contour_primitives, bounds, notes)

    contours: list[ContourSummary] = []
    contour_counter = 1
    for contour in contour_primitives:
        contour.contour_id = f"contour_{contour_counter:03d}"
        contour_counter += 1
        contours.append(contour)

    loop_error: Exception | None = None
    detected_loops: list[list[em.Edge]] = []
    if edge_primitives:
        try:
            deposit = em.Deposit(edge_primitives, gap_tol=DEFAULT_GAP_TOLERANCE)
            detected_loops = [list(loop) for loop in em.find_all_loops(deposit, timeout=LOOP_TIMEOUT_SECONDS)]
        except em.TimeoutError as exc:
            loop_error = exc
            detected_loops = [list(loop) for loop in getattr(exc, "solutions", [])]
            warnings.append(
                "Loop detection timed out before exploring every contour candidate. Partial contour results were preserved."
            )
        except Exception as exc:
            loop_error = exc
            warnings.append(f"Loop detection failed for non-circular geometry: {exc}")

    used_edge_ids = {edge.id for loop in detected_loops for edge in loop}
    for loop in detected_loops:
        contours.append(_contour_from_edges(loop, contour_id=f"contour_{contour_counter:03d}"))
        contour_counter += 1

    open_chains: list[OpenChainSummary] = []
    remaining_edges = [edge for edge in edge_primitives if edge.id not in used_edge_ids]
    if remaining_edges:
        remaining_deposit = em.Deposit(remaining_edges, gap_tol=DEFAULT_GAP_TOLERANCE)
        for chain_index, chain in enumerate(em.find_all_simple_chains(remaining_deposit), start=1):
            open_chains.append(_open_chain_from_edges(list(chain), chain_id=f"open_chain_{chain_index:03d}"))

    _classify_contours(contours)
    frame_contour_ids = _detect_drawing_frame_contours(
        contours,
        overall_bbox=_bbox_from_bounds(bounds),
        entity_counts=entity_counts,
        open_chain_count=len(open_chains),
    )
    if frame_contour_ids:
        _classify_contours(contours, ignored_ids=frame_contour_ids)
        notes.append(
            "Ignored likely drawing frame contour(s) and recomputed contour nesting for the enclosed part geometry."
        )
    excluded_annotation_ids = _exclude_annotation_loops(
        contours,
        entity_counts=entity_counts,
        open_chain_count=len(open_chains),
    )
    if excluded_annotation_ids:
        notes.append(
            "Excluded likely annotation loops from part reconstruction after contour classification."
        )
    contours.sort(key=lambda contour: contour.contour_id)
    open_chains.sort(key=lambda chain: chain.chain_id)

    hole_candidates = [
        HoleCandidate(
            center_x=contour.segments[0].center.x,
            center_y=contour.segments[0].center.y,
            radius=float(contour.segments[0].radius),
            diameter=float(contour.segments[0].radius) * 2.0,
            contour_id=contour.contour_id,
            role=contour.role,
            nesting_depth=contour.nesting_depth,
        )
        for contour in contours
        if contour.is_hole_candidate and contour.segments and contour.segments[0].center is not None and contour.segments[0].radius is not None
    ]

    insunits_value = int(document.header.get("$INSUNITS", 0) or 0)
    geometry_summary = GeometrySummary(
        source_file=str(source_file),
        effective_input_file=str(effective_input_file),
        file_type="dxf",
        units=INSUNITS_MAP.get(insunits_value),
        entity_counts=entity_counts,
        bounding_box=_bbox_from_bounds(bounds),
        hole_candidates=hole_candidates,
        contours=contours,
        open_chains=open_chains,
        outer_profile_ids=[contour.contour_id for contour in contours if contour.role == "outer_profile"],
        cutout_ids=[contour.contour_id for contour in contours if contour.role == "cutout"],
        island_ids=[contour.contour_id for contour in contours if contour.role == "island"],
        hole_contour_ids=[contour.contour_id for contour in contours if contour.role == "hole"],
        slot_candidate_ids=[contour.contour_id for contour in contours if contour.is_slot_candidate],
        closed_contour_count=len(contours),
        open_chain_count=len(open_chains),
        warnings=warnings,
        notes=_dedupe_preserve_order(notes),
    )

    if geometry_summary.units is None:
        geometry_summary.warnings.append(
            "DXF units were not embedded in the file. HermesCAD should confirm units unless the request text is explicit."
        )
    if geometry_summary.closed_contour_count == 0:
        geometry_summary.warnings.append(
            "No closed contours were detected. HermesCAD cannot safely build a solid until the 2D profile is closed."
        )
    if geometry_summary.open_chain_count > 0:
        geometry_summary.warnings.append(
            f"{geometry_summary.open_chain_count} open chain(s) were detected. The drawing may contain construction geometry or incomplete contours."
        )
    if len(geometry_summary.outer_profile_ids) > 1:
        if _drawing_has_annotations(entity_counts, len(open_chains)):
            geometry_summary.warnings.append(
                "Multiple disjoint top-level closed profiles remained after excluding drawing-frame or annotation geometry. "
                "The drawing likely contains multiple annotated views, so HermesCAD cannot safely infer one manufacturable part profile."
            )
        else:
            geometry_summary.notes.append(
                "Multiple top-level outer profiles were detected. HermesCAD will treat them as multiple planar regions in one job."
            )
    if loop_error is not None:
        geometry_summary.notes.append(f"Loop analysis diagnostic: {loop_error}")

    geometry_summary_path = output_dir / "geometry_summary.json"
    geometry_summary.geometry_summary_path = str(geometry_summary_path)
    geometry_summary_path.write_text(
        json.dumps(geometry_summary.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return geometry_summary
