from __future__ import annotations

import json
import shutil
from pathlib import Path

from .freecad import repository_root, run_freecad_assembly
from .models import AssemblyManifest, AssemblyProcessResult, GeometrySummary, ProcessResult
from .packaging import collect_output_artifacts, package_job_outputs, write_output_manifest
from .pipeline import process_cad_request
from .planning import select_hole_contour_ids


def load_assembly_manifest(manifest_path: Path) -> AssemblyManifest:
    manifest_path = manifest_path.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return AssemblyManifest.model_validate(payload)


def _write_summary_json(path: Path, payload: AssemblyProcessResult) -> None:
    path.write_text(json.dumps(payload.model_dump(mode="json"), indent=2), encoding="utf-8")


def _load_geometry_summary(path: Path) -> GeometrySummary:
    return GeometrySummary.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _build_runtime_fastener_specs(
    manifest: AssemblyManifest,
    processed_parts: dict[str, dict[str, object]],
    result: AssemblyProcessResult,
) -> list[dict[str, object]]:
    runtime_fasteners: list[dict[str, object]] = []
    requested_fasteners: list[dict[str, object]] = []

    for fastener_spec in manifest.fasteners:
        requested_fasteners.append(
            {
                "name": fastener_spec.name,
                "standard": fastener_spec.standard,
                "diameter": fastener_spec.diameter,
                "length_mm": fastener_spec.length_mm,
                "source_part": fastener_spec.source_part,
                "hole_selector": fastener_spec.hole_selector,
                "thread_mode": fastener_spec.thread_mode,
                "head_side": fastener_spec.head_side,
            }
        )

        part_context = processed_parts.get(fastener_spec.source_part)
        if part_context is None:
            result.warnings.append(
                f"Fastener group `{fastener_spec.name}` referenced unknown part `{fastener_spec.source_part}`, so HermesCAD skipped those fasteners."
            )
            continue

        part_result = part_context["result"]
        if not isinstance(part_result, ProcessResult) or not part_result.geometry_summary_path:
            result.warnings.append(
                f"Fastener group `{fastener_spec.name}` could not resolve a geometry summary for part `{fastener_spec.source_part}`, so HermesCAD skipped those fasteners."
            )
            continue

        geometry_summary_path = Path(part_result.geometry_summary_path).resolve()
        if not geometry_summary_path.exists():
            result.warnings.append(
                f"Fastener group `{fastener_spec.name}` expected geometry summary `{geometry_summary_path.name}` for part `{fastener_spec.source_part}`, but it was missing."
            )
            continue

        geometry_summary = _load_geometry_summary(geometry_summary_path)
        target_contour_ids = select_hole_contour_ids(geometry_summary, fastener_spec.hole_selector)
        if not target_contour_ids:
            result.warnings.append(
                f"Fastener group `{fastener_spec.name}` could not resolve `{fastener_spec.hole_selector}` hole targets on part `{fastener_spec.source_part}`."
            )
            continue

        target_id_set = set(target_contour_ids)
        selected_holes = [
            hole
            for hole in geometry_summary.hole_candidates
            if hole.contour_id and str(hole.contour_id) in target_id_set
        ]
        if not selected_holes:
            result.warnings.append(
                f"Fastener group `{fastener_spec.name}` resolved contour IDs on part `{fastener_spec.source_part}`, but no circular hole centers were available for placement."
            )
            continue

        runtime_fasteners.append(
            {
                "name": fastener_spec.name,
                "description": fastener_spec.description,
                "standard": fastener_spec.standard,
                "diameter": fastener_spec.diameter,
                "length_mm": fastener_spec.length_mm,
                "source_part": fastener_spec.source_part,
                "hole_selector": fastener_spec.hole_selector,
                "thread_mode": fastener_spec.thread_mode,
                "head_side": fastener_spec.head_side,
                "offset_mm": fastener_spec.offset_mm,
                "hole_centers_local_mm": [
                    {
                        "contour_id": str(hole.contour_id),
                        "x_mm": hole.center_x,
                        "y_mm": hole.center_y,
                    }
                    for hole in selected_holes
                ],
            }
        )
        result.actions_performed.append(
            f"Resolved {len(selected_holes)} placement points for fastener group `{fastener_spec.name}` from the `{fastener_spec.hole_selector}` holes on part `{fastener_spec.source_part}`."
        )

    if requested_fasteners:
        result.metadata["requested_fasteners"] = requested_fasteners
    return runtime_fasteners


