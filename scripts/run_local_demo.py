from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import bootstrap_repo_path

bootstrap_repo_path()

from hermescad.pipeline import create_job_directory, process_cad_request


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run the HermesCAD local demo.")
    parser.add_argument(
        "--input",
        type=Path,
        default=repo_root / "examples" / "drawings" / "bracket_simple.dxf",
        help="DXF or DWG input drawing.",
    )
    parser.add_argument(
        "--instruction-file",
        type=Path,
        default=repo_root / "examples" / "requests" / "example_email_request.txt",
        help="Text file containing the natural-language request.",
    )
    parser.add_argument(
        "--jobs-dir",
        type=Path,
        default=repo_root / "jobs",
        help="Directory where job folders should be created.",
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=repo_root / "outputs",
        help="Directory where packaged zip files should be written.",
    )
    args = parser.parse_args()

    instruction_text = args.instruction_file.read_text(encoding="utf-8").strip()
    job_dir = create_job_directory(args.jobs_dir)

    print(f"[HermesCAD] Starting local demo in `{job_dir}`")
    print(f"[HermesCAD] Input drawing: `{args.input}`")
    print(f"[HermesCAD] Request file: `{args.instruction_file}`")

    result = process_cad_request(
        input_file=args.input,
        instruction_text=instruction_text,
        job_dir=job_dir,
        outputs_dir=args.outputs_dir,
    )

    print(f"[HermesCAD] Geometry summary: {result.geometry_summary_path or 'not generated'}")
    print(f"[HermesCAD] Report: {result.report_path or 'not generated'}")
    print(f"[HermesCAD] Package: {result.package_path or 'not generated'}")
    print(f"[HermesCAD] FreeCAD status: {result.cad.message}")

    if result.failures:
        print("[HermesCAD] Recorded failures:")
        for failure in result.failures:
            print(f"  - {failure}")

    if result.report_path and result.package_path:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
