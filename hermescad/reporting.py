from __future__ import annotations

from pathlib import Path

from .models import GeometrySummary, ProcessResult


def _format_bullet_lines(items: list[str], fallback: str) -> list[str]:
    if not items:
        return [f"- {fallback}"]
    return [f"- {item}" for item in items]


def _format_feature_operation_lines(metadata: dict[str, object]) -> list[str]:
    operations = metadata.get("feature_operations", [])
    if not isinstance(operations, list) or not operations:
        return ["- No structured feature operations were recorded."]

    lines: list[str] = []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        contour_ids = operation.get("contour_ids", [])
        contour_count = len(contour_ids) if isinstance(contour_ids, list) else 0
        details: list[str] = []
        parameters = operation.get("parameters", {})
        if isinstance(parameters, dict):
            for key in [
                "major_diameter_mm",
                "included_angle_deg",
                "pilot_diameter_mm",
                "tap_drill_mm",
                "thread_pitch_mm",
                "thread_profile_standard",
                "screw_size",
                "selector",
            ]:
                if key in parameters:
                    details.append(f"{key}={parameters[key]}")
        detail_suffix = f" ({', '.join(details)})" if details else ""
        lines.append(
            f"- `{operation.get('operation_id', 'op')}`: `{operation.get('kind', 'unknown')}` on `{operation.get('target_kind', 'unknown')}` across {contour_count} contour(s) at {operation.get('depth_mm', 'unknown')} mm{detail_suffix}"
        )
    return lines or ["- No structured feature operations were recorded."]


def write_markdown_report(
    result: ProcessResult,
    geometry_summary: GeometrySummary | None,
    report_path: Path,
) -> Path:
    report_path = report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    geometry_lines: list[str]
    if geometry_summary is None:
        geometry_lines = ["DXF geometry inspection was not available."]
    else:
        bbox = geometry_summary.bounding_box
        geometry_lines = [
            f"Units: {geometry_summary.units or 'Unknown'}",
            f"Entity counts: {geometry_summary.entity_counts or {}}",
            (
                "Bounding box: "
                f"{bbox.width if bbox.width is not None else 'Unknown'} x "
                f"{bbox.height if bbox.height is not None else 'Unknown'}"
            ),
            f"Closed contours: {geometry_summary.closed_contour_count}",
            f"Open chains: {geometry_summary.open_chain_count}",
            f"Outer profiles: {len(geometry_summary.outer_profile_ids)}",
            f"Cutouts: {len(geometry_summary.cutout_ids)}",
            f"Circular hole candidates: {len(geometry_summary.hole_candidates)}",
        ]

    anticipated_outputs = sorted(
        {
            Path(artifact.path).name for artifact in result.outputs
        }
        | {"report.md"}
        | ({Path(result.package_path).name} if result.package_path else set())
    )

    lines = [
        "# HermesCAD Report",
        "",
        "## Summary",
        f"- Job ID: `{result.job_id}`",
        f"- Input file: `{Path(result.input_file).name}`",
        f"- Effective input file: `{Path(result.effective_input_file).name}`",
        f"- Feature plan: `{Path(result.feature_plan_path).name}`" if result.feature_plan_path else "- Feature plan: `not generated`",
        "",
        "## Original Request",
        result.instruction_text.strip(),
        "",
        "## Geometry Summary",
        *[f"- {line}" for line in geometry_lines],
        "",
        "## Actions Performed",
        *_format_bullet_lines(result.actions_performed, "No actions were recorded."),
        "",
        "## Assumptions",
        *_format_bullet_lines(result.assumptions, "No additional assumptions were recorded."),
        "",
        "## Feature Operations",
        *_format_feature_operation_lines(result.metadata),
        "",
        "## Warnings",
        *_format_bullet_lines(
            result.warnings,
            "No extra warnings were recorded, but all outputs still require engineering review.",
        ),
        "",
        "## CAD Execution",
        f"- Attempted: `{result.cad.attempted}`",
        f"- Available: `{result.cad.available}`",
        f"- Succeeded: `{result.cad.succeeded}`",
        f"- Message: {result.cad.message}",
        "",
        "## Outputs Generated",
        *[f"- `{name}`" for name in anticipated_outputs],
        "",
        "## Failures",
        *_format_bullet_lines(result.failures, "No blocking failures were recorded."),
        "",
        "## Engineering Review Notice",
        (
            "HermesCAD is an engineering workflow agent for repeatable CAD operations. "
            "It does not claim manufacturing readiness, and generated outputs must be reviewed by an engineer."
        ),
        "",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
