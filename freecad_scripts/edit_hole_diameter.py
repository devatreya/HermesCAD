from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Starter placeholder for a future FreeCAD workflow that resizes circular holes."
    )
    parser.add_argument("--fcstd", required=True, help="Existing FreeCAD model file.")
    parser.add_argument("--from-diameter", type=float, required=True, help="Current hole diameter in mm.")
    parser.add_argument("--to-diameter", type=float, required=True, help="Target hole diameter in mm.")
    args = parser.parse_args()

    print(
        "This starter script is reserved for a future workflow: resize all circular holes "
        f"from {args.from_diameter:g} mm to {args.to_diameter:g} mm in `{args.fcstd}`."
    )
    print("For the hackathon MVP, this path is documented but not fully implemented.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

