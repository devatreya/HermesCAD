# Architecture

```text
Email / WhatsApp
      ↓
Hermes existing communication layer
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
Hermes sends result back
```

Notes:

- Hermes owns the communication channel integration.
- HermesCAD owns the engineering workflow logic.
- FreeCAD is the only CAD engine in the MVP.
- `neka-nat/freecad-mcp` is the primary automation interface.
- Local Python plus FreeCAD scripts provide the fallback path.

