from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import ConversionResult


def convert_dwg_to_dxf(input_path: Path, output_dir: Path) -> ConversionResult:
    input_path = input_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if input_path.suffix.lower() != ".dwg":
        return ConversionResult(
            attempted=False,
            available=False,
            converted=False,
            input_path=str(input_path),
            output_path=str(input_path),
            message="Input is not a DWG file; conversion was not needed.",
        )

    tool = shutil.which("dwg2dxf")
    if not tool:
        return ConversionResult(
            attempted=True,
            available=False,
            converted=False,
            input_path=str(input_path),
            message=(
                "LibreDWG `dwg2dxf` was not found. Install LibreDWG or provide DXF input "
                "for the MVP workflow."
            ),
        )

    output_path = output_dir / f"{input_path.stem}.dxf"
    commands = [
        [tool, "-o", str(output_path), str(input_path)],
        [tool, str(input_path), str(output_path)],
    ]

    last_stdout = ""
    last_stderr = ""
    for command in commands:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        last_stdout = completed.stdout.strip()
        last_stderr = completed.stderr.strip()
        if completed.returncode == 0 and output_path.exists():
            return ConversionResult(
                attempted=True,
                available=True,
                converted=True,
                input_path=str(input_path),
                output_path=str(output_path),
                command=" ".join(command),
                message="DWG converted to DXF with LibreDWG.",
                stdout=last_stdout or None,
                stderr=last_stderr or None,
            )

    return ConversionResult(
        attempted=True,
        available=True,
        converted=False,
        input_path=str(input_path),
        output_path=str(output_path) if output_path.exists() else None,
        command=" or ".join(" ".join(command) for command in commands),
        message=(
            "LibreDWG was found, but DWG to DXF conversion failed. Check the drawing and "
            "the installed `dwg2dxf` command."
        ),
        stdout=last_stdout or None,
        stderr=last_stderr or None,
    )

