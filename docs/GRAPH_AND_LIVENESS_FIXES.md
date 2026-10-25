# Visualization and data-flow improvements

- Replaced the force-simulation layout with deterministic compact positions, separating connected vertices and isolated registers.
- Added node inspector, keyboard-accessible node selection and SVG download.
- Added per-instruction live-before/live-after tables for every basic block and every allocation iteration.
- Clarified that K does **not** affect the liveness of the unchanged original TAC. Compare rewritten rounds for spill-induced changes.
- Recompute allocation when register count or coalescing changes, after the first run.
- Run `python -m pytest` and `node --check public/script.js` before deployment.

## Scope

This update does not make claims of optimal graph coloring or guaranteed spill convergence for every K. The existing ten-round convergence guard remains.
