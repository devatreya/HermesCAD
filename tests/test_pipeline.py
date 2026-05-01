from hermescad.pipeline import _extract_extrusion_depth_mm


def test_extract_extrusion_depth_from_profile_length_language() -> None:
    instruction = (
        "Create a 100 mm long 3D profile extrusion from this 2D section. "
        "Use millimetres and return STEP, STL, FCStd, preview, and a report."
    )

    assert _extract_extrusion_depth_mm(instruction) == 100.0


def test_extract_extrusion_depth_from_direct_extrude_language() -> None:
    instruction = "Extrude the section to 85 mm and return the 3D model."

    assert _extract_extrusion_depth_mm(instruction) == 85.0


def test_extract_extrusion_depth_prefers_explicit_thickness_when_present() -> None:
    instruction = (
        "Create a 12 mm thick 3D model from this section and use M6 x 20 mm screws later in the assembly."
    )

    assert _extract_extrusion_depth_mm(instruction) == 12.0
