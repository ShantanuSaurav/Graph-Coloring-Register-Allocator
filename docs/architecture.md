# Architecture notes

## Pipeline

```
prog.tac
   |
   v
[M1] parser.py ------> instruction list
   |
   v
[M1] cfg.py ---------> Function with BasicBlocks, succs/preds, loop_depth
   |
   v
[M2] liveness.py ----> live_in / live_out on every block
   |
   v
[M2] interference.py -> InterferenceGraph (+ move_pairs)
   |
   v
[M3] allocator.py ---> coalesce -> simplify -> select -> AllocationResult
   |
   +-- success? --> emit allocated code
   |
   +-- actual spills? --> [M4] spiller.py rewrites the IR --> back to M1
```

## Module contracts

Everything crosses module boundaries through two files:

- `src/ir.py` — `Instr`, `BasicBlock`, `Function`
- `src/analysis/interference.py` — `InterferenceGraph`

Neither should change without telling the team. Everything else inside a module is that
owner's business.

## Why the loop terminates

Each actual spill removes one live range from contention and replaces it with several
very short ones (one per use). Short ranges have few interferences, so they colour
easily. In practice convergence takes two to four iterations on every benchmark here
(`briggs_example.tac` at K=2 is the slowest, at 4). `MAX_ITERATIONS = 10` in
`spiller.py` is a safety net, not an expected path — see `spiller.py`'s module
docstring for a concrete case where a naive choice of spill-cost heuristic *would*
have broken that guarantee, and why the pipeline avoids it.

## Measuring objective O3

Run the same benchmark twice at the same K:

```
python -m src.cli bench.tac --k 8 --no-coalesce   # baseline
python -m src.cli bench.tac --k 8                 # ours
```

Compare `count_spill_instructions` on the two outputs, or use
`scripts/coalescing_experiment.py`, which automates exactly this comparison (see the
README's "Coalescing ON vs OFF experiment" section) and reports the real,
non-fabricated result rather than assuming a target reduction holds on every input —
on `benchmarks/copy_heavy.tac` specifically it does not (spill counts are identical
ON and OFF at every tested K; see that section for why, and what coalescing *does*
measurably do there instead — real merges and redundant-move detection).

## Metrics as a single source of truth

`src/metrics.py`'s `AllocationMetrics`/`collect_metrics`/`run_and_collect_metrics`
were added so the CLI (`--metrics`), the web API (`/api/analyze`'s `metrics` field),
`scripts/run_benchmarks.py` and `scripts/coalescing_experiment.py` all compute the
same numbers the same way, instead of four separate ad-hoc counting implementations
that could silently drift apart. It reads two snapshots of one `run_allocation()`
call: the *first* iteration's `InterferenceGraph`/`AllocationResult` (captured via
`run_allocation`'s existing `on_iteration` hook) for graph-structure numbers — nodes,
edges, degree, coalescing candidates/merges/refusals — and the pipeline's *final*
`PipelineResult` for outcome numbers — spills, loads, stores, iterations, final
instruction count. Conflating the two would either describe the wrong "problem size"
(if spilling already rewrote the graph) or the wrong "result" (if only the first
attempt were reported), so the module docstring is explicit about which is which.

The `coalesce()`/`allocate()` instrumentation behind the coalescing numbers
(`coalesce_stats`, `coalesce_trace` on `AllocationResult`) is additive: both default
to empty/zero values and every existing call site and test from the original
implementation is unaffected. `coalesce_trace` is a live log of every pair the loop
actually evaluated, in order, including a pair re-evaluated in a later pass after an
earlier merge changed its neighbours — it is not reconstructed after the fact.
