# Assembly Examples

- [threaded_cover_stack/assembly_manifest.json](/Users/devatreya/Desktop/Projects/HermesCAD/examples/assemblies/threaded_cover_stack/assembly_manifest.json)
  Two-part deterministic assembly example that builds a threaded base plate and a clearance-hole cover plate, then places the cover 12 mm above the base.

Assembly manifests are explicit on purpose. HermesCAD does not infer mates automatically. Each manifest should describe:

- the part drawing path
- the natural-language part instruction text
- the final assembly placement for that part
- any explicit fastener specification that should be inserted into the assembly

The manifest is the preferred production input because it is deterministic and reviewable.

A Hermes prompt can also describe the same assembly without an existing JSON file, but the prompt must still provide the same information:

- each part path
- each part instruction
- each part placement
- any fastener intent

If a prompt provides only two file paths and says "assemble these", HermesCAD does not have enough information yet. It should stop and ask for the missing placements instead of inventing mates.
