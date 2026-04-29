from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import bootstrap_repo_path

bootstrap_repo_path()

from hermescad.models import GeometrySummary, ProcessResult
from hermescad.reporting import write_markdown_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a HermesCAD Markdown report from job JSON files.")
    parser.add_argument("--job-summary", type=Path, required=True, help="Path to job_summary.json.")
    parser.add_argument("--geometry-summary", type=Path, help="Path to geometry_summary.json.")
    parser.add_argument("--report-path", type=Path, required=True, help="Path to report.md.")
    args = parser.parse_args()

    result = ProcessResult.model_validate_json(args.job_summary.read_text(encoding="utf-8"))
    geometry_summary = None
    if args.geometry_summary and args.geometry_summary.exists():
        geometry_summary = GeometrySummary.model_validate_json(args.geometry_summary.read_text(encoding="utf-8"))

    report_path = write_markdown_report(result, geometry_summary, args.report_path)
    print(f"[HermesCAD] Wrote report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
