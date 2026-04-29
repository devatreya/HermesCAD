from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import bootstrap_repo_path

bootstrap_repo_path()

from hermescad.packaging import collect_output_artifacts, write_output_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an outputs manifest for a HermesCAD job.")
    parser.add_argument("job_dir", type=Path, help="Job directory to scan.")
    parser.add_argument("--manifest-path", type=Path, help="Optional manifest output path.")
    args = parser.parse_args()

    manifest_path = write_output_manifest(args.job_dir, args.manifest_path)
    artifacts = collect_output_artifacts(args.job_dir)
    print(f"[HermesCAD] Wrote manifest to {manifest_path}")
    print(f"[HermesCAD] Found {len(artifacts)} artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
