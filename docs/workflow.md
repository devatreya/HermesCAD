# Workflow

## Primary MVP Flow

1. Create a job folder.
2. Copy the input drawing into the job folder.
3. Detect the file type.
4. If the input is DWG, attempt conversion to DXF with LibreDWG.
5. Inspect DXF geometry with `ezdxf`.
6. Extract units, bounding box, entity counts, and circular hole candidates.
7. Generate a simple FreeCAD plate model from the geometry summary when thickness and units are available.
8. Export `FCStd`, `STEP`, `STL`, preview when possible, and a Markdown report.
9. Package the job outputs into a zip archive.

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

