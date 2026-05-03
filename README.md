# HermesCAD

HermesCAD turns engineering CAD requests into deliverables through Hermes chat. A user gives Hermes a DXF or DWG file path, or an explicit assembly request, and HermesCAD interprets the job, calls FreeCAD through MCP or local automation, and generates STEP, STL, FCStd, preview, and report outputs.

## What HermesCAD Is

HermesCAD is an engineering workflow agent for repeatable CAD operations. The current strongest path is 2D-to-3D reconstruction of one-thickness profile parts from DXF drawings, including non-rectangular outlines, circular holes, slots, internal windows, and other through-cut contours, plus explicit pocket, blind-hole, counterbore, countersink, metric screw-hole, and preserved-island boss operations when the request text gives clear depth intent.

## What HermesCAD Does

- Receives a DXF or DWG-oriented CAD request through Hermes.
- Prefers DXF inspection with `ezdxf`.
- Uses FreeCAD as the only CAD engine.
- Prefers [`neka-nat/freecad-mcp`](https://github.com/neka-nat/freecad-mcp) as the primary FreeCAD MCP.
- Falls back to local FreeCAD scripts if the MCP path is unavailable.
- Produces a report, packaged outputs, and clear status messages even when FreeCAD is missing.
- Can apply approximate metric screw-hole presets such as clearance holes, socket-head counterbores, and countersunk screw heads to existing DXF hole locations.
- Can model approximate internal metric threads on existing DXF hole locations when the drawing already includes the pilot-hole geometry and the request specifies a supported metric size.
- Can target different slots, windows, pockets, and preserved islands by relative descriptors such as `top`, `bottom`, `right`, `largest`, or `center`.
- Can target different hole groups independently, for example `corner holes 10 mm deep` while keeping a `center hole` through for a screw-head feature.
- Can build deterministic assemblies from an explicit JSON manifest that lists part drawings, per-part instructions, and placements.

## What HermesCAD Does Not Do

- It does not promise perfect DWG conversion.
- It does not produce manufacturing-ready CAD automatically.
- It does not fully understand every engineering drawing.
- It does not replace CAD engineers.
- It does not introduce CadQuery, Conjure, or a second CAD stack in the MVP.
- It does not place new screw holes safely without explicit DXF geometry for the hole locations.
- It does not infer assembly mates or fastener stacks automatically.
- It does not claim standards-verified or manufacturing-certified thread tolerances; modeled threads use an ISO-style 60 degree metric profile and still require engineering review.

## How Hermes Fits In

Hermes is the agent and prompt surface for this project. This repository does not include email or WhatsApp integrations. Instead, it provides:

- The HermesCAD skill in [hermes/skills/hermescad/SKILL.md](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/skills/hermescad/SKILL.md)
- Hermes MCP configuration examples in [hermes/config](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/config)
- Local scripts and FreeCAD automation helpers that Hermes can call

## How FreeCAD Fits In

FreeCAD is the only CAD backend in this repository. The runtime architecture is:

User prompt in Hermes chat  
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
Hermes returns results in chat and on disk

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

For deterministic assemblies, use:

```bash
python scripts/process_assembly_request.py examples/assemblies/threaded_cover_stack/assembly_manifest.json
```

That workflow produces one root assembly job folder with nested part subfolders plus assembly-level `FCStd`, `STEP`, `STL`, `preview`, report, and one packaged zip.

The worked assembly example lives in:

- [examples/assemblies/threaded_cover_stack/assembly_manifest.json](/Users/devatreya/Desktop/Projects/HermesCAD/examples/assemblies/threaded_cover_stack/assembly_manifest.json)

That example builds a two-part deterministic assembly: a threaded base plate plus a clearance-hole cover plate placed 12 mm above it.

## Assembly Input Modes

HermesCAD uses a manifest-shaped assembly model internally, but that does not mean the user must always hand-author JSON first.

Supported ways to describe an assembly:

- Preferred and first-class: an explicit JSON manifest with part drawings, per-part instructions, placements, and optional fasteners
- Hermes prompt with multiple part file paths plus exact per-part instructions and exact placement data

Important rule:

- HermesCAD can build the assembly only after the request has been normalized into explicit part specifications and placements
- If a prompt contains two or more file paths but does not say how the parts are positioned relative to one another, HermesCAD should stop and ask for the missing placement data instead of inventing mates

In other words:

- A manifest is the most reliable production input
- A free-form Hermes prompt is also acceptable if it provides enough deterministic information for Hermes to construct the equivalent runtime manifest internally

For production-style usage, the assembly request should always resolve to these details before FreeCAD assembly starts:

- each part drawing path
- each part’s natural-language modeling instruction
- the exact placement for each part
- any explicit fastener specification that should be inserted into the assembly

Canonical output contract:

- Each run should have one canonical working directory under `jobs/<job_id>/`.
- Each run should have one packaged archive at `outputs/<job_id>_outputs.zip`.
- Hermes should not create extra ad hoc top-level output folders for the same run.

The local demo does not require Hermes or FreeCAD MCP. If FreeCAD is not installed, it still completes DXF inspection, report generation, and packaging while clearly marking CAD generation as skipped.

## Connect This To Hermes

1. Install or copy the skill in [hermes/skills/hermescad](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/skills/hermescad).
2. Merge the example MCP config from [hermes/config/freecad_mcp_config_example.yaml](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/config/freecad_mcp_config_example.yaml) into `~/.hermes/config.yaml`.
3. Keep the FreeCAD tool list minimal for the demo.
4. Run `/reload-mcp` in Hermes after saving the config.
5. Test a basic tool such as `mcp_freecad_get_objects` or `mcp_freecad_create_document`.

For local usage, start Hermes from the repository root and pass either:

- one DXF/DWG path plus a 2D-to-3D instruction
- an explicit assembly manifest path
- multiple part paths plus exact per-part instructions and exact placement data

For assemblies, Hermes should normalize the request into explicit part definitions and placements before the FreeCAD assembly step begins.

## Use The Hermes Skill

The skill instructions live in [hermes/skills/hermescad/SKILL.md](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/skills/hermescad/SKILL.md). Hermes should use that skill when a user sends a 2D-to-3D DXF workflow request such as:

> Create a 10 mm thick 3D model from this 2D drawing. Cut all circular holes through. Add 1 mm chamfers. Send STEP, STL, FreeCAD file, preview, and report.

You can also point the local demo at the richer profile samples:

- [mount_plate_complex.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/mount_plate_complex.dxf)
- [dogbone_link_complex.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/dogbone_link_complex.dxf)
- [nested_pocket_island_complex.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/nested_pocket_island_complex.dxf)
- [actuator_plate_advanced.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/actuator_plate_advanced.dxf)
- [assembly_base_plate_threaded.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/assembly_base_plate_threaded.dxf)
- [assembly_cover_plate_clearance.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/assembly_cover_plate_clearance.dxf)

Example assembly prompt with an explicit manifest:

```text
Use the hermescad skill with this explicit assembly manifest:

/absolute/path/to/assembly_manifest.json

Build the assembly exactly from the manifest.
Return FCStd, STEP, STL, preview, and a report.
```

Example assembly prompt without a hand-written manifest:

```text
Use the hermescad skill to assemble these two parts:

/absolute/path/to/base_plate.dxf
/absolute/path/to/cover_plate.dxf

Part instructions:
- base_plate: Create a 12 mm thick model and keep the four corner holes as M6 threaded holes 10 mm deep.
- cover_plate: Create an 8 mm thick model and keep the four corner holes as M6 clearance holes.

Placement instructions:
- Place the base_plate at X=0, Y=0, Z=0 with no rotation.
- Place the cover_plate at X=0, Y=0, Z=12 mm with no rotation.

Fasteners:
- Insert 4 ISO4762 M6 x 20 screws through the cover plate corner holes into the base plate threaded holes.

Return FCStd, STEP, STL, preview, and a report.
```

That prompt is valid because it contains the same information that would otherwise live in a manifest: part paths, part-level instructions, placements, and fastener intent.

If you want a real example to copy and adapt, start from:

- [examples/assemblies/threaded_cover_stack/assembly_manifest.json](/Users/devatreya/Desktop/Projects/HermesCAD/examples/assemblies/threaded_cover_stack/assembly_manifest.json)
- [examples/drawings/assembly_base_plate_threaded.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/assembly_base_plate_threaded.dxf)
- [examples/drawings/assembly_cover_plate_clearance.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/assembly_cover_plate_clearance.dxf)

## Fallback Path If MCP Is Not Available

If `neka-nat/freecad-mcp` is unavailable or unstable, HermesCAD falls back to:

Hermes  
→ HermesCAD skill  
→ local Python scripts in [scripts](/Users/devatreya/Desktop/Projects/HermesCAD/scripts)  
→ FreeCAD via `freecadcmd`/`FreeCAD` if installed  
→ report + package + clear failure notes if FreeCAD still cannot run

That fallback still uses FreeCAD as the only CAD backend.

## Repository Hygiene

Generated working files are intentionally local-only:

- [jobs](/Users/devatreya/Desktop/Projects/HermesCAD/jobs) is a runtime workspace
- [outputs](/Users/devatreya/Desktop/Projects/HermesCAD/outputs) stores packaged deliverables

Both directories are ignored by git except for their `.gitkeep` placeholders, so a fresh clone should not inherit someone else’s run artifacts.

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
