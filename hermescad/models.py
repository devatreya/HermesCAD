from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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


class GeometrySummary(BaseModel):
    source_file: str
    effective_input_file: str
    file_type: str
    units: str | None = None
    entity_counts: dict[str, int] = Field(default_factory=dict)
    bounding_box: BoundingBox = Field(default_factory=BoundingBox)
    hole_candidates: list[HoleCandidate] = Field(default_factory=list)
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


class ProcessResult(BaseModel):
    job_id: str
    job_dir: str
    input_file: str
    effective_input_file: str
    instruction_text: str
    geometry_summary_path: str | None = None
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

