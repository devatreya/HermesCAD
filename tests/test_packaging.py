from pathlib import Path
from zipfile import ZipFile

from hermescad.packaging import package_job_outputs


def test_package_outputs_creates_zip(tmp_path: Path) -> None:
    job_dir = tmp_path / "job_001"
    output_dir = tmp_path / "outputs"
    job_dir.mkdir()
    output_dir.mkdir()

    (job_dir / "geometry_summary.json").write_text("{}", encoding="utf-8")
    (job_dir / "report.md").write_text("# Report\n", encoding="utf-8")

    zip_path = package_job_outputs(job_dir, output_dir, "job_001")

    assert zip_path.exists()
    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "geometry_summary.json" in names
    assert "report.md" in names
