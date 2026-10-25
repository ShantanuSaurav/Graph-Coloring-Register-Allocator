# Workbench design note (final release)

The final site is a four-workspace teaching tool: Allocation explorer,
Complexity analysis, Register banks, and Learning guide. Its source is
`public/index.html`, `public/style.css`, and `public/script.js`.

## Rendering

Graphs are rendered directly as SVG without external JavaScript, libraries, or
Graphviz WASM. The interference view separates connected components and isolated
variables; a graph with zero edges still shows all register nodes. Node inspectors
explain graph degree, neighbors, and physical register assignment. The CFG view
uses directed arrows between basic blocks. SVG export is available.

## Data semantics

The server returns every allocation iteration including CFG, per-instruction
liveness, interference edges, copy coalescing, simplify stack, spill rewrites and
assigned registers. Merged coalescing names are resolved for a complete node
color map. K controls coloring/spill pressure but not original-program liveness.

## Complexity experiments

A: vary K for a fixed TAC source. B: vary synthetic TAC instruction count for
fixed K. Time and memory are empirical Python allocator measurements. They are
not a proof of Big-O or executable runtime.

## Known limits

See `docs/FINAL_RELEASE.md`. No production deployment or full machine-level
correctness is claimed merely because local tests pass.
