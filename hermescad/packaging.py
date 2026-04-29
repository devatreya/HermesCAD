from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .models import OutputArtifact


def collect_output_artifacts(job_dir: Path) -> list[OutputArtifact]:
    job_dir = job_dir.resolve()
    artifacts: list[OutputArtifact] = []
    for path in sorted(job_dir.rglob("*")):
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() != ".zip":
            artifacts.append(OutputArtifact(path=str(path.resolve()), exists=True))
    return artifacts


def write_output_manifest(job_dir: Path, manifest_path: Path | None = None) -> Path:
    job_dir = job_dir.resolve()
    manifest_path = (manifest_path or job_dir / "outputs_manifest.json").resolve()
    manifest = {
        "job_dir": str(job_dir),
        "artifacts": [
            {
                "relative_path": str(path.relative_to(job_dir)),
                "size_bytes": path.stat().st_size,
            }
            for path in sorted(job_dir.rglob("*"))
            if path.is_file() and path.resolve() != manifest_path and not path.name.startswith(".")
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def package_job_outputs(job_dir: Path, output_dir: Path, job_id: str) -> Path:
    job_dir = job_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{job_id}_outputs.zip"

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(job_dir.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                archive.write(path, arcname=str(path.relative_to(job_dir)))

    return zip_path

