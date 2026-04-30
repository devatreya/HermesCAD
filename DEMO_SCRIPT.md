# Demo Script

1. User sends an email or WhatsApp message with a DXF drawing attached.
2. Hermes receives the request through its existing communication layer.
3. Hermes invokes the HermesCAD skill for a 2D-to-3D profile-part workflow.
4. HermesCAD inspects the drawing, then processes it through FreeCAD via `neka-nat/freecad-mcp` or the local fallback scripts.
5. HermesCAD returns STEP, STL, FCStd, preview, and report artifacts when possible.
6. Hermes explains all assumptions, warnings, and any skipped steps in the same reply thread.

Suggested demo talk track:

- Start with the sample request in [examples/requests/example_email_request.txt](/Users/devatreya/Desktop/Projects/HermesCAD/examples/requests/example_email_request.txt).
- Show the sample DXF in [examples/drawings/bracket_simple.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/bracket_simple.dxf) or one of the richer profile samples in [examples/drawings/README.md](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/README.md).
- Run `python scripts/run_local_demo.py`, or point it at a richer profile with `python scripts/run_local_demo.py --input examples/drawings/mount_plate_complex.dxf`.
- For a deeper feature-sequencing demo, use [nested_pocket_island_complex.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/nested_pocket_island_complex.dxf) and ask for a pocket depth, a deeper slot, and through-holes.
- Open the generated `report.md`, `geometry_summary.json`, and output package.
- If FreeCAD is installed, show the exported CAD files and preview.
- If FreeCAD is not installed, show that the workflow still reports the issue cleanly instead of faking CAD success.
