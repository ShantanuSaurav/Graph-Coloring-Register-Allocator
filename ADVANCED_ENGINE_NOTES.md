> **Historical development notes:** This document describes an earlier phase. For the latest behavior, including conservative spill fallback and complexity-by-input-size experiments, see [README.md](README.md) and [docs/FINAL_RELEASE.md](docs/FINAL_RELEASE.md).

# Advanced allocation, validation, and profiling

## Improvements in this release

1. **Bounded exact graph coloring fallback.** `src/colouring/allocator.py` retains the Chaitin–Briggs simplify/select heuristic, but if it produces spills on a small graph, `exact_colour_bounded()` attempts a DSATUR-style backtracking search. Graphs with over 18 nodes are skipped; the attempt is capped at 50,000 candidate assignments. This can avoid unnecessary spills. An unsuccessful search **does not prove** the graph is impossible to color when a limit was reached. The fallback colors the *coalesced* interference graph so it respects existing coalescing mappings.
2. **Semantic regression coverage.** `tests/test_advanced_allocation.py` checks a concrete graph the greedy allocator cannot color with K=3 even though a solution exists, an impossible K=2 triangle, search limits, and 75 seeded straight-line TAC programs at K=2,3,4. Where full allocation succeeds, it checks interference validity and compares rewritten TAC execution with the original using the bounded reference interpreter.
3. **Explicit stop reason.** The pipeline exposes `stop_reason` as `success` or `iteration_limit`, also returned by `/api/analyze`. Hitting the retry limit means the heuristic did not converge; it does not prove the program inherently needs more registers.
4. **Measured profiling.** `python scripts/profile_allocator.py --repeat 7 --output allocator_profile.csv` writes per-benchmark median Python allocator wall-time in milliseconds and peak traced Python allocation memory in KiB for K=2,3,4,8. These are empirical local measurements, not asymptotic Big-O proofs, native memory consumption or target-program runtime. The run is intentionally sequential to reduce interference but results depend on machine load and Python version.

## Current boundaries

- Register allocation remains intra-procedural, in a custom TAC IR. No physical ISA lowering, calling convention or machine-code execution is implemented.
- Exact coloring is exponential worst-case and therefore bounded and small-graph only; it does **not** make NP-complete graph coloring polynomial.
- Some spill-rewrite inputs still fail to converge within 10 iterations, notably `copy_heavy.tac` for K=2 or K=3. Future work: analyze live-range splitting, reload-temporary protection, rematerialization, pressure-aware coalescing decisions, and spill progress metrics. Each algorithmic change must keep execution-equivalence tests green.
- The interpreter checks TAC semantics, not physical-register instruction scheduling or executable machine code. Passing randomized tests is evidence, not exhaustive verification.
- Original program liveness depends on control flow and uses/definitions, **not** K. Only spill rewriting can modify a later round's liveness.

## Run checks

```bash
python -m pytest -q
python scripts/profile_allocator.py --repeat 5 --output allocator_profile.csv
python scripts/dev_server.py
```

Then open http://127.0.0.1:8000. The web workbench, including interference graph and instruction-level liveness, is retained from the prior release.
