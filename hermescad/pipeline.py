from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .conversion import convert_dwg_to_dxf
from .freecad import repository_root, run_freecad_generation
from .inspection import inspect_dxf_file
from .models import FeaturePlan, FreeCADRunResult, GeometrySummary, ProcessResult
from .packaging import collect_output_artifacts, package_job_outputs, write_output_manifest
from .planning import build_feature_plan, write_feature_plan
from .reporting import write_markdown_report

THICKNESS_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*mm\s*thick", re.IGNORECASE),
    re.compile(r"thickness\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
]
CHAMFER_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*mm\s*chamfers?", re.IGNORECASE),
    re.compile(r"add\s+(\d+(?:\.\d+)?)\s*mm\s*chamfers?", re.IGNORECASE),
]


def _extract_measurement(text: str, patterns: list[re.Pattern[str]]) -> float | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


def _has_millimetre_context(text: str) -> bool:
    lowered = text.lower()
    return " mm" in lowered or "millimet" in lowered


def create_job_directory(base_dir: Path | None = None) -> Path:
    base_dir = (base_dir or repository_root() / "jobs").resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job_dir = base_dir / f"job_{timestamp}"
    suffix = 1
    while job_dir.exists():
        suffix += 1
        job_dir = base_dir / f"job_{timestamp}_{suffix}"
    job_dir.mkdir(parents=True, exist_ok=False)
    return job_dir


def _write_text_file(path: Path, contents: str) -> None:
    path.write_text(contents.strip() + "\n", encoding="utf-8")


