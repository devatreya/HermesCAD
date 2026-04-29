from __future__ import annotations

from pathlib import Path

from .models import GeometrySummary, ProcessResult


def _format_bullet_lines(items: list[str], fallback: str) -> list[str]:
    if not items:
        return [f"- {fallback}"]
    return [f"- {item}" for item in items]


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

