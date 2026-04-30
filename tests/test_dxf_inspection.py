from pathlib import Path

from hermescad.inspection import inspect_dxf_file


def test_bracket_simple_dxf_is_inspected(tmp_path: Path) -> None:
    sample = Path("examples/drawings/bracket_simple.dxf")
    summary = inspect_dxf_file(sample, tmp_path)

    assert summary.entity_counts["CIRCLE"] == 4
    assert summary.bounding_box.width == 120.0
    assert summary.bounding_box.height == 80.0
    assert len(summary.hole_candidates) == 4
    assert summary.closed_contour_count == 5
    assert summary.open_chain_count == 0
    assert len(summary.outer_profile_ids) == 1
    assert len(summary.hole_contour_ids) == 4
    assert (tmp_path / "geometry_summary.json").exists()


def test_mount_plate_complex_classifies_cutouts_and_slot(tmp_path: Path) -> None:
    sample = Path("examples/drawings/mount_plate_complex.dxf")
    summary = inspect_dxf_file(sample, tmp_path)

    assert summary.closed_contour_count == 8
    assert summary.open_chain_count == 0
    assert len(summary.outer_profile_ids) == 1
    assert len(summary.cutout_ids) == 2
    assert len(summary.hole_contour_ids) == 5
    assert len(summary.slot_candidate_ids) == 1


def test_dogbone_link_complex_has_outer_profile_holes_and_slot(tmp_path: Path) -> None:
    sample = Path("examples/drawings/dogbone_link_complex.dxf")
    summary = inspect_dxf_file(sample, tmp_path)

    assert summary.closed_contour_count == 4
    assert summary.open_chain_count == 0
    assert len(summary.outer_profile_ids) == 1
    assert len(summary.cutout_ids) == 1
    assert len(summary.hole_contour_ids) == 2
    assert len(summary.slot_candidate_ids) >= 1


def test_nested_pocket_island_complex_tracks_islands_and_deep_holes(tmp_path: Path) -> None:
    sample = Path("examples/drawings/nested_pocket_island_complex.dxf")
    summary = inspect_dxf_file(sample, tmp_path)

    assert len(summary.outer_profile_ids) == 1
    assert len(summary.cutout_ids) == 1
    assert len(summary.island_ids) == 2
    assert len(summary.hole_contour_ids) == 5
    assert len(summary.slot_candidate_ids) == 1


def test_actuator_plate_advanced_tracks_multiple_regions_and_slots(tmp_path: Path) -> None:
    sample = Path("examples/drawings/actuator_plate_advanced.dxf")
    summary = inspect_dxf_file(sample, tmp_path)

    assert summary.bounding_box.width == 220.0
    assert summary.bounding_box.height == 160.0
    assert len(summary.outer_profile_ids) == 1
    assert len(summary.cutout_ids) == 5
    assert len(summary.island_ids) == 1
    assert len(summary.hole_contour_ids) == 5
    assert len(summary.slot_candidate_ids) == 2
