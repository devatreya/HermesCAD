from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_repo_path

bootstrap_repo_path()

from hermescad.assembly import process_assembly_manifest
from hermescad.pipeline import create_job_directory


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Process a HermesCAD assembly manifest.")
    parser.add_argument("manifest_file", type=Path, help="Assembly manifest JSON file.")
    parser.add_argument("--job-dir", type=Path, help="Existing or new job directory.")
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=repo_root / "outputs",
        help="Directory where the packaged zip file should be written.",
    )
    args = parser.parse_args()

    job_dir = args.job_dir or create_job_directory(repo_root / "jobs")
    print(f"[HermesCAD] Processing assembly manifest into `{job_dir}`")
    result = process_assembly_manifest(
        manifest_path=args.manifest_file,
        job_dir=job_dir,
        outputs_dir=args.outputs_dir,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2))

    if result.report_path and result.package_path:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
