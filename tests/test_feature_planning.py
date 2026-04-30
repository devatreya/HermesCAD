from pathlib import Path

from hermescad.inspection import inspect_dxf_file
from hermescad.planning import build_feature_plan


def test_mount_plate_feature_plan_supports_pockets_and_blind_holes(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/mount_plate_complex.dxf"), tmp_path)
    plan = build_feature_plan(
        "Create a 12 mm thick 3D model. Make the internal window and slot 4 mm deep pockets. Make all holes 6 mm deep. Add 1 mm chamfers.",
        summary,
        thickness_mm=12.0,
        chamfer_mm=1.0,
    )

    assert len(plan.operations) == 3
    assert plan.operations[0].kind == "blind_hole"
    assert plan.operations[0].depth_mm == 6.0
    assert plan.operations[1].target_kind == "slots"
    assert plan.operations[1].kind == "pocket_cut"
    assert plan.operations[1].depth_mm == 4.0
    assert plan.operations[2].target_kind == "cutouts"
    assert plan.operations[2].kind == "pocket_cut"
    assert plan.operations[2].depth_mm == 4.0


def test_default_feature_plan_keeps_through_cut_behavior(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/dogbone_link_complex.dxf"), tmp_path)
    plan = build_feature_plan(
        "Create a 10 mm thick 3D model. Cut all circular holes and internal cutouts through. Add 0.75 mm chamfers.",
        summary,
        thickness_mm=10.0,
        chamfer_mm=0.75,
    )

    assert len(plan.operations) == 2
    assert all(operation.kind == "through_cut" for operation in plan.operations)
    assert all(operation.depth_mm == 10.0 for operation in plan.operations)


def test_nested_pocket_plan_can_target_slot_inside_pocket_hierarchy(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/nested_pocket_island_complex.dxf"), tmp_path)
    plan = build_feature_plan(
        "Create a 14 mm thick 3D model. Make the large pocket 5 mm deep, make the slot 9 mm deep, and cut all holes through.",
        summary,
        thickness_mm=14.0,
        chamfer_mm=None,
    )

    slot_operation = next(operation for operation in plan.operations if operation.target_kind == "slots")
    cutout_operation = next(operation for operation in plan.operations if operation.target_kind == "cutouts")

    assert slot_operation.kind == "pocket_cut"
    assert slot_operation.depth_mm == 9.0
    assert len(slot_operation.contour_ids) == 1
    assert cutout_operation.kind == "pocket_cut"
    assert cutout_operation.depth_mm == 5.0


def test_mount_plate_feature_plan_supports_counterbores(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/mount_plate_complex.dxf"), tmp_path)
    plan = build_feature_plan(
        "Create a 12 mm thick 3D model. Cut all holes through. Add 12 mm diameter counterbores 4 mm deep to all holes.",
        summary,
        thickness_mm=12.0,
        chamfer_mm=None,
    )

    counterbore = next(operation for operation in plan.operations if operation.kind == "counterbore_hole")
    assert counterbore.depth_mm == 4.0
    assert counterbore.parameters["major_diameter_mm"] == 12.0


def test_mount_plate_feature_plan_supports_countersinks(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/mount_plate_complex.dxf"), tmp_path)
    plan = build_feature_plan(
        "Create a 12 mm thick 3D model. Cut all holes through. Add 90 degree countersinks with 12 mm major diameter to all holes.",
        summary,
        thickness_mm=12.0,
        chamfer_mm=None,
    )

    countersink = next(operation for operation in plan.operations if operation.kind == "countersink_hole")
    assert countersink.parameters["major_diameter_mm"] == 12.0
    assert countersink.parameters["included_angle_deg"] == 90.0
    assert countersink.depth_mm > 0.0


def test_mount_plate_feature_plan_supports_corner_socket_head_screw_holes(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/mount_plate_complex.dxf"), tmp_path)
    plan = build_feature_plan(
        "Create a 12 mm thick 3D model. Make the corner holes M8 socket head screw holes. Cut the slot and window through.",
        summary,
        thickness_mm=12.0,
        chamfer_mm=None,
    )

    clearance = next(operation for operation in plan.operations if operation.kind == "clearance_hole")
    counterbore = next(operation for operation in plan.operations if operation.kind == "counterbore_hole")

    assert len(clearance.contour_ids) == 4
    assert len(counterbore.contour_ids) == 4
    assert clearance.parameters["major_diameter_mm"] == 9.0
    assert counterbore.parameters["major_diameter_mm"] == 13.0
    assert counterbore.depth_mm == 8.0
    assert counterbore.parameters["selector"] == "corner"


def test_mount_plate_feature_plan_supports_center_countersunk_screw_hole(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/mount_plate_complex.dxf"), tmp_path)
    plan = build_feature_plan(
        "Create a 12 mm thick 3D model. Make the center hole an M5 countersunk screw hole. Cut all cutouts through.",
        summary,
        thickness_mm=12.0,
        chamfer_mm=None,
    )

    clearance = next(
        operation
        for operation in plan.operations
        if operation.kind == "clearance_hole" and operation.parameters.get("selector") == "center"
    )
    countersink = next(
        operation
        for operation in plan.operations
        if operation.kind == "countersink_hole" and operation.parameters.get("selector") == "center"
    )

    assert len(clearance.contour_ids) == 1
    assert clearance.parameters["major_diameter_mm"] == 5.5
    assert len(countersink.contour_ids) == 1
    assert countersink.parameters["major_diameter_mm"] == 10.0
    assert countersink.parameters["pilot_diameter_mm"] == 9.0
    assert any("already larger than the requested M5 clearance diameter" in warning for warning in plan.warnings)


def test_mount_plate_feature_plan_supports_targeted_blind_hole_groups(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/mount_plate_complex.dxf"), tmp_path)
    plan = build_feature_plan(
        "Create a 12 mm thick 3D model. Make the corner holes 6 mm deep. Make the center hole through. Cut the slot and window through.",
        summary,
        thickness_mm=12.0,
        chamfer_mm=None,
    )

    corner_holes = next(
        operation
        for operation in plan.operations
        if operation.target_kind == "holes" and operation.kind == "blind_hole"
    )
    center_hole = next(
        operation
        for operation in plan.operations
        if operation.target_kind == "holes" and operation.kind == "through_cut"
    )

    assert len(corner_holes.contour_ids) == 4
    assert corner_holes.depth_mm == 6.0
    assert corner_holes.parameters["selector"] == "corner"
    assert center_hole.contour_ids == ["contour_005"]
    assert center_hole.parameters["selector"] == "center"


def test_blind_hole_targets_block_overlapping_screw_presets(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/mount_plate_complex.dxf"), tmp_path)
    plan = build_feature_plan(
        "Create a 12 mm thick 3D model. Make the center hole 8 mm deep. Make the center hole an M8 countersunk screw hole. Cut all cutouts through.",
        summary,
        thickness_mm=12.0,
        chamfer_mm=None,
    )

    assert any(
        operation.kind == "blind_hole"
        and operation.target_kind == "holes"
        and operation.parameters.get("selector") == "center"
        for operation in plan.operations
    )
    assert not any(
        operation.kind == "countersink_hole" and operation.parameters.get("selector") == "center"
        for operation in plan.operations
    )
    assert any("skipped the screw-hole preset" in warning for warning in plan.warnings)


def test_actuator_plate_feature_plan_supports_targeted_regions_and_boss(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/actuator_plate_advanced.dxf"), tmp_path)
    plan = build_feature_plan(
        (
            "Create a 16 mm thick 3D model. "
            "Make the largest pocket 6 mm deep. "
            "Make the right window through. "
            "Make the top window 4 mm deep. "
            "Make the bottom slot 8 mm deep. "
            "Make the top slot through. "
            "Raise the center island by 3 mm. "
            "Make the corner holes M6 socket head screw holes. "
            "Make the center hole an M8 countersunk screw hole."
        ),
        summary,
        thickness_mm=16.0,
        chamfer_mm=None,
    )

    by_kind = {}
    for operation in plan.operations:
        by_kind.setdefault(operation.kind, []).append(operation)

    assert any(op.kind == "boss_add" and op.depth_mm == 3.0 and len(op.contour_ids) == 1 for op in plan.operations)
    assert any(
        op.target_kind == "cutouts" and op.kind == "pocket_cut" and op.depth_mm == 6.0 and op.parameters.get("selector") == "largest"
        for op in plan.operations
    )
    assert any(
        op.target_kind == "cutouts" and op.kind == "through_cut" and op.depth_mm == 16.0 and op.parameters.get("selector") == "right"
        for op in plan.operations
    )
    assert any(
        op.target_kind == "cutouts" and op.kind == "pocket_cut" and op.depth_mm == 4.0 and op.parameters.get("selector") == "top"
        for op in plan.operations
    )
    assert any(
        op.target_kind == "slots" and op.kind == "pocket_cut" and op.depth_mm == 8.0 and op.parameters.get("selector") == "bottom"
        for op in plan.operations
    )
    assert any(
        op.target_kind == "slots" and op.kind == "through_cut" and op.depth_mm == 16.0 and op.parameters.get("selector") == "top"
        for op in plan.operations
    )
    assert any(op.kind == "counterbore_hole" and op.parameters.get("selector") == "corner" for op in by_kind.get("counterbore_hole", []))
    assert any(op.kind == "countersink_hole" and op.parameters.get("selector") == "center" for op in by_kind.get("countersink_hole", []))


def test_threaded_base_plate_supports_targeted_threaded_holes(tmp_path: Path) -> None:
    summary = inspect_dxf_file(Path("examples/drawings/assembly_base_plate_threaded.dxf"), tmp_path)
    plan = build_feature_plan(
        (
            "Create a 12 mm thick 3D model. "
            "Make the corner holes M6 threaded 10 mm deep. "
            "Make the largest pocket 4 mm deep. "
            "Raise the center island by 2 mm."
        ),
        summary,
        thickness_mm=12.0,
        chamfer_mm=None,
    )

    threaded_holes = next(operation for operation in plan.operations if operation.kind == "threaded_hole")
    pocket = next(operation for operation in plan.operations if operation.target_kind == "cutouts")
    boss = next(operation for operation in plan.operations if operation.kind == "boss_add")

    assert len(threaded_holes.contour_ids) == 4
    assert threaded_holes.depth_mm == 10.0
    assert threaded_holes.parameters["major_diameter_mm"] == 6.0
    assert threaded_holes.parameters["tap_drill_mm"] == 5.0
    assert threaded_holes.parameters["thread_pitch_mm"] == 1.0
    assert pocket.kind == "pocket_cut"
    assert pocket.depth_mm == 4.0
    assert boss.depth_mm == 2.0
