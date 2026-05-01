from pathlib import Path

import ezdxf

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


def test_annotated_sheet_border_is_excluded_from_part_geometry(tmp_path: Path) -> None:
    drawing_path = tmp_path / "annotated_sheet_border.dxf"
    document = ezdxf.new("R2010")
    modelspace = document.modelspace()

    modelspace.add_lwpolyline(
        [(0.0, 0.0), (200.0, 0.0), (200.0, 150.0), (0.0, 150.0)],
        close=True,
    )
    modelspace.add_circle((100.0, 75.0), 40.0)
    modelspace.add_circle((100.0, 75.0), 10.0)
    modelspace.add_text("BRAKE DISC DETAIL", dxfattribs={"height": 5.0}).set_placement((20.0, 135.0))
    document.saveas(drawing_path)

    summary = inspect_dxf_file(drawing_path, tmp_path)

    assert any(contour.role == "drawing_frame" for contour in summary.contours)
    assert len(summary.outer_profile_ids) == 1
    assert len(summary.hole_contour_ids) == 1
    outer_profile = next(contour for contour in summary.contours if contour.contour_id in summary.outer_profile_ids)
    assert outer_profile.is_circle
    assert any("drawing frame" in note.lower() for note in summary.notes)


def test_annotated_multi_view_geometry_warns_when_multiple_profiles_remain(tmp_path: Path) -> None:
    drawing_path = tmp_path / "annotated_multi_view.dxf"
    document = ezdxf.new("R2010")
    modelspace = document.modelspace()

    modelspace.add_lwpolyline(
        [(0.0, 0.0), (220.0, 0.0), (220.0, 160.0), (0.0, 160.0)],
        close=True,
    )
    modelspace.add_circle((60.0, 70.0), 30.0)
    modelspace.add_circle((160.0, 70.0), 20.0)
    modelspace.add_text("TWO SEPARATE VIEWS", dxfattribs={"height": 5.0}).set_placement((20.0, 145.0))
    document.saveas(drawing_path)

    summary = inspect_dxf_file(drawing_path, tmp_path)

    assert any(contour.role == "drawing_frame" for contour in summary.contours)
    assert len(summary.outer_profile_ids) == 2
    assert any("multiple disjoint top-level closed profiles" in warning.lower() for warning in summary.warnings)
