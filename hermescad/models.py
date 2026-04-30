from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Point2D(BaseModel):
    x: float
    y: float


class BoundingBox(BaseModel):
    min_x: float | None = None
    min_y: float | None = None
    max_x: float | None = None
    max_y: float | None = None
    width: float | None = None
    height: float | None = None


class HoleCandidate(BaseModel):
    center_x: float
    center_y: float
    radius: float
    diameter: float
    contour_id: str | None = None
    role: str | None = None
    nesting_depth: int | None = None


class GeometrySegment(BaseModel):
    kind: str
    start: Point2D
    end: Point2D
    source_entity_type: str
    approximated: bool = False
    center: Point2D | None = None
    radius: float | None = None
    start_angle_deg: float | None = None
    end_angle_deg: float | None = None
    sweep_angle_deg: float | None = None


class ContourSummary(BaseModel):
    contour_id: str
    source: str
    closed: bool = True
    source_entity_types: list[str] = Field(default_factory=list)
    segment_types: list[str] = Field(default_factory=list)
    segments: list[GeometrySegment] = Field(default_factory=list)
    sampled_points: list[Point2D] = Field(default_factory=list)
    bounding_box: BoundingBox = Field(default_factory=BoundingBox)
    area: float = 0.0
    perimeter: float = 0.0
    orientation: str = "Unknown"
    nesting_depth: int = 0
    parent_contour_id: str | None = None
    child_contour_ids: list[str] = Field(default_factory=list)
    role: str = "ambiguous"
    is_circle: bool = False
    is_hole_candidate: bool = False
    is_slot_candidate: bool = False
    notes: list[str] = Field(default_factory=list)


class OpenChainSummary(BaseModel):
    chain_id: str
    source_entity_types: list[str] = Field(default_factory=list)
    segment_types: list[str] = Field(default_factory=list)
    segments: list[GeometrySegment] = Field(default_factory=list)
    sampled_points: list[Point2D] = Field(default_factory=list)
    bounding_box: BoundingBox = Field(default_factory=BoundingBox)
    approximate_length: float = 0.0
    start_point: Point2D | None = None
    end_point: Point2D | None = None
    notes: list[str] = Field(default_factory=list)


class FeatureOperation(BaseModel):
    operation_id: str
    kind: str
    target_kind: str
    contour_ids: list[str] = Field(default_factory=list)
    depth_mm: float
    parameters: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class FeaturePlan(BaseModel):
    base_thickness_mm: float
    chamfer_mm: float | None = None
    operations: list[FeatureOperation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    feature_plan_path: str | None = None


class GeometrySummary(BaseModel):
    source_file: str
    effective_input_file: str
    file_type: str
    units: str | None = None
    entity_counts: dict[str, int] = Field(default_factory=dict)
    bounding_box: BoundingBox = Field(default_factory=BoundingBox)
    hole_candidates: list[HoleCandidate] = Field(default_factory=list)
    contours: list[ContourSummary] = Field(default_factory=list)
    open_chains: list[OpenChainSummary] = Field(default_factory=list)
    outer_profile_ids: list[str] = Field(default_factory=list)
    cutout_ids: list[str] = Field(default_factory=list)
    island_ids: list[str] = Field(default_factory=list)
    hole_contour_ids: list[str] = Field(default_factory=list)
    slot_candidate_ids: list[str] = Field(default_factory=list)
    closed_contour_count: int = 0
    open_chain_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    geometry_summary_path: str | None = None


class ConversionResult(BaseModel):
    attempted: bool = False
    available: bool = False
    converted: bool = False
    input_path: str
    output_path: str | None = None
    command: str | None = None
    message: str
    stdout: str | None = None
    stderr: str | None = None


class OutputArtifact(BaseModel):
    path: str
    exists: bool = True


class FreeCADRunResult(BaseModel):
    attempted: bool = False
    available: bool = False
    succeeded: bool = False
    command: str | None = None
    message: str
    generated_files: list[str] = Field(default_factory=list)
    stdout: str | None = None
    stderr: str | None = None


class AssemblyPlacement(BaseModel):
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    rx_deg: float = 0.0
    ry_deg: float = 0.0
    rz_deg: float = 0.0


class AssemblyPartSpec(BaseModel):
    name: str
    input_file: str
    instruction_text: str
    placement: AssemblyPlacement = Field(default_factory=AssemblyPlacement)


class AssemblyManifest(BaseModel):
    assembly_name: str
    description: str | None = None
    parts: list[AssemblyPartSpec] = Field(default_factory=list)


class ProcessResult(BaseModel):
    job_id: str
    job_dir: str
    input_file: str
    effective_input_file: str
    instruction_text: str
    geometry_summary_path: str | None = None
    feature_plan_path: str | None = None
    report_path: str | None = None
    summary_path: str | None = None
    package_path: str | None = None
    cad: FreeCADRunResult = Field(
        default_factory=lambda: FreeCADRunResult(message="CAD generation not attempted.")
    )
    outputs: list[OutputArtifact] = Field(default_factory=list)
    actions_performed: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssemblyProcessResult(BaseModel):
    assembly_name: str
    job_id: str
    job_dir: str
    manifest_path: str
    report_path: str | None = None
    summary_path: str | None = None
    package_path: str | None = None
    cad: FreeCADRunResult = Field(
        default_factory=lambda: FreeCADRunResult(message="Assembly generation not attempted.")
    )
    part_results: list[ProcessResult] = Field(default_factory=list)
    outputs: list[OutputArtifact] = Field(default_factory=list)
    actions_performed: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
