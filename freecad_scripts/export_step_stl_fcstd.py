from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export STEP and STL from an existing FreeCAD document.")
    parser.add_argument("--fcstd", type=Path, required=True, help="Input FCStd file.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for exported files.")
    parser.add_argument("--object-name", type=str, help="Optional FreeCAD object name to export.")
    args = parser.parse_args()

    try:  # pragma: no cover - depends on FreeCAD runtime
        import FreeCAD as App
        import Import
        import Mesh
    except Exception as exc:  # pragma: no cover - depends on FreeCAD runtime
        print(f"FreeCAD modules are unavailable: {exc}")
        return 1

    try:  # pragma: no cover - depends on FreeCAD runtime
        document = App.openDocument(str(args.fcstd.resolve()))
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        if args.object_name:
            objects = [document.getObject(args.object_name)]
        else:
            objects = [obj for obj in document.Objects if hasattr(obj, "Shape")]
        objects = [obj for obj in objects if obj is not None]
        if not objects:
            print("No exportable objects were found in the FreeCAD document.")
            return 1

        step_path = output_dir / f"{args.fcstd.stem}.step"
        stl_path = output_dir / f"{args.fcstd.stem}.stl"
        Import.export(objects, str(step_path))
        Mesh.export(objects, str(stl_path))
        print(f"Exported {step_path}")
        print(f"Exported {stl_path}")
        return 0
    except Exception as exc:
        print(f"FreeCAD export failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

