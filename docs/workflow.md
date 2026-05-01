# Workflow

## Primary Part Flow

1. Create a job folder.
2. Copy the input drawing into the job folder.
3. Detect the file type.
4. If the input is DWG, attempt conversion to DXF with LibreDWG.
5. Inspect DXF geometry with `ezdxf`.
6. Extract units, bounding box, entity counts, closed contours, nesting depth, circular hole candidates, slot-like contours, and cutout candidates.
7. Build a feature plan from the request text and inspected geometry.
8. Generate the FreeCAD model when thickness, units, and a safe planar interpretation are available.
9. Export `FCStd`, `STEP`, `STL`, preview when possible, and a Markdown report.
10. Package the job outputs into one zip archive.

## Assembly Flow

1. Normalize the request into explicit assembly inputs.
2. Preferred input: one JSON manifest with part drawings, per-part instructions, placements, and optional fasteners.
3. Acceptable prompt-only input: multiple part file paths plus exact per-part instructions and exact placements.
4. Process each part independently through the standard HermesCAD part flow.
5. Resolve any fastener placement points from the inspected hole geometry of the source part.
6. Build the final assembly in FreeCAD from explicit placements.
7. Export assembly `FCStd`, `STEP`, `STL`, preview, assembly report, and one packaged zip.

## Request Normalization Rules

- One part file plus one modeling instruction can run directly.
- Two or more part files can run only if the request also includes deterministic placement data.
- If the request does not contain enough placement information, HermesCAD should stop rather than infer mates automatically.
- Internally, assembly execution remains manifest-shaped even when the user supplied the data in free-form Hermes prompt text.

## Hermes Integration Flow

1. Hermes receives the email or WhatsApp message.
2. Hermes invokes the HermesCAD skill.
3. HermesCAD prefers the FreeCAD MCP path.
4. HermesCAD falls back to local scripts when MCP is unavailable.
5. Hermes returns the packaged result and the report in the same thread.

## Fallback Behavior

If FreeCAD cannot run:

- DXF inspection still runs.
- The report is still generated.
- The package is still generated.
- CAD generation is clearly marked as skipped.

## Safety Stops

HermesCAD should stop instead of guessing when:

- thickness is missing for a 2D-to-3D build
- units are missing and the request does not provide enough context
- the drawing appears to contain multiple ambiguous top-level profiles
- the user requests an assembly without explicit placement data
- the user requests hole/thread/pocket details without enough dimensional information
