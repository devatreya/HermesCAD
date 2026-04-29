# Setup

## 1. Python Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`pytest` is included in `requirements.txt` so the local test suite can run in the same environment.

## 2. FreeCAD

Install FreeCAD as a system application. Do not add FreeCAD as a pip dependency in this repository.

After installation, verify that at least one of these commands is available:

- `freecadcmd`
- `FreeCAD`
- `freecad`

If your command name is different, set `FREECAD_CMD` in your shell or `.env`:

```bash
export FREECAD_CMD=/path/to/freecadcmd
```

On macOS, HermesCAD also auto-checks:

- `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`
- `~/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`

## 3. LibreDWG

LibreDWG is optional. HermesCAD uses it only for DWG to DXF conversion.

Expected command:

- `dwg2dxf`

If `dwg2dxf` is not installed, DWG conversion is skipped and the workflow tells the user to provide DXF or install LibreDWG.

## 4. neka-nat/freecad-mcp

Primary MCP: [`neka-nat/freecad-mcp`](https://github.com/neka-nat/freecad-mcp)

Recommended setup flow:

1. Install FreeCAD first.
2. Clone the upstream repository:

```bash
git clone https://github.com/neka-nat/freecad-mcp.git
```

3. Copy `addon/FreeCADMCP` into your FreeCAD `Mod` directory as described in the upstream README.
4. Restart FreeCAD.
5. Switch to the MCP Addon workbench.
6. Start the RPC server from the "FreeCAD MCP" toolbar, or enable auto-start if you want it every session.
7. Install `uv` so `uvx` is available, because the example Hermes config uses `uvx freecad-mcp`.

The upstream README also supports remote-host usage with `--host` when the FreeCAD RPC server is running on another machine.

## 5. Hermes Skill Installation

This repository includes the skill at:

- [hermes/skills/hermescad/SKILL.md](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/skills/hermescad/SKILL.md)

Install it into your Hermes skill directory according to your Hermes deployment conventions, or copy this skill folder into the location where Hermes loads custom skills.

## 6. Hermes MCP Config

Use the examples in:

- [hermes/config/hermes_config_example.yaml](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/config/hermes_config_example.yaml)
- [hermes/config/freecad_mcp_config_example.yaml](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/config/freecad_mcp_config_example.yaml)

Important notes:

1. Add the FreeCAD MCP entry under `mcp_servers` in `~/.hermes/config.yaml`.
2. Expose only the minimum tool set for the hackathon demo:
   `create_document`, `execute_code`, `get_view`, `get_objects`, `get_object`
3. Keep `resources` and `prompts` disabled unless you explicitly need them.
4. Run `/reload-mcp` in Hermes after changing the config.

## 7. Test The MCP Connection

After configuration:

1. Start FreeCAD and the FreeCAD MCP RPC server if required.
2. Reload Hermes MCP servers with `/reload-mcp`.
3. Call a low-risk tool such as:
   `mcp_freecad_get_objects`
4. Create a scratch document with:
   `mcp_freecad_create_document`

If that works, HermesCAD can prefer the MCP path.

## 8. Fallback Path

If the MCP setup fails or is unstable:

1. Keep FreeCAD installed locally.
2. Run the local scripts in this repository.
3. HermesCAD will inspect DXF, generate reports, and package outputs even when CAD generation is skipped.

The fallback path still uses FreeCAD as the only CAD backend.
