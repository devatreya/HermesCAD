---
name: hermescad
description: "Process 2D DXF/DWG CAD requests into FreeCAD outputs with assumptions, warnings, and report generation."
version: 0.1.0
metadata:
  hermes:
    tags: [cad, freecad, dxf, dwg, engineering, step, stl, fcstd]
---

# HermesCAD Skill

## When To Use This Skill

Use this skill when Hermes receives an engineering request with a CAD attachment and the user wants a repeatable 2D-to-3D CAD operation in FreeCAD. The strongest current path is a planar drawing with closed contours that can be interpreted as one-thickness material plus through-cut holes, slots, windows, or other nested cutouts. HermesCAD can also handle explicit pocket, blind-hole, counterbore, countersink, metric screw-hole, approximate threaded-hole, preserved-island boss, and deterministic assembly operations when the request text or assembly manifest clearly specifies the required dimensions and placements.

## Accepted Inputs

- Natural-language request text in Hermes chat
- DXF attachment
- DWG attachment when DXF is unavailable
- Optional assembly manifest with explicit part placements
- Optional multi-part prompt with explicit part file paths, per-part instructions, and exact placements
- Optional thickness, chamfer, hole-edit, screw-hole, export-format, and unit instructions

## Default Assumptions

- Prefer DXF over DWG.
- Use FreeCAD as the only CAD backend.
- Prefer `neka-nat/freecad-mcp` first.
- Use the local FreeCAD script fallback only if MCP is unavailable or fails.
- Always generate a report.
- Always state assumptions and warnings.
- Never claim manufacturing readiness.

## Workflow Steps

1. Identify the attachment file type first.
2. Create a single canonical job directory under the repository `jobs/` folder, for example `jobs/job_<timestamp>`.
3. Copy the source drawing into that job directory.
4. If the file is DXF, inspect it directly.
5. If the file is DWG, attempt conversion to DXF using LibreDWG if available.
6. Extract or confirm units.
7. Extract or confirm thickness.
8. Detect whether the drawing provides a safe closed planar profile for one-thickness 2D-to-3D reconstruction.
9. Inspect geometry:
   units if available, bounding box, lines, polylines, circles, arcs, closed contours, nesting depth, cutout candidates, slot-like contours, and circular hole candidates
10. Build a feature plan from the request text:
   base thickness, chamfer, through-cuts, blind holes, pocket depths, slot depths, preserved-island boss heights, and explicit hole-finishing operations such as counterbores, countersinks, threaded holes, or metric screw-hole presets where clearly stated
   Use hole-group selectors when the request distinguishes `corner holes`, `center hole`, `top holes`, or similar subsets.
11. If the request is an assembly, require or construct an explicit manifest with part drawings, per-part instructions, and placements before CAD generation.
12. If the user provided multiple part file paths directly in the Hermes prompt, normalize that prompt into the same explicit runtime structure HermesCAD would have loaded from a manifest.
13. Prefer FreeCAD MCP execution for model creation and export.
14. If MCP is unavailable, use the local FreeCAD scripts.
15. Generate STEP, STL, FCStd, preview, and report when possible.
16. Package the final job directory into exactly one zip file at `outputs/<job_id>_outputs.zip`.
17. If any step fails, explain exactly what failed and what the user should send next.

## Clarification Rules

- If thickness is missing, ask for thickness before 2D-to-3D generation.
- If units are missing, assume millimetres only if the user gave enough context; otherwise ask.
- If the user requests pockets, blind holes, multiple depth levels, counterbores, or countersinks but does not give the required depths, diameters, or included angles, ask for the missing values before modeling.
- If the user requests screw holes without existing DXF circular hole locations, explain that HermesCAD can resize or finish existing hole geometry but cannot safely invent new screw-hole positions from text alone.
- If the user requests threaded holes, require an explicit supported metric size such as `M4`, `M5`, `M6`, or `M8`. If the inspected DXF pilot hole is already larger than the required tap-drill diameter, explain that HermesCAD cannot safely back-fill a valid thread and needs corrected pilot geometry.
- If the user requests a raised boss or pad, confirm that the drawing includes a preserved island contour that HermesCAD can use safely. Do not invent boss footprints from text alone.
- If the user mixes blind-hole depth instructions with screw-head presets on the same hole targets, explain that HermesCAD will preserve the requested blind-hole depth and skip the overlapping screw preset unless the design intent is clarified.
- If the user asks for an assembly, require an explicit placement manifest or enough exact placement data to build one. Do not infer mates or bolt stacks automatically.
- If the drawing does not provide enough closed contour or depth information to safely infer a one-thickness build, explain the ambiguity and ask for the missing manufacturing intent or a cleaner planar export.
- If the request is ambiguous about holes, chamfers, or output formats, ask only for the missing details that block progress.

