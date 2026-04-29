from pathlib import Path

from hermescad.inspection import inspect_dxf_file


def test_bracket_simple_dxf_is_inspected(tmp_path: Path) -> None:
    sample = Path("examples/drawings/bracket_simple.dxf")
    summary = inspect_dxf_file(sample, tmp_path)

    assert summary.entity_counts["CIRCLE"] == 4
    assert summary.bounding_box.width == 120.0
    assert summary.bounding_box.height == 80.0
    assert len(summary.hole_candidates) == 4
    assert (tmp_path / "geometry_summary.json").exists()

