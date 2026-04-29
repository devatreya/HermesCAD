from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import bootstrap_repo_path

bootstrap_repo_path()

from hermescad.conversion import convert_dwg_to_dxf


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert DWG input to DXF using LibreDWG.")
    parser.add_argument("input_file", type=Path, help="DWG input file.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory where the converted DXF should be written.",
    )
    args = parser.parse_args()

    result = convert_dwg_to_dxf(args.input_file, args.output_dir)
    print(f"[HermesCAD] {result.message}")
    if result.output_path:
        print(f"[HermesCAD] Output: {result.output_path}")
    if result.command:
        print(f"[HermesCAD] Command: {result.command}")

    if result.converted or not result.attempted:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
