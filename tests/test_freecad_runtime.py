from __future__ import annotations

import json
from pathlib import Path

from hermescad import freecad
from hermescad.preview import FreeCADRpcExecutionResult


def test_run_freecad_assembly_prefers_live_rpc(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "job"
    output_dir.mkdir(parents=True, exist_ok=True)

    def fake_execute_code(code: str, rpc_url: str | None = None) -> FreeCADRpcExecutionResult:
        assert "create_assembly_from_parts.py" in code
        assert "HERMESCAD_FREECAD_CONFIG" in code
        (output_dir / "hermescad_assembly.FCStd").write_text("fcstd", encoding="utf-8")
        (output_dir / "hermescad_assembly.step").write_text("step", encoding="utf-8")
        (output_dir / "hermescad_assembly.stl").write_text("stl", encoding="utf-8")
        (output_dir / "preview.png").write_text("preview", encoding="utf-8")
        (output_dir / "assembly_result.json").write_text(
            json.dumps(
                {
                    "outputs": [
                        str((output_dir / "hermescad_assembly.FCStd").resolve()),
                        str((output_dir / "hermescad_assembly.step").resolve()),
                        str((output_dir / "hermescad_assembly.stl").resolve()),
                    ],
                    "preview_status": "Preview exported to preview.png.",
                }
            ),
            encoding="utf-8",
        )
        return FreeCADRpcExecutionResult(
            attempted=True,
            succeeded=True,
            message="Python code execution scheduled. Output: assembly created.",
        )

    monkeypatch.setattr(freecad, "execute_code_via_running_freecad", fake_execute_code)
    monkeypatch.setattr(freecad, "freecad_rpc_url", lambda: "http://127.0.0.1:9875")
    monkeypatch.setattr(freecad, "detect_freecad_command", lambda: None)

    result = freecad.run_freecad_assembly(
        assembly_config={
            "assembly_name": "rpc_preferred",
            "output_dir": str(output_dir.resolve()),
            "parts": [],
            "fasteners": [],
        },
        output_dir=output_dir,
    )

    assert result.succeeded is True
    assert result.command == "http://127.0.0.1:9875 execute_code create_assembly_from_parts.py"
    assert "HermesCAD assembly workflow" in result.message
    assert (output_dir / "freecad_assembly_input.json").exists()
