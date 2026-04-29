from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_repo_path

bootstrap_repo_path()

from hermescad.pipeline import create_job_directory, process_cad_request


def _load_instruction_text(args: argparse.Namespace) -> str:
    if args.instruction_file:
        return args.instruction_file.read_text(encoding="utf-8").strip()
    if args.instruction_text:
        return args.instruction_text.strip()
    raise ValueError("Provide either --instruction-text or --instruction-file.")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Process a HermesCAD CAD request.")
    parser.add_argument("input_file", type=Path, help="Input DXF or DWG file.")
    parser.add_argument("--instruction-text", type=str, help="Natural-language CAD request.")
    parser.add_argument("--instruction-file", type=Path, help="Path to a text file containing the request.")
    parser.add_argument("--job-dir", type=Path, help="Existing or new job directory.")
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=repo_root / "outputs",
        help="Directory where packaged zip files should be written.",
    )
    args = parser.parse_args()

    instruction_text = _load_instruction_text(args)
    job_dir = args.job_dir or create_job_directory(repo_root / "jobs")

    print(f"[HermesCAD] Processing request into `{job_dir}`")
    result = process_cad_request(
        input_file=args.input_file,
        instruction_text=instruction_text,
        job_dir=job_dir,
        outputs_dir=args.outputs_dir,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2))

    if result.report_path and result.package_path:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
