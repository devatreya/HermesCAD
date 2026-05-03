# Architecture

```text
User prompt in Hermes chat
      ↓
Hermes Agent
      ↓
HermesCAD Skill
      ↓
neka-nat/freecad-mcp OR local FreeCAD scripts
      ↓
FreeCAD
      ↓
STEP / STL / FCStd / preview / report
      ↓
Hermes returns results in chat and on disk
```

Notes:

- Hermes owns the prompt orchestration and tool execution.
- HermesCAD owns the engineering workflow logic.
- FreeCAD is the only CAD engine in the MVP.
- `neka-nat/freecad-mcp` is the primary automation interface.
- Local Python plus FreeCAD scripts provide the fallback path.
