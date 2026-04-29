from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import bootstrap_repo_path

bootstrap_repo_path()

from hermescad.packaging import package_job_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Package HermesCAD job outputs into a zip archive.")
    parser.add_argument("job_dir", type=Path, help="Job directory to package.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for the zip archive.")
    parser.add_argument("--job-id", type=str, help="Override the job id used in the zip file name.")
    args = parser.parse_args()

    job_id = args.job_id or args.job_dir.resolve().name
    zip_path = package_job_outputs(args.job_dir, args.output_dir, job_id)
    print(f"[HermesCAD] Wrote package to {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
