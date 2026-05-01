from __future__ import annotations

from pathlib import Path

from hermescad.assembly import load_assembly_manifest, process_assembly_manifest
from hermescad.inspection import inspect_dxf_file
from hermescad.models import FreeCADRunResult, ProcessResult


def test_load_assembly_manifest_reads_part_placements() -> None:
    manifest = load_assembly_manifest(Path("examples/assemblies/threaded_cover_stack/assembly_manifest.json"))

    assert manifest.assembly_name == "threaded_cover_stack"
    assert len(manifest.parts) == 2
    assert len(manifest.fasteners) == 1
    assert manifest.parts[0].name == "base_plate"
    assert manifest.parts[1].placement.z_mm == 12.0
    assert manifest.fasteners[0].source_part == "cover_plate"


def test_process_assembly_manifest_creates_single_root_package(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manifest_path = Path("examples/assemblies/threaded_cover_stack/assembly_manifest.json")
    outputs_dir = tmp_path / "outputs"
    job_dir = tmp_path / "jobs" / "assembly_job"

    def fake_process_cad_request(input_file, instruction_text, job_dir, outputs_dir, *, package_outputs):
        job_dir.mkdir(parents=True, exist_ok=True)
        assert package_outputs is False
        (job_dir / "hermescad_model.FCStd").write_text("fcstd", encoding="utf-8")
        (job_dir / "hermescad_model.step").write_text("step", encoding="utf-8")
        (job_dir / "hermescad_model.stl").write_text("stl", encoding="utf-8")
        (job_dir / "report.md").write_text("part report", encoding="utf-8")
        geometry_summary = inspect_dxf_file(Path(input_file), job_dir)
        return ProcessResult(
            job_id=job_dir.name,
            job_dir=str(job_dir),
            input_file=str(input_file),
            effective_input_file=str(input_file),
            instruction_text=instruction_text,
            geometry_summary_path=geometry_summary.geometry_summary_path,
            report_path=str((job_dir / "report.md").resolve()),
            cad=FreeCADRunResult(
                attempted=True,
                available=True,
                succeeded=True,
                message="fake part success",
            ),
        )

    def fake_run_freecad_assembly(assembly_config, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        assert len(assembly_config["fasteners"]) == 1
        assert assembly_config["fasteners"][0]["source_part"] == "cover_plate"
        assert len(assembly_config["fasteners"][0]["hole_centers_local_mm"]) == 4
        (output_dir / "hermescad_assembly.FCStd").write_text("assembly fcstd", encoding="utf-8")
        (output_dir / "hermescad_assembly.step").write_text("assembly step", encoding="utf-8")
        (output_dir / "hermescad_assembly.stl").write_text("assembly stl", encoding="utf-8")
        (output_dir / "preview.png").write_text("preview", encoding="utf-8")
        (output_dir / "assembly_result.json").write_text(
            '{"fasteners":[{"name":"corner_cap_screws","inserted_count":4}],"fastener_warnings":[]}',
            encoding="utf-8",
        )
        return FreeCADRunResult(
            attempted=True,
            available=True,
            succeeded=True,
            message="fake assembly success",
        )

    monkeypatch.setattr("hermescad.assembly.process_cad_request", fake_process_cad_request)
    monkeypatch.setattr("hermescad.assembly.run_freecad_assembly", fake_run_freecad_assembly)

    result = process_assembly_manifest(
        manifest_path=manifest_path,
        job_dir=job_dir,
        outputs_dir=outputs_dir,
    )

    assert result.cad.succeeded is True
    assert len(result.part_results) == 2
    assert result.package_path is not None
    assert Path(result.package_path).exists()
    assert list(outputs_dir.glob("*.zip")) == [Path(result.package_path)]
