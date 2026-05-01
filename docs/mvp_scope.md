# MVP Scope

## In Scope

- 2D DXF profile drawings with closed planar contours
- One-thickness profile reconstruction from non-rectangular outer boundaries
- Circular holes, slots, internal windows, and other through-cut contour detection
- Explicit pocket-depth, blind-hole, counterbore, countersink, metric screw-hole, and preserved-island boss operations when the request text specifies those dimensions clearly
- Approximate internal metric threaded-hole modeling on existing DXF hole geometry when the request specifies a supported metric size
- Selector-driven region targeting such as `top slot`, `largest pocket`, `right window`, or `center island`
- Selector-driven hole targeting such as `corner holes 10 mm deep` or `center hole countersunk`
- Deterministic assembly builds from explicit manifests with part-level instructions and placements
- Thickness-driven 2D-to-3D extrusion
- STEP, STL, FCStd, preview when possible, and report generation
- Hermes skill guidance
- FreeCAD MCP configuration examples
- Local fallback scripts

## Out Of Scope

- Arbitrary DWG fidelity
- Multi-depth pockets and variable-thickness feature inference
- Simultaneous countersink plus exterior-chamfer execution in a single stable feature pass
- Automatic placement of new screw holes from natural-language instructions without matching DXF hole geometry
- Standards-verified or tolerance-certified thread tolerances
- Arbitrary additive boss footprints that are not represented as preserved islands in the DXF topology
- Automatic mate inference, constraint solving, or fit validation for assemblies
- Nested blocks and xrefs
- GD&T interpretation
- Manufacturing sign-off
- Automatic handling of every engineering drawing style
- CadQuery, Conjure, or any second CAD engine
