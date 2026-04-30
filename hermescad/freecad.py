from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .models import FreeCADRunResult
from .preview import export_preview_via_running_freecad


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def detect_freecad_command() -> str | None:
    configured = os.environ.get("FREECAD_CMD")
    if configured:
        return configured

    macos_bundle_candidates = [
        Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"),
        Path.home() / "Applications" / "FreeCAD.app" / "Contents" / "Resources" / "bin" / "freecadcmd",
    ]
    for candidate in macos_bundle_candidates:
        if candidate.exists():
            return str(candidate)

    candidates = ["freecadcmd", "FreeCADCmd", "FreeCAD", "freecad"]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _candidate_invocations(command: str, script_path: Path) -> list[list[str]]:
    command_name = Path(command).name.lower()
    if "cmd" in command_name:
        return [[command, str(script_path)]]
    return [
        [command, "-c", str(script_path)],
        [command, "--console", str(script_path)],
        [command, str(script_path)],
    ]


def run_freecad_generation(
    dxf_path: Path,
    geometry_summary_path: Path,
    feature_plan_path: Path,
    output_dir: Path,
    thickness_mm: float,
    chamfer_mm: float | None = None,
) -> FreeCADRunResult:
    command = detect_freecad_command()
    if not command:
        return FreeCADRunResult(
            attempted=True,
            available=False,
            succeeded=False,
            message=(
                "FreeCAD was not found on PATH. Install FreeCAD and set `FREECAD_CMD` if needed, "
                "or use the DXF inspection/report fallback workflow."
            ),
        )

    script_path = repository_root() / "freecad_scripts" / "create_plate_from_dxf.py"
    config_path = output_dir.resolve() / "freecad_job_input.json"
    config_payload = {
        "dxf": str(dxf_path.resolve()),
        "geometry_summary": str(geometry_summary_path.resolve()),
        "feature_plan": str(feature_plan_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "thickness_mm": thickness_mm,
        "chamfer_mm": chamfer_mm if chamfer_mm is not None else 0.0,
    }
    config_path.write_text(json.dumps(config_payload, indent=2), encoding="utf-8")

    last_stdout = ""
    last_stderr = ""
    last_message = "FreeCAD execution failed."
    for invocation in _candidate_invocations(command, script_path):
        environment = os.environ.copy()
        environment["HERMESCAD_FREECAD_CONFIG"] = str(config_path)
        completed = subprocess.run(
            invocation,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            env=environment,
        )
        last_stdout = completed.stdout.strip()
        last_stderr = completed.stderr.strip()

        if completed.returncode == 0:
            preview_path = output_dir / "preview.png"
            preview_result = None
            if not preview_path.exists():
                preview_result = export_preview_via_running_freecad(
                    fcstd_path=output_dir / "hermescad_model.FCStd",
                    output_path=preview_path,
                )
                result_path = output_dir / "freecad_result.json"
                if preview_path.exists() and result_path.exists():
                    try:
                        result_payload = json.loads(result_path.read_text(encoding="utf-8"))
                        result_payload["preview_status"] = preview_result.message
                        outputs = list(result_payload.get("outputs", []))
                        preview_resolved = str(preview_path.resolve())
                        if preview_resolved not in outputs:
                            outputs.append(preview_resolved)
                        result_payload["outputs"] = outputs
                        result_path.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
                    except Exception:
                        pass

            expected_outputs = [
                output_dir / "hermescad_model.FCStd",
                output_dir / "hermescad_model.step",
                output_dir / "hermescad_model.stl",
            ]
            generated_files = sorted(
                str(path.resolve())
                for path in output_dir.iterdir()
                if path.is_file() and path.suffix.lower() in {".fcstd", ".step", ".stl", ".png", ".md", ".json"}
            )
            missing_outputs = [str(path.name) for path in expected_outputs if not path.exists()]
            if missing_outputs:
                last_message = (
                    "FreeCAD returned success, but expected CAD outputs were missing: "
                    + ", ".join(missing_outputs)
                )
                continue
            message = "FreeCAD completed the MVP model generation workflow."
            if preview_result is not None:
                message = f"{message} {preview_result.message}"
            return FreeCADRunResult(
                attempted=True,
                available=True,
                succeeded=True,
                command=" ".join(invocation),
                message=message,
                generated_files=generated_files,
                stdout=last_stdout or None,
                stderr=last_stderr or None,
            )

        last_message = (
            f"FreeCAD command exited with code {completed.returncode}. "
            "See stdout/stderr in the job summary for details."
        )

    return FreeCADRunResult(
        attempted=True,
        available=True,
        succeeded=False,
        command=command,
        message=last_message,
        stdout=last_stdout or None,
        stderr=last_stderr or None,
    )


def run_freecad_assembly(
    assembly_config: dict[str, object],
    output_dir: Path,
) -> FreeCADRunResult:
    command = detect_freecad_command()
    if not command:
        return FreeCADRunResult(
            attempted=True,
            available=False,
            succeeded=False,
            message=(
                "FreeCAD was not found on PATH. Install FreeCAD and set `FREECAD_CMD` if needed "
                "before running the HermesCAD assembly workflow."
            ),
        )

    script_path = repository_root() / "freecad_scripts" / "create_assembly_from_parts.py"
    config_path = output_dir.resolve() / "freecad_assembly_input.json"
    config_path.write_text(json.dumps(assembly_config, indent=2), encoding="utf-8")

    last_stdout = ""
    last_stderr = ""
    last_message = "FreeCAD assembly execution failed."
    for invocation in _candidate_invocations(command, script_path):
        environment = os.environ.copy()
        environment["HERMESCAD_FREECAD_CONFIG"] = str(config_path)
        completed = subprocess.run(
            invocation,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            env=environment,
        )
        last_stdout = completed.stdout.strip()
        last_stderr = completed.stderr.strip()
        if completed.returncode == 0:
            preview_path = output_dir / "preview.png"
            preview_result = None
            if not preview_path.exists():
                preview_result = export_preview_via_running_freecad(
                    fcstd_path=output_dir / "hermescad_assembly.FCStd",
                    output_path=preview_path,
                )

            expected_outputs = [
                output_dir / "hermescad_assembly.FCStd",
                output_dir / "hermescad_assembly.step",
                output_dir / "hermescad_assembly.stl",
            ]
            missing_outputs = [str(path.name) for path in expected_outputs if not path.exists()]
            if missing_outputs:
                last_message = (
                    "FreeCAD returned success, but expected assembly outputs were missing: "
                    + ", ".join(missing_outputs)
                )
                continue

            generated_files = sorted(
                str(path.resolve())
                for path in output_dir.iterdir()
                if path.is_file() and path.suffix.lower() in {".fcstd", ".step", ".stl", ".png", ".md", ".json"}
            )
            message = "FreeCAD completed the HermesCAD assembly workflow."
            if preview_result is not None:
                message = f"{message} {preview_result.message}"
            return FreeCADRunResult(
                attempted=True,
                available=True,
                succeeded=True,
                command=" ".join(invocation),
                message=message,
                generated_files=generated_files,
                stdout=last_stdout or None,
                stderr=last_stderr or None,
            )

        last_message = (
            f"FreeCAD assembly command exited with code {completed.returncode}. "
            "See stdout/stderr in the assembly summary for details."
        )

    return FreeCADRunResult(
        attempted=True,
        available=True,
        succeeded=False,
        command=command,
        message=last_message,
        stdout=last_stdout or None,
        stderr=last_stderr or None,
    )
