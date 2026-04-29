from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_repo_path

bootstrap_repo_path()

from hermescad.inspection import inspect_dxf_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a DXF file with ezdxf.")
    parser.add_argument("input_file", type=Path, help="DXF input file.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory where geometry_summary.json should be written.",
    )
    args = parser.parse_args()

    summary = inspect_dxf_file(args.input_file, args.output_dir)
    print(json.dumps(summary.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