## CAD Safety Rules

- Always identify the file type first.
- Prefer DXF over DWG.
- Do not use CadQuery.
- Do not introduce a second CAD engine.
- Do not claim the generated model is manufacturing-ready.
- Always include assumptions and warnings in the final response.
- Treat `execute_code` as a trusted local-demo tool only.
- Metric screw-hole presets are approximate defaults for local workflow acceleration and must be reviewed before fabrication.
- Modeled threads use an ISO-style 60 degree metric profile and must still be reviewed before fabrication.

## FreeCAD MCP Execution Steps

1. Confirm that the Hermes MCP server for FreeCAD is enabled under `mcp_servers`.
2. Prefer the minimal tool set only:
   `mcp_freecad_create_document`, `mcp_freecad_execute_code`, `mcp_freecad_get_view`, `mcp_freecad_get_objects`, `mcp_freecad_get_object`
3. Create or open a working document.
4. Use inspected DXF geometry as the source of truth for closed contours, nesting relationships, hole candidates, slot-like cutouts, and the final planar profile.
5. Build an ordered feature plan from the request text before applying cuts:
   outer-profile extrusion first, then targeted pockets / blind holes / through-cuts / preserved-island boss additions / threaded holes / explicit hole-finishing operations in a deterministic sequence
6. If the request mentions screw holes, resolve whether the DXF already contains the circular hole locations. Use those contours as targets for clearance, counterbore, countersink, or threaded-hole presets; do not invent new hole locations from text alone.
7. If the request mentions `top`, `bottom`, `left`, `right`, `largest`, or `center`, apply those selectors to the relevant contour family so different slots, windows, pockets, or islands can receive different operations in the same part.
8. If countersinks and exterior chamfers are both requested in the same run, prioritize the countersinks and explicitly warn that HermesCAD will skip the exterior chamfer for robustness unless the workflow is updated.
9. Use `execute_code` only for trusted local workflows where direct FreeCAD automation is required.
10. Capture a preview with `get_view` when available and save it as `preview.png`.
11. Export STEP, STL, FCStd, and report the result.
12. If the request is an assembly, finish each part first, then place the resulting part outputs into one explicit FreeCAD assembly document using the provided placements.
13. If MCP returns errors or the RPC server is unavailable, switch to the fallback local-script path.

## Fallback Local Script Steps

1. Use `scripts/process_cad_request.py` for orchestration.
2. If the input is DWG, attempt conversion with `scripts/convert_dwg_to_dxf.py`.
3. Inspect geometry with `scripts/inspect_dxf.py`.
4. Build a structured feature plan from the request text before CAD generation.
5. Call `scripts/generate_freecad_model.py` if FreeCAD is available.
6. If the FreeCAD GUI RPC server is running, export `preview.png` from the live FreeCAD session after model generation.
7. If FreeCAD is unavailable, still generate the report and output package and explicitly mark CAD generation as skipped.
8. Package artifacts with `scripts/package_outputs.py`.

## Output Requirements

- Always return a Markdown report.
- Return STEP, STL, FCStd, preview, and report when possible.
- Always write deliverables into one canonical job directory under `jobs/`.
- Always create exactly one packaged zip under `outputs/<job_id>_outputs.zip`.
- Do not create extra ad hoc output folders under `outputs/` for the same run.
- Always state assumptions.
- Always state warnings.
- If something fails, explain exactly what failed and what the user should send next.

## Response Template

Status:
- Request type identified: `<DXF or DWG>`
- Workflow path used: `<FreeCAD MCP or local FreeCAD fallback>`

Assumptions:
- `<units>`
- `<thickness>`
- `<other geometry assumptions>`

Outputs:
- `<STEP if generated>`
- `<STL if generated>`
- `<FCStd if generated>`
- `<preview if generated>`
- `<report>`

Warnings:
- `<engineering review warning>`
- `<any skipped or ambiguous step>`

If Blocked:
- `<exact failure>`
- `<what the user should send next>`
