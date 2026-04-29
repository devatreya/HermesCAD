# Demo Script

1. User sends an email or WhatsApp message with a DXF drawing attached.
2. Hermes receives the request through its existing communication layer.
3. Hermes invokes the HermesCAD skill for a simple 2D-to-3D plate or bracket workflow.
4. HermesCAD inspects the drawing, then processes it through FreeCAD via `neka-nat/freecad-mcp` or the local fallback scripts.
5. HermesCAD returns STEP, STL, FCStd, preview, and report artifacts when possible.
6. Hermes explains all assumptions, warnings, and any skipped steps in the same reply thread.

Suggested demo talk track:

- Start with the sample request in [examples/requests/example_email_request.txt](/Users/devatreya/Desktop/Projects/HermesCAD/examples/requests/example_email_request.txt).
- Show the sample DXF in [examples/drawings/bracket_simple.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/bracket_simple.dxf).
- Run `python scripts/run_local_demo.py`.
- Open the generated `report.md`, `geometry_summary.json`, and output package.
- If FreeCAD is installed, show the exported CAD files and preview.
- If FreeCAD is not installed, show that the workflow still reports the issue cleanly instead of faking CAD success.

