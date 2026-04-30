# Project Overview

HermesCAD is not a generic CAD generator. It is an engineering inbox workflow agent.

The core idea is simple: engineers already send DWG and DXF files over email and WhatsApp when they need a repeatable CAD operation completed. Hermes already handles those communication channels. HermesCAD adds the engineering workflow layer that interprets the request, inspects the drawing, calls FreeCAD, and packages the result.

For the hackathon MVP:

- Hermes receives the message and attachment.
- Hermes invokes the HermesCAD skill.
- HermesCAD prefers `neka-nat/freecad-mcp` for FreeCAD control.
- HermesCAD falls back to local FreeCAD scripts when MCP is unavailable.
- The result is returned as STEP, STL, FCStd, preview, and a report when possible.

HermesCAD is intentionally narrow in scope. Version 1 is built for 2D-to-3D profile parts with one global thickness from DXF drawings, plus explicit pocket or blind-depth operations when the request text clearly specifies them. It is not for arbitrary assemblies, full drawing-note interpretation, or manufacturing sign-off.
