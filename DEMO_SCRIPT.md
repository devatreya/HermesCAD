# Demo Script

1. User opens Hermes chat and provides a DXF or DWG file path, or attaches a drawing directly if the Hermes UI supports attachments.
2. Hermes receives the request in chat.
3. Hermes invokes the HermesCAD skill for a 2D-to-3D profile-part or assembly workflow.
4. HermesCAD inspects the drawing, then processes it through FreeCAD via `neka-nat/freecad-mcp` or the local fallback scripts.
5. HermesCAD returns STEP, STL, FCStd, preview, and report artifacts when possible.
6. Hermes explains all assumptions, warnings, and any skipped steps in the same chat response.

Suggested demo talk track:

- Start with the sample request text in [examples/requests/example_email_request.txt](/Users/devatreya/Desktop/Projects/HermesCAD/examples/requests/example_email_request.txt) or paste an equivalent prompt directly into Hermes chat.
- Show the sample DXF in [examples/drawings/bracket_simple.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/bracket_simple.dxf) or one of the richer profile samples in [examples/drawings/README.md](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/README.md).
- Show Hermes receiving the prompt and file path, then run the equivalent local path flow with `python scripts/run_local_demo.py`, or point it at a richer profile with `python scripts/run_local_demo.py --input examples/drawings/mount_plate_complex.dxf`.
- For a deeper feature-sequencing demo, use [nested_pocket_island_complex.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/nested_pocket_island_complex.dxf) and ask for a pocket depth, a deeper slot, and through-holes.
- For an assembly demo, use the manifest example in [examples/assemblies/threaded_cover_stack/assembly_manifest.json](/Users/devatreya/Desktop/Projects/HermesCAD/examples/assemblies/threaded_cover_stack/assembly_manifest.json) or describe the same assembly directly in Hermes chat with explicit placements.
- Open the generated `report.md`, `geometry_summary.json`, and output package.
- If FreeCAD is installed, show the exported CAD files and preview.
- If FreeCAD is not installed, show that the workflow still reports the issue cleanly instead of faking CAD success.
