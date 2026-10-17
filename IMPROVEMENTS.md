# Improvements — phase 1

This project was revised to address correctness and API reliability issues while preserving the existing frontend JSON contract.

## Completed

1. **Consistent failed allocations:** `run_allocation` no longer rewrites the IR after the final allowed iteration. Its returned `function`, `graph`, and `allocation` refer to the same analysed attempt. This prevents misleading final output after non-convergence.
2. **Explicit allocation bounds:** calling `run_allocation` with `k < 1` or `max_iterations < 1` now raises `ValueError`.
3. **API validation:** incoming TAC must be 1–50,000 characters, and register count `k` must be within 1–32. Invalid requests receive FastAPI's standard HTTP 422 response.
4. **Safer error reporting:** unexpected errors are logged server-side and are not returned with stack traces or internal error descriptions. Normal parsing and CFG errors remain user-readable and backward compatible.
5. **Safer CFG DOT generation:** graph identifiers and labels are quoted and escaped before embedding into Graphviz DOT.
6. **New regression tests:** five additional tests cover bad API inputs, unexpected backend errors, unsuccessful allocation state consistency, and invalid pipeline parameters.

## Verification

Run from the repository root:

```bash
python -m pytest -q
```

Verified locally: **144 passed** on Python 3.13.

## Recommended phase 2

- Investigate persistent spill/reload cycles in `copy_heavy.tac` at low K, then add progress/cycle detection and stronger spill heuristics with correctness checks.
- Build a simple TAC interpreter to compare original and rewritten program execution for semantic equivalence.
- Expose clear explanations for allocation non-convergence in the frontend.
- Add an interactive graph-coloring step player and iteration-by-iteration spill visualization.
- Add browser tests and resource limits based on the parsed instruction count.

**Note:** This phase does not claim to solve the difficult low-register spill-convergence cases. The 10-iteration safety cap remains.
