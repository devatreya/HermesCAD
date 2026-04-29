# FreeCAD MCP

## Selected MCP

HermesCAD uses [`neka-nat/freecad-mcp`](https://github.com/neka-nat/freecad-mcp) as the primary FreeCAD MCP.

## Why We Chose It

- It is purpose-built to let an AI assistant control FreeCAD.
- It exposes the exact kinds of document, object, and execution tools needed for a hackathon MVP.
- Its upstream README documents both local and remote-host setups.

## Tools We Expose

For the MVP, expose only:

- `create_document`
- `execute_code`
- `get_view`
- `get_objects`
- `get_object`

In Hermes, these appear as:

- `mcp_freecad_create_document`
- `mcp_freecad_execute_code`
- `mcp_freecad_get_view`
- `mcp_freecad_get_objects`
- `mcp_freecad_get_object`

We intentionally do not expose `delete_object` or `insert_part_from_library` for the demo unless a later workflow truly needs them.

## Example Hermes MCP Config

See [hermes/config/freecad_mcp_config_example.yaml](/Users/devatreya/Desktop/Projects/HermesCAD/hermes/config/freecad_mcp_config_example.yaml).

Local example:

```yaml
mcp_servers:
  freecad:
    command: "uvx"
    args:
      - "freecad-mcp"
    enabled: true
    timeout: 120
    connect_timeout: 60
    tools:
      include:
        - create_document
        - execute_code
        - get_view
        - get_objects
        - get_object
      resources: false
      prompts: false
```

## Reload MCP In Hermes

After updating `~/.hermes/config.yaml`, run:

```text
/reload-mcp
```

## Test The Connection

Suggested smoke tests:

1. Start the FreeCAD MCP RPC server from inside FreeCAD if required.
2. Reload Hermes MCP servers.
3. Call `mcp_freecad_get_objects`.
4. Call `mcp_freecad_create_document`.

If those work, HermesCAD can use the MCP-first path.

## Fallback If It Fails

If `neka-nat/freecad-mcp` is difficult to install or unstable:

- Keep FreeCAD as the only CAD backend.
- Use the local scripts in [scripts](/Users/devatreya/Desktop/Projects/HermesCAD/scripts).
- Run FreeCAD headlessly through `freecadcmd` or an equivalent system command when available.
- If FreeCAD still cannot run, generate inspection, report, and package outputs and clearly mark CAD generation as skipped.

## Security Warning

`execute_code` is powerful. Limit it to trusted local demo workflows and expose only the minimum tools needed for HermesCAD.

