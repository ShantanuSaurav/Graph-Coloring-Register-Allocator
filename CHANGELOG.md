# Changelog

## Final workbench release

- Reworked the interface into Allocation explorer, Complexity analysis, Register banks, and Learning guide.
- Removed all runtime dependencies on external JavaScript graph renderers.
- Added compact interference components, isolated-node SVGs, CFG arrows, per-node inspection, SVG export and responsive graph sizing.
- Exposed coalesced-register mappings, simplify stack and optimistic nodes in the API.
- Added a bounded conservative final spill strategy for difficult K≥2 allocations, with explicit stop reason.
- Added synthetic input-size timing and space experiments alongside the original K comparison.
- Strengthened execution equivalence and API regression tests and fixed arbitrary-precision integer division.
- Bundled example TAC files inside `public/examples/` for portable static hosting.
- Added setup instructions, a learner's guide, release notes and screenshot previews.

## Earlier development phases

- Added typed FastAPI request validation, DOT escaping and safe errors.
- Fixed mismatched final-iteration state and fresh spill-temporary naming collisions.
- Added a reference TAC interpreter, graph-coloring consistency checks and benchmark profiling.
- Added a bounded exact-coloring fallback and randomized semantic tests.
