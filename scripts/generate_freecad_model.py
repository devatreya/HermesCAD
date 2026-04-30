from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_repo_path

bootstrap_repo_path()

from hermescad.freecad import run_freecad_generation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the FreeCAD-side HermesCAD model generation.")
    parser.add_argument("--dxf", type=Path, required=True, help="Input DXF file.")
    parser.add_argument(
        "--geometry-summary",
        type=Path,
        required=True,
        help="Path to geometry_summary.json.",
    )
    parser.add_argument(
        "--feature-plan",
        type=Path,
        required=True,
        help="Path to feature_plan.json.",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="Job output directory.")
    parser.add_argument("--thickness-mm", type=float, required=True, help="Requested thickness in mm.")
    parser.add_argument("--chamfer-mm", type=float, help="Optional chamfer size in mm.")
    args = parser.parse_args()

    result = run_freecad_generation(
        dxf_path=args.dxf,
        geometry_summary_path=args.geometry_summary,
        feature_plan_path=args.feature_plan,
        output_dir=args.output_dir,
        thickness_mm=args.thickness_mm,
        chamfer_mm=args.chamfer_mm,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    return 0 if result.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
