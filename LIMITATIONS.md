# Limitations

- DWG is proprietary and conversion may fail.
- DXF is the preferred MVP input.
- 2D-to-3D conversion is ambiguous without thickness, depth, and units.
- Generated CAD must be reviewed by an engineer.
- Complex blocks, xrefs, GD&T, inferred mates, and unconstrained assembly reasoning are not supported in the MVP.
- The strongest validated path is still a one-thickness 2D profile part with explicit depths, plus deterministic assemblies that use a manifest with explicit placements.
- Partial-depth pockets, blind holes, counterbores, and countersinks are only safe when the request text gives explicit dimensions; HermesCAD does not infer those values reliably from DXF alone.
- Screw-hole presets only act on existing DXF circular hole geometry; HermesCAD does not safely invent new screw-hole positions from natural-language instructions alone.
- Screw-hole presets use approximate default clearance/head dimensions, and threaded-hole modeling uses an ISO-style 60 degree metric profile rather than tolerance-certified thread definitions.
- HermesCAD does not currently combine blind-hole depth instructions with overlapping screw-hole presets on the same exact hole targets; it preserves the blind-hole depth and skips the conflicting screw preset.
- HermesCAD does not currently combine overlapping threaded-hole and clearance/head-form screw presets on the same exact hole targets; it preserves the threaded-hole request and skips the conflicting head-form preset.
- Raised bosses are currently limited to preserved island contours already present in the inspected DXF topology; HermesCAD does not safely invent arbitrary additive boss footprints from text alone.
- When countersinks and exterior chamfers are requested together, HermesCAD currently prioritizes the countersinks and skips the exterior chamfer for FreeCAD robustness.
- The FreeCAD MCP `execute_code` tool is powerful and should be used carefully.
- HermesCAD does not claim manufacturing readiness.
