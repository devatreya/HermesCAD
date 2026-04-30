# Sample Drawings

## HermesCAD-authored fixtures

- [bracket_simple.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/bracket_simple.dxf)
  Rectangular bracket sample used by the original local demo.
- [mount_plate_complex.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/mount_plate_complex.dxf)
  One-thickness mounting plate with a non-rectangular outer profile, a rectangular window, an obround slot, and five holes.
- [dogbone_link_complex.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/dogbone_link_complex.dxf)
  Dogbone-style link with rounded outer lobes, two holes, and a through-slot.
- [nested_pocket_island_complex.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/nested_pocket_island_complex.dxf)
  Nested pocket sample with a preserved island, a secondary slot feature, and multiple holes. This is the best current stress test for explicit pocket-depth sequencing.
- [actuator_plate_advanced.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/actuator_plate_advanced.dxf)
  Advanced multi-feature plate with two slots, multiple windows/pockets, a preserved center island for boss testing, and mixed hole groups for targeted screw-hole workflows.
- [assembly_base_plate_threaded.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/assembly_base_plate_threaded.dxf)
  Base plate with four M6 tap-drill pilot holes, a central pocket, and a preserved island sized for deterministic threaded-hole and assembly testing.
- [assembly_cover_plate_clearance.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/assembly_cover_plate_clearance.dxf)
  Matching cover plate with M6 clearance holes, a large central window, and a top slot for the threaded-cover-stack assembly example.

## Internet-sourced contour benchmarks

- [internet_closed_loop_with_arcs.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/internet_closed_loop_with_arcs.dxf)
  Copied from the `ezdxf` repository as a closed-loop arc benchmark.
- [internet_nested_polylines_benchmark.dxf](/Users/devatreya/Desktop/Projects/HermesCAD/examples/drawings/internet_nested_polylines_benchmark.dxf)
  Copied from the `ezdxf` repository as a nested-polyline benchmark with open-chain leftovers and text entities.

Source attribution for the internet benchmarks:

- `internet_closed_loop_with_arcs.dxf` source:
  `mozman/ezdxf/examples/edgeminer/6_closed_loop_with_arcs.dxf`
- `internet_nested_polylines_benchmark.dxf` source:
  `mozman/ezdxf/examples/edgeminer/1_polylines.dxf`

The `ezdxf` project is MIT-licensed, which makes these benchmark files convenient for repository examples and parser regression tests.
