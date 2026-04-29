---
name: hermescad
description: "Process simple DXF/DWG CAD requests into FreeCAD outputs with assumptions, warnings, and report generation."
version: 0.1.0
metadata:
  hermes:
    tags: [cad, freecad, dxf, dwg, engineering, step, stl, fcstd]
---

# HermesCAD Skill

## When To Use This Skill

Use this skill when Hermes receives an engineering request with a CAD attachment and the user wants a repeatable CAD operation on a simple mechanical 2D drawing, especially a plate or bracket workflow that can be handled in FreeCAD.

## Accepted Inputs

- Natural-language request text from email or WhatsApp
- DXF attachment
- DWG attachment when DXF is unavailable
- Optional thickness, chamfer, hole-edit, export-format, and unit instructions

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
8. Detect whether the request fits the MVP scope:
   simple plate or bracket from a 2D mechanical drawing
9. Inspect geometry:
   units if available, bounding box, lines, polylines, circles, arcs, and circular hole candidates
10. Prefer FreeCAD MCP execution for model creation and export.
11. If MCP is unavailable, use the local FreeCAD scripts.
12. Generate STEP, STL, FCStd, preview, and report when possible.
13. Package the final job directory into exactly one zip file at `outputs/<job_id>_outputs.zip`.
14. If any step fails, explain exactly what failed and what the user should send next.

## Clarification Rules

- If thickness is missing, ask for thickness before 2D-to-3D generation.
- If units are missing, assume millimetres only if the user gave enough context; otherwise ask.
- If the drawing looks outside the MVP scope, say so clearly and ask for a simpler DXF, a clearer instruction, or a manual engineering review path.
- If the request is ambiguous about holes, chamfers, or output formats, ask only for the missing details that block progress.

## CAD Safety Rules

- Always identify the file type first.
- Prefer DXF over DWG.
- Do not use CadQuery.
- Do not introduce a second CAD engine.
- Do not claim the generated model is manufacturing-ready.
- Always include assumptions and warnings in the final response.
- Treat `execute_code` as a trusted local-demo tool only.

## FreeCAD MCP Execution Steps

1. Confirm that the Hermes MCP server for FreeCAD is enabled under `mcp_servers`.
2. Prefer the minimal tool set only:
   `mcp_freecad_create_document`, `mcp_freecad_execute_code`, `mcp_freecad_get_view`, `mcp_freecad_get_objects`, `mcp_freecad_get_object`
3. Create or open a working document.
4. Use inspected DXF geometry as the source of truth for the MVP plate envelope and circular hole candidates.
5. Use `execute_code` only for trusted local workflows where direct FreeCAD automation is required.
6. Capture a preview with `get_view` when available and save it as `preview.png`.
7. Export STEP, STL, FCStd, and report the result.
8. If MCP returns errors or the RPC server is unavailable, switch to the fallback local-script path.

## Fallback Local Script Steps

1. Use `scripts/process_cad_request.py` for orchestration.
2. If the input is DWG, attempt conversion with `scripts/convert_dwg_to_dxf.py`.
3. Inspect geometry with `scripts/inspect_dxf.py`.
4. Call `scripts/generate_freecad_model.py` if FreeCAD is available.
5. If the FreeCAD GUI RPC server is running, export `preview.png` from the live FreeCAD session after model generation.
6. If FreeCAD is unavailable, still generate the report and output package and explicitly mark CAD generation as skipped.
7. Package artifacts with `scripts/package_outputs.py`.

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
