# Project Overview

HermesCAD is not a generic CAD generator. It is a Hermes-driven engineering workflow agent for repeatable CAD operations.

The core idea is simple: a user prompts Hermes in chat, points it at one or more CAD files, and asks for a repeatable engineering operation. HermesCAD adds the workflow layer that interprets the request, inspects the drawing, calls FreeCAD, and packages the result.

For the hackathon MVP:

- Hermes receives the prompt and file path or attachment.
- Hermes invokes the HermesCAD skill.
- HermesCAD prefers `neka-nat/freecad-mcp` for FreeCAD control.
- HermesCAD falls back to local FreeCAD scripts when MCP is unavailable.
- The result is returned in Hermes chat and written to disk as STEP, STL, FCStd, preview, and a report when possible.

HermesCAD is intentionally narrow in scope. Version 1 is built for 2D-to-3D profile parts with one global thickness from DXF drawings, plus explicit pocket or blind-depth operations when the request text clearly specifies them. It is not for arbitrary assemblies, full drawing-note interpretation, or manufacturing sign-off.