def _write_assembly_report(result: AssemblyProcessResult, report_path: Path) -> Path:
    report_path = report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# HermesCAD Assembly Report",
        "",
        "## Summary",
        f"- Assembly name: `{result.assembly_name}`",
        f"- Job ID: `{result.job_id}`",
        f"- Manifest: `{Path(result.manifest_path).name}`",
        "",
        "## Actions Performed",
    ]
    if result.actions_performed:
        lines.extend(f"- {action}" for action in result.actions_performed)
    else:
        lines.append("- No actions were recorded.")

    lines.extend(
        [
            "",
            "## Assumptions",
        ]
    )
    if result.assumptions:
        lines.extend(f"- {assumption}" for assumption in result.assumptions)
    else:
        lines.append("- No additional assumptions were recorded.")

    lines.extend(
        [
            "",
            "## Fasteners",
        ]
    )
    requested_fasteners = result.metadata.get("requested_fasteners", [])
    if requested_fasteners:
        for fastener in requested_fasteners:
            if not isinstance(fastener, dict):
                continue
            lines.append(
                (
                    f"- Requested `{fastener.get('standard', 'unknown')}` `{fastener.get('diameter', 'unknown')}` "
                    f"fasteners from part `{fastener.get('source_part', 'unknown')}` using the "
                    f"`{fastener.get('hole_selector', 'all')}` hole selector at `{fastener.get('length_mm', 'unknown')}` mm length."
                )
            )
    else:
        lines.append("- No explicit assembly fasteners were requested in the manifest.")

    assembly_result = result.metadata.get("assembly_result")
    if isinstance(assembly_result, dict):
        inserted_fasteners = assembly_result.get("fasteners", [])
        fastener_warnings = assembly_result.get("fastener_warnings", [])
        if inserted_fasteners:
            lines.append("Inserted fastener instances:")
            for fastener in inserted_fasteners:
                if not isinstance(fastener, dict):
                    continue
                lines.append(
                    (
                        f"  - `{fastener.get('standard', 'unknown')}` `{fastener.get('diameter', 'unknown')}` "
                        f"x `{fastener.get('length_mm', 'unknown')}` mm on `{fastener.get('source_part', 'unknown')}`: "
                        f"{fastener.get('inserted_count', 0)} inserted."
                    )
                )
        if fastener_warnings:
            lines.extend(f"- Fastener warning: {warning}" for warning in fastener_warnings if isinstance(warning, str))

    lines.extend(
        [
            "",
            "## Part Results",
        ]
    )
    if result.part_results:
        for part_result in result.part_results:
            lines.append(
                f"- `{Path(part_result.job_dir).name}`: CAD succeeded=`{part_result.cad.succeeded}` input=`{Path(part_result.input_file).name}`"
            )
    else:
        lines.append("- No part results were recorded.")

    lines.extend(
        [
            "",
            "## CAD Execution",
            f"- Attempted: `{result.cad.attempted}`",
            f"- Available: `{result.cad.available}`",
            f"- Succeeded: `{result.cad.succeeded}`",
            f"- Message: {result.cad.message}",
            "",
            "## Warnings",
        ]
    )
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- No extra warnings were recorded, but all outputs still require engineering review.")

    lines.extend(
        [
            "",
            "## Failures",
        ]
    )
    if result.failures:
        lines.extend(f"- {failure}" for failure in result.failures)
    else:
        lines.append("- No blocking failures were recorded.")

    lines.extend(
        [
            "",
            "## Engineering Review Notice",
            (
                "HermesCAD assemblies are deterministic placement workflows built from generated part outputs. "
                "They do not claim manufacturing readiness, fit validation, tolerance validation, or fastener correctness."
            ),
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def process_assembly_manifest(
    manifest_path: Path,
    job_dir: Path,
    outputs_dir: Path | None = None,
) -> AssemblyProcessResult:
    manifest = load_assembly_manifest(manifest_path)
    manifest_path = manifest_path.resolve()
    job_dir = job_dir.resolve()
    outputs_dir = (outputs_dir or repository_root() / "outputs").resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    copied_manifest = job_dir / manifest_path.name
    if copied_manifest != manifest_path:
        shutil.copy2(manifest_path, copied_manifest)

    result = AssemblyProcessResult(
        assembly_name=manifest.assembly_name,
        job_id=job_dir.name,
        job_dir=str(job_dir),
        manifest_path=str(copied_manifest),
        assumptions=[
            "HermesCAD assembly placement is explicit from the manifest. It does not infer mates or constraints automatically.",
            "All generated threaded holes and assembly placements still require engineering review before fabrication or release.",
        ],
    )
    result.actions_performed.extend(
        [
            f"Created assembly job directory `{job_dir.name}`.",
            f"Copied the assembly manifest to `{copied_manifest.name}`.",
        ]
    )
    if manifest.description:
        result.metadata["description"] = manifest.description

    parts_dir = job_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    assembly_part_specs: list[dict[str, object]] = []
    processed_parts: dict[str, dict[str, object]] = {}

    for part_spec in manifest.parts:
        part_job_dir = parts_dir / part_spec.name
        part_result: ProcessResult = process_cad_request(
            input_file=Path(part_spec.input_file),
            instruction_text=part_spec.instruction_text,
            job_dir=part_job_dir,
            outputs_dir=outputs_dir,
            package_outputs=False,
        )
        result.part_results.append(part_result)
        processed_parts[part_spec.name] = {
            "part_spec": part_spec,
            "result": part_result,
        }
        result.actions_performed.append(
            f"Processed part `{part_spec.name}` into `{part_job_dir.relative_to(job_dir)}`."
        )

        if not part_result.cad.succeeded:
            result.failures.append(
                f"Part `{part_spec.name}` did not complete CAD generation successfully, so the assembly model was not attempted."
            )
            continue

        fcstd_path = part_job_dir / "hermescad_model.FCStd"
        step_path = part_job_dir / "hermescad_model.step"
        if not fcstd_path.exists() or not step_path.exists():
            result.failures.append(
                f"Part `{part_spec.name}` was missing expected CAD outputs, so the assembly model was not attempted."
            )
            continue

        assembly_part_specs.append(
            {
                "name": part_spec.name,
                "fcstd_path": str(fcstd_path.resolve()),
                "step_path": str(step_path.resolve()),
                "placement": part_spec.placement.model_dump(mode="json"),
            }
        )

    runtime_fasteners = _build_runtime_fastener_specs(manifest, processed_parts, result)

    if not result.failures and assembly_part_specs:
        runtime_config_path = job_dir / "freecad_assembly_runtime.json"
        runtime_config = {
            "config_path": str(runtime_config_path.resolve()),
            "assembly_name": manifest.assembly_name,
            "description": manifest.description,
            "output_dir": str(job_dir.resolve()),
            "parts": assembly_part_specs,
            "fasteners": runtime_fasteners,
        }
        runtime_config_path.write_text(json.dumps(runtime_config, indent=2), encoding="utf-8")
        result.actions_performed.append("Wrote the FreeCAD assembly runtime config.")
        result.cad = run_freecad_assembly(runtime_config, job_dir)
        if result.cad.succeeded:
            result.actions_performed.append("Generated the assembly outputs through the local FreeCAD automation path.")
        else:
            result.failures.append(result.cad.message)
            result.actions_performed.append("Tried to generate the FreeCAD assembly, but the automation step failed.")
    else:
        result.cad.message = "Assembly generation was skipped because one or more parts did not complete successfully."
        result.cad.available = True
        result.cad.attempted = False
        result.cad.succeeded = False

    assembly_result_path = job_dir / "assembly_result.json"
    if assembly_result_path.exists():
        try:
            result.metadata["assembly_result"] = json.loads(assembly_result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            result.warnings.append(f"Failed to parse `assembly_result.json`: {exc}")

    result.report_path = str((job_dir / "assembly_report.md").resolve())
    _write_assembly_report(result, Path(result.report_path))
    result.actions_performed.append("Generated the assembly report.")

    write_output_manifest(job_dir)
    result.actions_performed.append("Wrote `outputs_manifest.json` for the assembly workflow.")

    result.summary_path = str((job_dir / "assembly_summary.json").resolve())
    result.outputs = collect_output_artifacts(job_dir)
    _write_summary_json(Path(result.summary_path), result)

    result.package_path = str((outputs_dir / f"{job_dir.name}_outputs.zip").resolve())
    try:
        package_job_outputs(job_dir, outputs_dir, job_dir.name)
        result.actions_performed.append("Packaged the assembly job outputs into a zip archive.")
    except Exception as exc:
        result.package_path = None
        result.failures.append(f"Failed to package assembly outputs: {exc}")

    result.outputs = collect_output_artifacts(job_dir)
    _write_summary_json(Path(result.summary_path), result)
    return result
