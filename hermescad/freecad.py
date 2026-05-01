from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .models import FreeCADRunResult
from .preview import execute_code_via_running_freecad, export_preview_via_running_freecad, freecad_rpc_url


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


def _update_preview_metadata(result_path: Path, preview_path: Path, preview_message: str) -> None:
    if not preview_path.exists() or not result_path.exists():
        return

    try:
        result_payload = json.loads(result_path.read_text(encoding="utf-8"))
        result_payload["preview_status"] = preview_message
        outputs = list(result_payload.get("outputs", []))
        preview_resolved = str(preview_path.resolve())
        if preview_resolved not in outputs:
            outputs.append(preview_resolved)
        result_payload["outputs"] = outputs
        result_path.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def _build_run_script_rpc_code(script_path: Path, config_path: Path) -> str:
    return f"""
import os
import runpy
import sys

script_path = {json.dumps(str(script_path.resolve()))}
config_path = {json.dumps(str(config_path.resolve()))}
previous_argv = list(sys.argv)
previous_config = os.environ.get("HERMESCAD_FREECAD_CONFIG")

try:
    os.environ["HERMESCAD_FREECAD_CONFIG"] = config_path
    sys.argv = [script_path, "--config", config_path]
    try:
        runpy.run_path(script_path, run_name="__main__")
    except SystemExit as exc:
        exit_code = exc.code
        if exit_code not in (None, 0):
            raise RuntimeError(f"HermesCAD FreeCAD script exited with code {{exit_code!r}}")
finally:
    sys.argv = previous_argv
    if previous_config is None:
        os.environ.pop("HERMESCAD_FREECAD_CONFIG", None)
    else:
        os.environ["HERMESCAD_FREECAD_CONFIG"] = previous_config
"""


def _wait_for_output_files(
    paths: list[Path],
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 0.5,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if all(path.exists() for path in paths):
            return True
        time.sleep(poll_interval_seconds)
    return all(path.exists() for path in paths)


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
                _update_preview_metadata(output_dir / "freecad_result.json", preview_path, preview_result.message)

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
    script_path = repository_root() / "freecad_scripts" / "create_assembly_from_parts.py"
    config_path = output_dir.resolve() / "freecad_assembly_input.json"
    config_path.write_text(json.dumps(assembly_config, indent=2), encoding="utf-8")

    def _success_result(command_text: str, stdout_text: str | None, stderr_text: str | None) -> FreeCADRunResult:
        preview_path = output_dir / "preview.png"
        preview_result = None
        if not preview_path.exists():
            preview_result = export_preview_via_running_freecad(
                fcstd_path=output_dir / "hermescad_assembly.FCStd",
                output_path=preview_path,
                focus_object=None,
            )
            _update_preview_metadata(output_dir / "assembly_result.json", preview_path, preview_result.message)

        expected_outputs = [
            output_dir / "hermescad_assembly.FCStd",
            output_dir / "hermescad_assembly.step",
            output_dir / "hermescad_assembly.stl",
        ]
        missing_outputs = [str(path.name) for path in expected_outputs if not path.exists()]
        if missing_outputs:
            raise RuntimeError(
                "FreeCAD returned success, but expected assembly outputs were missing: "
                + ", ".join(missing_outputs)
            )

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
            command=command_text,
            message=message,
            generated_files=generated_files,
            stdout=stdout_text or None,
            stderr=stderr_text or None,
        )

    last_stdout = ""
    last_stderr = ""
    last_message = "FreeCAD assembly execution failed."
    rpc_code = _build_run_script_rpc_code(script_path, config_path)
    rpc_execution = execute_code_via_running_freecad(rpc_code, rpc_url=freecad_rpc_url())
    if rpc_execution.succeeded:
        rpc_expected_outputs = [
            output_dir / "hermescad_assembly.FCStd",
            output_dir / "hermescad_assembly.step",
            output_dir / "hermescad_assembly.stl",
            output_dir / "assembly_result.json",
        ]
        if not _wait_for_output_files(rpc_expected_outputs, timeout_seconds=90.0):
            last_message = (
                "Live FreeCAD RPC assembly execution was scheduled, but the expected output files were not ready "
                "before the timeout. HermesCAD will fall back to `freecadcmd`."
            )
            last_stdout = rpc_execution.message
            last_stderr = last_message
        else:
            try:
                return _success_result(
                    command_text=f"{freecad_rpc_url()} execute_code {script_path.name}",
                    stdout_text=rpc_execution.message,
                    stderr_text=None,
                )
            except Exception as exc:
                last_message = str(exc)
                last_stdout = rpc_execution.message
    elif rpc_execution.attempted:
        last_message = (
            "Live FreeCAD RPC assembly execution failed, so HermesCAD will fall back to `freecadcmd`. "
            + rpc_execution.message
        )
        last_stderr = rpc_execution.message

    command = detect_freecad_command()
    if not command:
        unavailable_message = (
            "FreeCAD was not found on PATH and the FreeCAD GUI RPC server was unavailable. "
            "Install FreeCAD and set `FREECAD_CMD` if needed before running the HermesCAD assembly workflow."
        )
        return FreeCADRunResult(
            attempted=True,
            available=False,
            succeeded=False,
            message=last_message if rpc_execution.attempted else unavailable_message,
            stdout=last_stdout or None,
            stderr=last_stderr or None,
        )

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
            try:
                result = _success_result(" ".join(invocation), last_stdout, last_stderr)
            except Exception as exc:
                last_message = str(exc)
                continue
            if rpc_execution.attempted and not rpc_execution.succeeded:
                result.message = (
                    "Live FreeCAD RPC assembly execution failed, so HermesCAD used the `freecadcmd` fallback. "
                    + result.message
                )
                if rpc_execution.message:
                    result.stderr = (
                        f"{rpc_execution.message}\n{result.stderr}" if result.stderr else rpc_execution.message
                    )
            return result

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
