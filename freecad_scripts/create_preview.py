from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Attempt to create a PNG preview from a FreeCAD model.")
    parser.add_argument("--fcstd", type=Path, required=True, help="Input FCStd file.")
    parser.add_argument("--output", type=Path, required=True, help="Output PNG path.")
    args = parser.parse_args()

    try:  # pragma: no cover - depends on FreeCAD runtime
        import FreeCAD as App
        import FreeCADGui as Gui
    except Exception as exc:  # pragma: no cover - depends on FreeCAD runtime
        print(
            "FreeCAD GUI modules are unavailable, so a preview cannot be generated in this environment: "
            f"{exc}"
        )
        return 1

    try:  # pragma: no cover - depends on FreeCAD runtime
        App.openDocument(str(args.fcstd.resolve()))
        active_document = Gui.activeDocument()
        if active_document is None:
            print("FreeCAD did not provide an active GUI document, so preview export was skipped.")
            return 1
        view = active_document.activeView()
        view.viewAxonometric()
        Gui.SendMsgToActiveView("ViewFit")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        view.saveImage(str(args.output.resolve()), 1600, 1200, "White")
        print(f"Preview exported to {args.output.resolve()}")
        return 0
    except Exception as exc:
        print(f"FreeCAD preview export failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

