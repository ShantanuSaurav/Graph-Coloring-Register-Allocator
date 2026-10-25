# Final release — implementation and verification notes

## What changed after the initial academic reviews

The basic TAC → CFG → liveness → interference → coalescing → coloring → spilling pipeline remains recognizable from Reviews 1 and 2. Subsequent engineering work added:

1. **Native SVG graphs**: no CDN or Graphviz JS dependency. Connected interference components have a bounded force layout, while isolated nodes are rendered explicitly; CFG nodes display basic-block details and directed arrows.
2. **Instruction-level liveness**: live-before and live-after rows clarify why a single-block program can have empty block-level IN/OUT sets while requiring multiple simultaneous registers.
3. **Resolved copy coalescing**: visual assignments now include nodes whose names were coalesced away rather than showing them as inexplicably uncolored.
4. **More robust spilling**: after the bounded retry heuristic fails and K≥2, the engine tries a conservative rewrite beginning from the original program, assigning each virtual value a spill slot and shortening its live range. It returns a separately named success state and reports the added memory operations.
5. **Bounded small-graph exact fallback**: existing DSATUR-style search can avoid avoidable spills on small colorable graphs; it is limited by graph size and assignment budget.
6. **Verification**: the test suite exercises interference checks, a bounded TAC interpreter, randomized semantic preservation, and API results. Integer division in the interpreter no longer converts arbitrary-precision values through floating-point arithmetic.
7. **Complexity studies**: one experiment varies K for the current source; a second varies synthetic TAC size with fixed K. Both report median wall-time and median peak Python allocations, not machine-code runtime.
8. **Student interface**: rebuilt restrained light UI, step descriptions, benchmark examples shipped as static resources, a standalone guide, responsive layout, register groups and exports.

## Verification performed for the final package

- `python -m pytest -q` runs all tests; see the result from the final packaging check.
- `node --check public/script.js` validates JavaScript syntax.
- FastAPI TestClient exercises the graph, liveness, coloring and experiment endpoints.
- A headless Chromium DOM smoke test mounts the actual HTML/CSS/JS and supplies JSON responses captured from the real FastAPI app. It verifies graph SVGs, CFG SVGs, liveness tables, register groups, learning-guide navigation, complexity charts and responsive menu behavior. This tests frontend rendering, but **is not a real live Vercel browser test**.

## Limitations retained honestly

- Educational intra-procedural TAC only; no target machine code, calling conventions, precolored hardware registers, or stack-frame layout emitted for an ISA.
- Correctness tests exercise bounded example programs and randomized subsets. Passing them does not prove correctness for all possible TAC programs.
- K=1 may be insufficient for two distinct simultaneous operands. The conservative fallback applies only for K≥2 and may itself fail on unsupported instruction constraints.
- The conservative fallback can produce substantially more memory traffic than a better heuristic.
- Empirical complexity measurements depend on the Python interpreter, system load and `tracemalloc`. Avoid labeling them formal Big-O measurements.
- An external Vercel deployment must still be verified on the new project domain.

## Project archive

The root contains upload-ready source, tests, static assets, benchmark fixtures, academic review files and documentation. It deliberately excludes Python caches and unrelated editor/tool history.
