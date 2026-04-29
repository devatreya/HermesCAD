from pathlib import Path

from hermescad import preview


def test_preview_export_succeeds_when_rpc_writes_image(tmp_path: Path, monkeypatch) -> None:
    fcstd_path = tmp_path / "model.FCStd"
    output_path = tmp_path / "preview.png"
    fcstd_path.write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(preview, "_rpc_endpoint_is_reachable", lambda rpc_url: True)

    class FakeServerProxy:
        def __init__(self, rpc_url: str, allow_none: bool = True) -> None:
            self.rpc_url = rpc_url

        def execute_code(self, code: str) -> dict[str, object]:
            output_path.write_bytes(b"png")
            return {"success": True, "message": "ok"}

    monkeypatch.setattr(preview, "ServerProxy", FakeServerProxy)

    result = preview.export_preview_via_running_freecad(fcstd_path, output_path)

    assert result.succeeded is True
    assert output_path.exists()


def test_preview_export_skips_when_rpc_unreachable(tmp_path: Path, monkeypatch) -> None:
    fcstd_path = tmp_path / "model.FCStd"
    output_path = tmp_path / "preview.png"
    fcstd_path.write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(preview, "_rpc_endpoint_is_reachable", lambda rpc_url: False)

    result = preview.export_preview_via_running_freecad(fcstd_path, output_path)

    assert result.succeeded is False
    assert "not reachable" in result.message
    assert not output_path.exists()
