from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from xmlrpc.client import ServerProxy


DEFAULT_FREECAD_RPC_URL = "http://127.0.0.1:9875"


@dataclass
class PreviewExportResult:
    attempted: bool
    succeeded: bool
    output_path: str | None
    message: str


@dataclass
class FreeCADRpcExecutionResult:
    attempted: bool
    succeeded: bool
    message: str
    response: object | None = None


def _rpc_endpoint_is_reachable(rpc_url: str, timeout_seconds: float = 1.5) -> bool:
    parsed = urlparse(rpc_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def freecad_rpc_url() -> str:
    return os.environ.get("HERMESCAD_FREECAD_RPC_URL", DEFAULT_FREECAD_RPC_URL)


def execute_code_via_running_freecad(
    code: str,
    rpc_url: str | None = None,
) -> FreeCADRpcExecutionResult:
    resolved_rpc_url = rpc_url or freecad_rpc_url()
    if not _rpc_endpoint_is_reachable(resolved_rpc_url):
        return FreeCADRpcExecutionResult(
            attempted=False,
            succeeded=False,
            message=(
                "FreeCAD RPC execution was skipped because the FreeCAD GUI RPC server was not reachable. "
                "Start the FreeCAD MCP RPC server to enable live FreeCAD automation."
            ),
        )

    try:
        proxy = ServerProxy(resolved_rpc_url, allow_none=True)
        response = proxy.execute_code(code)
    except Exception as exc:
        return FreeCADRpcExecutionResult(
            attempted=True,
            succeeded=False,
            message=f"FreeCAD RPC execution failed: {exc}",
        )

    if isinstance(response, dict):
        if response.get("success"):
            return FreeCADRpcExecutionResult(
                attempted=True,
                succeeded=True,
                message=str(response.get("message") or "FreeCAD RPC execution succeeded."),
                response=response,
            )
        return FreeCADRpcExecutionResult(
            attempted=True,
            succeeded=False,
            message=str(response.get("error") or response.get("message") or "FreeCAD RPC execution failed."),
            response=response,
        )

    return FreeCADRpcExecutionResult(
        attempted=True,
        succeeded=False,
        message="FreeCAD RPC execution returned an unexpected response shape.",
        response=response,
    )


def _wait_for_output_path(output_path: Path, timeout_seconds: float = 8.0, poll_interval_seconds: float = 0.2) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if output_path.exists():
            return True
        time.sleep(poll_interval_seconds)
    return output_path.exists()


def _build_preview_rpc_code(
    fcstd_path: Path,
    output_path: Path,
    focus_object: str | None,
    width: int,
    height: int,
) -> str:
    return f"""
import os
import FreeCAD
import FreeCADGui

target_path = {json.dumps(str(fcstd_path.resolve()))}
output_path = {json.dumps(str(output_path.resolve()))}
focus_object = {repr(focus_object)}
image_width = {width}
image_height = {height}

previous_doc_name = FreeCAD.ActiveDocument.Name if FreeCAD.ActiveDocument else None
opened_here = False
doc = None

for existing in FreeCAD.listDocuments().values():
    if getattr(existing, "FileName", "") == target_path:
        doc = existing
        break

if doc is None:
    doc = FreeCAD.openDocument(target_path)
    opened_here = True

FreeCAD.setActiveDocument(doc.Name)
try:
    FreeCADGui.setActiveDocument(doc.Name)
except Exception:
    pass

gui_doc = FreeCADGui.getDocument(doc.Name)
if gui_doc is None:
    raise RuntimeError("No GUI document handle was available for preview export.")

for document_object in getattr(doc, "Objects", []):
    view_object = getattr(document_object, "ViewObject", None)
    if view_object is None:
        continue
    try:
        view_object.Visibility = True
    except Exception:
        pass
    try:
        view_object.DisplayMode = "Shaded"
    except Exception:
        pass
    try:
        view_object.ShapeColor = (0.72, 0.74, 0.78)
    except Exception:
        pass
    try:
        view_object.LineColor = (0.12, 0.14, 0.18)
    except Exception:
        pass

view = gui_doc.activeView()
if view is None or not hasattr(view, "saveImage"):
    raise RuntimeError("Active GUI view does not support image export.")

view.viewIsometric()
if focus_object:
    target_object = doc.getObject(focus_object)
    if target_object is not None:
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(target_object)
        FreeCADGui.SendMsgToActiveView("ViewSelection")
    else:
        view.fitAll()
else:
    view.fitAll()

FreeCADGui.updateGui()
view.saveImage(output_path, image_width, image_height, "White")

if opened_here:
    FreeCAD.closeDocument(doc.Name)

if previous_doc_name and previous_doc_name in FreeCAD.listDocuments():
    FreeCAD.setActiveDocument(previous_doc_name)
    try:
        FreeCADGui.setActiveDocument(previous_doc_name)
    except Exception:
        pass

print("saved", os.path.exists(output_path), output_path)
"""


def export_preview_via_running_freecad(
    fcstd_path: Path,
    output_path: Path,
    focus_object: str | None = "HermesCADPart",
    width: int = 1600,
    height: int = 1200,
) -> PreviewExportResult:
    fcstd_path = fcstd_path.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not fcstd_path.exists():
        return PreviewExportResult(
            attempted=False,
            succeeded=False,
            output_path=None,
            message=f"Preview skipped because the FreeCAD file does not exist: {fcstd_path}",
        )

    code = _build_preview_rpc_code(
        fcstd_path=fcstd_path,
        output_path=output_path,
        focus_object=focus_object,
        width=width,
        height=height,
    )

    execution = execute_code_via_running_freecad(code, rpc_url=freecad_rpc_url())
    if execution.succeeded and _wait_for_output_path(output_path):
        return PreviewExportResult(
            attempted=execution.attempted,
            succeeded=True,
            output_path=str(output_path),
            message=f"Preview exported to {output_path}.",
        )

    return PreviewExportResult(
        attempted=execution.attempted,
        succeeded=False,
        output_path=str(output_path),
        message=execution.message,
    )
