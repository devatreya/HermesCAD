from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate that expected FreeCAD outputs exist.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory containing HermesCAD outputs.")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    expected_files = {
        "fcstd": output_dir / "hermescad_model.FCStd",
        "step": output_dir / "hermescad_model.step",
        "stl": output_dir / "hermescad_model.stl",
        "preview": output_dir / "preview.png",
    }
    result = {
        "output_dir": str(output_dir),
        "files": {name: path.exists() for name, path in expected_files.items()},
        "notes": [
            "This validation checks file presence only.",
            "It does not claim geometric correctness or manufacturing readiness.",
        ],
    }

    fcstd_path = expected_files["fcstd"]
    if fcstd_path.exists():
        try:  # pragma: no cover - depends on FreeCAD runtime
            import FreeCAD as App

            document = App.openDocument(str(fcstd_path))
            result["object_count"] = len(document.Objects)
        except Exception as exc:
            result["notes"].append(f"FreeCAD object inspection was unavailable: {exc}")

    print(json.dumps(result, indent=2))
    return 0 if expected_files["fcstd"].exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
