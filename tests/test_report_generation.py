from pathlib import Path

from hermescad.models import FreeCADRunResult, OutputArtifact, ProcessResult
from hermescad.reporting import write_markdown_report


def test_markdown_report_includes_assumptions_and_warnings(tmp_path: Path) -> None:
    result = ProcessResult(
        job_id="job_test",
        job_dir=str(tmp_path),
        input_file="examples/drawings/bracket_simple.dxf",
        effective_input_file="examples/drawings/bracket_simple.dxf",
        instruction_text="Create a 10 mm thick 3D model and send a report.",
        package_path=str(tmp_path / "job_test_outputs.zip"),
        cad=FreeCADRunResult(
            attempted=False,
            available=False,
            succeeded=False,
            message="FreeCAD was unavailable for this test.",
        ),
        outputs=[OutputArtifact(path=str(tmp_path / "geometry_summary.json"))],
        assumptions=["Thickness interpreted as 10 mm."],
        warnings=["Generated outputs require engineering review."],
        metadata={
            "feature_operations": [
                {
                    "operation_id": "op_001",
                    "kind": "pocket_cut",
                    "target_kind": "cutouts",
                    "contour_ids": ["contour_001"],
                    "depth_mm": 4.0,
                    "parameters": {"selector": "top"},
                }
            ]
        },
    )

    report_path = write_markdown_report(result, None, tmp_path / "report.md")
    contents = report_path.read_text(encoding="utf-8")

    assert report_path.exists()
    assert "## Assumptions" in contents
    assert "## Feature Operations" in contents
    assert "## Warnings" in contents
    assert "engineering review" in contents.lower()