def _write_summary_json(path: Path, result: ProcessResult) -> None:
    path.write_text(json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8")


def process_cad_request(
    input_file: Path,
    instruction_text: str,
    job_dir: Path,
    outputs_dir: Path | None = None,
    *,
    package_outputs: bool = True,
) -> ProcessResult:
    input_file = input_file.resolve()
    job_dir = job_dir.resolve()
    outputs_dir = (outputs_dir or repository_root() / "outputs").resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    copied_input = job_dir / input_file.name
    if input_file != copied_input:
        shutil.copy2(input_file, copied_input)

    request_file = job_dir / "request.txt"
    _write_text_file(request_file, instruction_text)

    result = ProcessResult(
        job_id=job_dir.name,
        job_dir=str(job_dir),
        input_file=str(input_file),
        effective_input_file=str(copied_input),
        instruction_text=instruction_text.strip(),
        metadata={
            "requested_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    result.actions_performed.extend(
        [
            f"Created job directory `{job_dir.name}`.",
            f"Copied input drawing to `{copied_input.name}`.",
            "Stored the original request text in `request.txt`.",
        ]
    )

    effective_input = copied_input
    geometry_summary: GeometrySummary | None = None
    feature_plan: FeaturePlan | None = None

    if copied_input.suffix.lower() == ".dwg":
        conversion = convert_dwg_to_dxf(copied_input, job_dir)
        result.actions_performed.append("Attempted DWG to DXF conversion with LibreDWG.")
        if conversion.converted and conversion.output_path:
            effective_input = Path(conversion.output_path)
            result.effective_input_file = conversion.output_path
            result.assumptions.append("DWG input was converted to DXF before inspection and modeling.")
        else:
            result.warnings.append(conversion.message)
            if conversion.stderr:
                result.failures.append(conversion.stderr)

    if effective_input.suffix.lower() == ".dxf":
        try:
            geometry_summary = inspect_dxf_file(copied_input, job_dir, effective_input)
            result.geometry_summary_path = geometry_summary.geometry_summary_path
            result.actions_performed.append("Inspected DXF geometry and saved `geometry_summary.json`.")
        except Exception as exc:
            result.failures.append(str(exc))
            result.warnings.append("DXF inspection failed, so CAD generation was skipped.")
    else:
        result.warnings.append(
            "Effective input is not DXF. HermesCAD could not inspect geometry or generate the MVP 3D model."
        )

    thickness_mm = _extract_measurement(instruction_text, THICKNESS_PATTERNS)
    chamfer_mm = _extract_measurement(instruction_text, CHAMFER_PATTERNS)
    can_attempt_cad = geometry_summary is not None and thickness_mm is not None

    if thickness_mm is None:
        result.failures.append(
            "Thickness was not provided in the request. Hermes should ask the user for thickness before 2D-to-3D generation."
        )
    else:
        result.assumptions.append(f"Model thickness interpreted as {thickness_mm:g} mm from the request text.")

    if chamfer_mm is not None:
        result.assumptions.append(
            f"Outside-edge chamfer interpreted as {chamfer_mm:g} mm where the simplified FreeCAD model supports it."
        )
    else:
        result.warnings.append("No chamfer value was detected, so chamfering was skipped.")

    if geometry_summary is not None:
        if geometry_summary.units:
            result.assumptions.append(f"Drawing units interpreted as {geometry_summary.units}.")
        elif _has_millimetre_context(instruction_text):
            result.assumptions.append(
                "DXF units were not embedded. Millimetres were assumed because the request text explicitly used mm."
            )
        else:
            can_attempt_cad = False
            result.failures.append(
                "DXF units were not embedded and the request text did not provide enough context to safely assume units."
            )

        result.assumptions.append(
            "HermesCAD reconstructs closed 2D contours, treats top-level contours as material regions, "
            "treats nested odd-depth contours as cutouts, and interprets circular cutouts as through-hole candidates."
        )
        if geometry_summary.closed_contour_count == 0:
            can_attempt_cad = False
            result.failures.append(
                "No closed contours were detected, so HermesCAD could not safely reconstruct a 2D profile for extrusion."
            )

    result.warnings.append(
        "Generated outputs require engineering review and are not claimed to be manufacturing-ready."
    )

    if can_attempt_cad and geometry_summary and result.geometry_summary_path:
        feature_plan = build_feature_plan(
            instruction_text=instruction_text,
            geometry_summary=geometry_summary,
            thickness_mm=thickness_mm,
            chamfer_mm=chamfer_mm,
        )
        feature_plan_path = write_feature_plan(job_dir / "feature_plan.json", feature_plan)
        result.feature_plan_path = str(feature_plan_path)
        result.actions_performed.append("Built a structured feature plan from the request text and inspected contours.")
        result.assumptions.append(
            f"Planned {len(feature_plan.operations)} ordered feature operation(s) from the current geometry and request text."
        )
        result.warnings.extend(feature_plan.warnings)
        if chamfer_mm is not None and any(operation.kind == "countersink_hole" for operation in feature_plan.operations):
            result.warnings.append(
                "Exterior chamfers were requested along with countersinks. HermesCAD will prioritize the countersink operations and skip the exterior chamfer in the same run for FreeCAD robustness."
            )
        result.metadata["feature_operations"] = [operation.model_dump(mode="json") for operation in feature_plan.operations]

        cad_result = run_freecad_generation(
            dxf_path=effective_input,
            geometry_summary_path=Path(result.geometry_summary_path),
            feature_plan_path=feature_plan_path,
            output_dir=job_dir,
            thickness_mm=thickness_mm,
            chamfer_mm=chamfer_mm,
        )
        result.cad = cad_result
        if cad_result.succeeded:
            result.actions_performed.append("Generated FreeCAD outputs through the local FreeCAD automation path.")
        elif not cad_result.available:
            result.warnings.append(cad_result.message)
            result.actions_performed.append("FreeCAD was unavailable, so HermesCAD stayed in inspection/report fallback mode.")
        else:
            result.failures.append(cad_result.message)
            result.actions_performed.append("Tried to generate a FreeCAD model, but the automation step failed.")
    else:
        result.cad = FreeCADRunResult(
            attempted=False,
            available=False,
            succeeded=False,
            message="CAD generation was skipped because required geometry, units, or thickness information was unavailable.",
        )
        result.actions_performed.append("Skipped CAD generation and continued with inspection/report/package outputs.")

    result.outputs = collect_output_artifacts(job_dir)
    result.report_path = str((job_dir / "report.md").resolve())
    if package_outputs:
        result.package_path = str((outputs_dir / f"{job_dir.name}_outputs.zip").resolve())
    else:
        result.package_path = None

    write_markdown_report(result, geometry_summary, Path(result.report_path))
    result.actions_performed.append("Generated the Markdown engineering assumptions report.")

    write_output_manifest(job_dir)
    result.actions_performed.append("Wrote `outputs_manifest.json` for downstream packaging/debugging.")

    result.summary_path = str((job_dir / "job_summary.json").resolve())
    result.outputs = collect_output_artifacts(job_dir)
    _write_summary_json(Path(result.summary_path), result)

    if package_outputs:
        try:
            package_job_outputs(job_dir, outputs_dir, job_dir.name)
            result.actions_performed.append("Packaged generated outputs into a zip archive.")
        except Exception as exc:
            result.package_path = None
            result.failures.append(f"Failed to package outputs: {exc}")
    else:
        result.actions_performed.append("Skipped per-part packaging because this request is being used inside a larger workflow.")

    result.outputs = collect_output_artifacts(job_dir)
    _write_summary_json(Path(result.summary_path), result)
    return result
