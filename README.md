# HermesCAD

HermesCAD turns engineering inbox requests into CAD deliverables. Engineers already send DWG/DXF files over email and WhatsApp. Hermes reads the message, understands the requested CAD operation, calls FreeCAD through a reusable engineering skill and FreeCAD MCP, generates STEP/STL/FCStd/preview/report, and sends the result back in the same thread.

## What HermesCAD Is

HermesCAD is an engineering workflow agent for repeatable CAD operations. The MVP focuses on simple 2D mechanical DXF drawings such as plates and brackets, then turns them into a lightweight FreeCAD workflow with documented assumptions.

## What HermesCAD Does

- Receives a DXF or DWG-oriented CAD request through Hermes.
- Prefers DXF inspection with `ezdxf`.
- Uses FreeCAD as the only CAD engine.
- Prefers [`neka-nat/freecad-mcp`](https://github.com/neka-nat/freecad-mcp) as the primary FreeCAD MCP.
- Falls back to local FreeCAD scripts if the MCP path is unavailable.
- Produces a report, packaged outputs, and clear status messages even when FreeCAD is missing.

## What HermesCAD Does Not Do

- It does not promise perfect DWG conversion.
- It does not produce manufacturing-ready CAD automatically.
- It does not fully understand every engineering drawing.
- It does not replace CAD engineers.
- It does not introduce CadQuery, Conjure, or a second CAD stack in the MVP.

## How Hermes Fits In

Hermes already owns the communication layer. This repository does not build email or WhatsApp integrations from scratch. Instead, it provides:

- The HermesCAD skill in [hermes/skills/hermescad/SKILL.md](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/skills/hermescad/SKILL.md)
- Hermes MCP configuration examples in [hermes/config](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/config)
- Local scripts and FreeCAD automation helpers that Hermes can call

## How FreeCAD Fits In

FreeCAD is the only CAD backend in this repository. The runtime architecture is:

Email / WhatsApp  
↓  
Hermes existing communication layer  
↓  
Hermes Agent  
↓  
HermesCAD Skill  
↓  
`neka-nat/freecad-mcp` OR local FreeCAD scripts  
↓  
FreeCAD  
↓  
STEP / STL / FCStd / preview / report  
↓  
Hermes sends result back

## FreeCAD MCP Used

The primary MCP is [`neka-nat/freecad-mcp`](https://github.com/neka-nat/freecad-mcp). For the hackathon MVP, Hermes should expose only this minimal tool set:

- `create_document`
- `execute_code`
- `get_view`
- `get_objects`
- `get_object`

See [hermes/config/freecad_mcp_config_example.yaml](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/config/freecad_mcp_config_example.yaml) and [docs/freecad_mcp.md](/Users/devatreya/Desktop/Projects/HermesCAD/docs/freecad_mcp.md).

## Run The Local Demo

1. Create and activate a Python environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run:

```bash
python scripts/run_local_demo.py
```

On macOS, HermesCAD also checks the standard app-bundle path `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd` automatically. If your install lives somewhere else, set `FREECAD_CMD` first.

Expected outputs:

- `jobs/<job_id>/geometry_summary.json`
- `jobs/<job_id>/report.md`
- `jobs/<job_id>/job_summary.json`
- `outputs/<job_id>_outputs.zip`
- If FreeCAD is available:
  `jobs/<job_id>/hermescad_model.FCStd`, `hermescad_model.step`, `hermescad_model.stl`, and possibly `preview.png`

The local demo does not require Hermes or FreeCAD MCP. If FreeCAD is not installed, it still completes DXF inspection, report generation, and packaging while clearly marking CAD generation as skipped.

## Connect This To Hermes

1. Install or copy the skill in [hermes/skills/hermescad](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/skills/hermescad).
2. Merge the example MCP config from [hermes/config/freecad_mcp_config_example.yaml](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/config/freecad_mcp_config_example.yaml) into `~/.hermes/config.yaml`.
3. Keep the FreeCAD tool list minimal for the demo.
4. Run `/reload-mcp` in Hermes after saving the config.
5. Test a basic tool such as `mcp_freecad_get_objects` or `mcp_freecad_create_document`.

## Use The Hermes Skill

The skill instructions live in [hermes/skills/hermescad/SKILL.md](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/skills/hermescad/SKILL.md). Hermes should use that skill when a user sends a simple plate/bracket DXF workflow request such as:

> Create a 10 mm thick 3D model from this 2D drawing. Cut all circular holes through. Add 1 mm chamfers. Send STEP, STL, FreeCAD file, preview, and report.

## Fallback Path If MCP Is Not Available

If `neka-nat/freecad-mcp` is unavailable or unstable, HermesCAD falls back to:

Hermes  
→ HermesCAD skill  
→ local Python scripts in [scripts](/Users/devatreya/Desktop/Projects/HermesCAD/scripts)  
→ FreeCAD via `freecadcmd`/`FreeCAD` if installed  
→ report + package + clear failure notes if FreeCAD still cannot run

That fallback still uses FreeCAD as the only CAD backend.

## Repository Guide

- [PROJECT_OVERVIEW.md](/Users/devatreya/Desktop/Projects/HermesCAD/PROJECT_OVERVIEW.md)
- [SETUP.md](/Users/devatreya/Desktop/Projects/HermesCAD/SETUP.md)
- [DEMO_SCRIPT.md](/Users/devatreya/Desktop/Projects/HermesCAD/DEMO_SCRIPT.md)
- [LIMITATIONS.md](/Users/devatreya/Desktop/Projects/HermesCAD/LIMITATIONS.md)
- [docs/architecture.md](/Users/devatreya/Desktop/Projects/HermesCAD/docs/architecture.md)
- [docs/workflow.md](/Users/devatreya/Desktop/Projects/HermesCAD/docs/workflow.md)
- [docs/mvp_scope.md](/Users/devatreya/Desktop/Projects/HermesCAD/docs/mvp_scope.md)
- [docs/freecad_mcp.md](/Users/devatreya/Desktop/Projects/HermesCAD/docs/freecad_mcp.md)
- [docs/future_work.md](/Users/devatreya/Desktop/Projects/HermesCAD/docs/future_work.md)
