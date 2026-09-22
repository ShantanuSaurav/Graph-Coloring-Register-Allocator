# regalloc-a5 — Graph-Coloring Register Allocator

A Chaitin–Briggs register allocator with interference-graph construction, conservative
coalescing and optimistic spilling.

**Course:** BCSE307 Compiler Design · **Project ID:** A5 · **Team:** \_\_

🚀 **Live Web App (Vercel Frontend):** [https://graph-coloring-register-allocator.vercel.app/](https://graph-coloring-register-allocator.vercel.app/)

---

## What this does

A compiler front end emits code over an unbounded number of *virtual registers*. A real
CPU has around 16. This tool decides which virtual registers get a physical register.

Two values can share a register as long as they are never live at the same time. We build
an **interference graph** — one node per live range, an edge between any two ranges that
overlap — and then colour it with K colours, where each colour is one physical register.
When K colours are not enough, we **spill** the least-costly value to memory.

```
prog.tac  ──►  parse  ──►  liveness  ──►  interference graph  ──►  colour  ──►  prog.alloc.tac
                                                    ▲                  │
                                                    └──── spill & rewrite ◄┘
```

---

## Quick start

```bash
git clone <repo-url>
cd regalloc-a5
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Parse a program and dump its CFG and liveness
python -m src.cli benchmarks/simple.tac --dump-cfg --dump-live

# Full allocation: parse -> CFG -> liveness -> interference -> coalesce -> colour
# -> spill and retry if K isn't enough -> final allocated program
python -m src.cli benchmarks/simple.tac --k 8

# Force spilling to see the rewrite/retry loop in action
python -m src.cli benchmarks/high_pressure.tac --k 4

# Write the interference graph out as Graphviz DOT (render with `dot -Tpng`)
python -m src.cli benchmarks/briggs_example.tac --k 3 --dump-graph graph.dot

# Show every intermediate stage: coalescing candidates/verdicts, spill before/after,
# and a structured metrics summary (see "Metrics" below)
python -m src.cli benchmarks/copy_heavy.tac --k 4 --dump-coalesce --dump-spill --metrics

# Run the tests
pytest -v
```

The full pipeline is implemented and working end to end — parsing, CFG/loop-depth
construction, liveness, interference-graph construction, Briggs coalescing,
simplify/select colouring, and the spill/rewrite/retry loop. `pytest -v` runs 139
tests covering all of it (87 from the original Review 2 implementation, 52 added for
the metrics/benchmarking/web-dashboard work below — see [Testing](#testing)).

---

## The IR we accept

A plain-text three-address code. One instruction per line, `#` starts a comment.

```
func main
  t1 = 1              # constant load
  t2 = 2
  t3 = t1 + t2        # binary op:  dst = src1 OP src2
  t4 = t3             # copy — coalescing candidate
label L1
  t5 = t4 * 2
  if t5 < 100 goto L1 # conditional branch
  ret t5
end
```

Supported forms:

| Form | Example | Meaning |
|---|---|---|
| `dst = const` | `t1 = 5` | load a constant |
| `dst = src` | `t2 = t1` | copy (coalescing candidate) |
| `dst = src1 OP src2` | `t3 = t1 + t2` | binary operation |
| `label NAME` | `label L1` | branch target |
| `goto NAME` | `goto L1` | unconditional jump |
| `if src REL src goto NAME` | `if t5 < 100 goto L1` | conditional jump |
| `ret src` | `ret t5` | return |
| `func NAME` / `end` | | function boundaries |

Operators: `+ - * / %`  ·  Relations: `< <= > >= == !=`

Virtual registers are any identifier starting with `t` followed by digits. Anything else
in an operand position is treated as a literal constant.

---

## Repository layout

```
regalloc-a5/
├── src/
│   ├── ir.py                  shared data types (Instr, BasicBlock, Function)
│   ├── cli.py                 command-line entry point
│   ├── metrics.py             AllocationMetrics — single source of truth for numbers
│   ├── frontend/              M1 — parser, CFG construction, loop depth
│   ├── analysis/              M2 — liveness dataflow, interference graph
│   ├── colouring/             M3 — coalescing, simplify, select
│   └── spilling/              M4 — spill cost model, code rewriter
├── api/index.py                FastAPI backend for the web demo (also the Vercel entry point)
├── public/                     static frontend (tabbed dashboard) served by api/index.py or Vercel
├── scripts/
│   ├── dev_server.py           run api/ + public/ together locally (no Vercel CLI needed)
│   ├── run_benchmarks.py       run every benchmark across a K sweep, emit JSON/CSV
│   ├── coalescing_experiment.py  coalescing ON vs OFF on one benchmark, emit JSON/CSV
│   ├── plot_results.py         matplotlib plots from those CSVs (K-vs-spills, ON/OFF)
│   └── demo.py                 compact faculty-facing walkthrough of one run
├── results/                     generated JSON/CSV/PNG from the scripts above (gitignored)
├── tests/                      pytest suites, one per module/feature
├── benchmarks/                 .tac test inputs
├── docs/                       architecture notes, diagrams, report
└── .github/workflows/ci.yml    runs pytest on every push
```

Modules communicate through the shared classes in `src/ir.py` and
`src/analysis/interference.py`. Each module can be tested in isolation, so all four
members can work in parallel. `src/metrics.py` is the one place that reads those
structures to produce reportable numbers — the CLI, the web API, and every script
under `scripts/` all call into it rather than each computing their own counts.

---

## Module ownership

| Module | Owner | Responsibility | Status |
|---|---|---|---|
| `frontend/` | M1 — \_\_\_\_\_\_ | Tokenize, parse, build CFG, compute loop depth | Done |
| `analysis/` | M2 — \_\_\_\_\_\_ | Live-variable dataflow, interference graph | Done |
| `colouring/` | M3 — \_\_\_\_\_\_ | Briggs coalescing, simplify, select | Done |
| `spilling/` | M4 — \_\_\_\_\_\_ | Spill cost, candidate choice, code rewriting, retry loop | Done |

Every module has a named secondary reviewer so no component has a single point of failure.

---

## How we work

- One branch per module: `m1-frontend`, `m2-analysis`, `m3-colouring`, `m4-spilling`.
- Every merge goes through a pull request reviewed by one other member.
- CI runs `pytest` on every push; the suite must pass before merging.
- M4 owns the `main` branch and the regression suite.

---

## Algorithm

Chaitin–Briggs, in six stages:

1. **Parse** the IR, build the control-flow graph, record loop nesting depth.
2. **Liveness** — backward dataflow to a fixed point:
   `OUT[B] = ⋃ IN[S] for successors S`, `IN[B] = USE[B] ∪ (OUT[B] − DEF[B])`.
3. **Build** the interference graph from the live ranges.
4. **Coalesce** copies using Briggs' conservative test: merge `a` and `b` only if the
   merged node has fewer than K neighbours of significant degree. This can never create
   an uncolourable node.
5. **Simplify and select.** Push every node of degree `< K` onto a stack — such a node is
   always colourable, since its neighbours can use at most `K−1` colours between them.
   *Briggs' contribution:* when every remaining node has degree `≥ K`, push one
   optimistically rather than spilling it outright, because a high-degree node is often
   still colourable. Then pop each node and give it a colour its neighbours are not using.
   A node with no free colour becomes an **actual spill**.
6. **Spill** the candidate minimising `cost / degree`, where
   `cost = Σ 10^(loop depth)` over all definitions and uses. Insert stores and reloads,
   then rebuild and re-run from step 1.

The loop terminates because each iteration removes at least one live range from
contention and the replacement ranges are very short. Capped at 10 iterations
(`spilling.spiller.MAX_ITERATIONS`).

---

## Metrics

`src/metrics.py` defines `AllocationMetrics`, one dataclass covering everything worth
reporting about a run: input size, CFG shape, interference-graph shape, coalescing
candidates/merges/refusals, spill counts, iterations, and the final result. Every
number in it is read directly off the real `Function`/`InterferenceGraph`/
`AllocationResult`/`PipelineResult` objects the pipeline already produces — nothing is
recomputed by hand in more than one place.

```bash
# print the metrics for one run
python -m src.cli benchmarks/copy_heavy.tac --k 4 --metrics

# or save them as JSON
python -m src.cli benchmarks/copy_heavy.tac --k 4 --metrics-json results/one_run.json
```

The web API returns the same structure under the `metrics` key of `/api/analyze`'s
response, and every script below reuses `src.metrics.run_and_collect_metrics` to
produce its rows.

Graph-structure fields (`num_interference_nodes`, `num_coalescing_merges`, etc.)
describe the *first* allocation attempt — the original program's interference
problem, before any spill rewriting changed the code. Outcome fields
(`num_spilled_vregs`, `num_retry_iterations`, `num_final_instructions`, etc.)
describe the pipeline's *last* attempt, i.e. what it actually returned. See the
module docstring for why those are deliberately different snapshots.

---

## Benchmarks and experiments

### The benchmark set

```
simple            5 values, 3 registers needed — the smallest non-trivial case
diamond           branch + join, exercises liveness merging at a join point
loop              a single loop — loop_depth-weighted spill cost
nested_loop       loop inside a loop — depth-2 (100x) spill cost
briggs_example    hand-worked fixture from Briggs et al. (1994), used as a regression pin
high_pressure     8 values live at once — forces a spill at K < 8
copy_heavy        8-value cluster through 4 safe copy pairs, plus a 3-hop copy chain —
                  built specifically to exercise coalescing under real register
                  pressure (see "Coalescing ON vs OFF" below)
```

`copy_heavy.tac` needs K ≥ 4 to succeed (it is not colourable at K = 2 or 3 even with
coalescing) — unlike the other six benchmarks, which all succeed at K ≥ 2. That is
expected, not a bug: it is what "real register pressure" in the benchmark's own
docstring means.

### Benchmark runner (K-scaling experiment)

```bash
python scripts/run_benchmarks.py                                    # K = 1, 2, 3, 4, 8 (default)
python scripts/run_benchmarks.py --k 1 2 3 4 8 12
python scripts/run_benchmarks.py --json results/benchmark_results.json --csv results/benchmark_results.csv
python scripts/run_benchmarks.py --no-coalesce                      # O3 baseline comparison
```

Runs every `.tac` file in `benchmarks/` at each requested K through the real
pipeline, prints a table (Benchmark / K / Status / Spills / Loads / Stores /
Iterations / Merges), and can also emit JSON/CSV for `scripts/plot_results.py` or
external analysis. An invalid K (`< 1`) or a parse error is reported as a row with
that status, not a crash. K = 1 is expected to `FAIL` on every benchmark (see below).

### Coalescing ON vs OFF experiment

```bash
python scripts/coalescing_experiment.py                              # copy_heavy.tac, K = 2..8
python scripts/coalescing_experiment.py --benchmark benchmarks/copy_heavy.tac --k 2 4 6 8
python scripts/coalescing_experiment.py --json results/coalescing_results.json \
                                         --csv results/coalescing_results.csv
```

Runs the same benchmark at the same K twice — once with coalescing enabled, once with
`do_coalesce=False` (the flag `--no-coalesce` maps to) — and reports the difference:
candidates, successful merges, refusals, redundant-move detections, and spill
loads/stores/iterations for both. **Honest result on `copy_heavy.tac`:** coalescing
does perform real merges (3 of 7 candidates at K = 4–6, all 7 at K = 8) and increases
the number of copy instructions provably rendered redundant (same register on both
sides), but it does **not** reduce the spill count at any tested K for this
benchmark — the merged cluster's degree is still high enough to need the same number
of spills either way. This allocator assigns registers; it does not rewrite the
instruction stream to delete now-redundant copies, so "copies before" and "copies
after" are also equal by construction. The script prints this finding rather than
manufacturing an improvement — see `DO NOT FABRICATE RESULTS` in the project brief.

### K-vs-spill plots

```bash
python scripts/run_benchmarks.py --csv results/benchmark_results.csv
python scripts/coalescing_experiment.py --csv results/coalescing_results.csv
python scripts/plot_results.py    # reads those two CSVs, writes results/*.png
```

`scripts/plot_results.py` never runs the allocator itself — it only reads the CSVs
the two scripts above already produced, with matplotlib, and writes
`results/k_vs_spills.png` (spill count vs. K, one line per benchmark) and
`results/coalescing_on_off.png` (spills ON vs OFF, and merges accepted per K).

### Faculty demo

```bash
python scripts/demo.py                                              # high_pressure.tac, K=2
python scripts/demo.py --benchmark benchmarks/copy_heavy.tac --k 4
```

A compact, stage-by-stage walkthrough of one real run (parse → CFG → liveness →
interference → coalescing → colouring → spilling → verification), ending in a
metrics summary, the final register mapping, and a verification checklist that only
shows a checkmark when `AllocationResult.verify()` actually passed. See
"Faculty demonstration" below for the full script.

---

## Web demo

You can try the full pipeline directly in your browser:
**🚀 Live Web App:** [https://graph-coloring-register-allocator.vercel.app/](https://graph-coloring-register-allocator.vercel.app/)

`api/index.py` is a FastAPI app (also the Vercel serverless entry point via
`vercel.json`) that runs the same real pipeline and returns, in one response: the
parsed TAC, every iteration's CFG/liveness/interference/coalescing/spilling detail,
the final allocation, the `AllocationMetrics`, and a verification block.
`public/` is a static, dependency-light dashboard with one tab per stage (Input, CFG,
Liveness, Interference Graph, Coalescing, Registers, Spills, Metrics, Final Output,
Verification) that reads that response — it does not recompute anything itself. The
CFG tab renders a small dependency-free box-and-arrow view straight from the
backend's block list (so it always works) plus a Graphviz rendering when the
`d3-graphviz`/WASM CDN scripts are reachable.

```bash
python scripts/dev_server.py                # serves public/ and /api on localhost:8000
python scripts/dev_server.py --port 8080
```

Then open the printed URL, paste or pick a benchmark, set K and the coalescing
checkbox, and click **Parse & Analyze**.

---

## Testing

```bash
pytest -v
```

139 tests. The original 87 (`test_parser.py`, `test_cfg.py`, `test_liveness.py`,
`test_interference.py`, `test_colouring.py`, `test_spilling.py`) are unchanged and
still all pass — see [Regression protection](#regression-protection). 52 more were
added for this round of work:

| File | Covers |
|---|---|
| `test_metrics.py` | `AllocationMetrics` field-by-field against hand-traced benchmarks, the candidates = merged + refused invariant, spill-metric consistency with `count_spill_instructions`, and that a failed allocation reports failure rather than faking success |
| `test_coalesce_stats.py` | The `coalesce()`/`allocate()` instrumentation itself (candidate/merged/refused counters and the per-pair accepted/refused trace), backward compatibility of the old `coalesce(graph, k)` call form |
| `test_copy_heavy_benchmark.py` | `benchmarks/copy_heavy.tac` parses, contains the designed copy pairs, forces a real spill at low K, and converges to a verified allocation with coalescing both on and off |
| `test_benchmark_runner.py` | `scripts/run_benchmarks.py` executes every benchmark, handles an invalid K without crashing, and produces the documented result schema/JSON/CSV |
| `test_cli.py` | Every existing CLI flag continues to behave as before, plus `--dump-coalesce`, `--dump-spill`, `--metrics`, `--metrics-json` |
| `test_api.py` | `/api/analyze` on straight-line/branch/loop/spill-heavy input, that CFG → liveness → interference still run in that order (the regression the module docstring describes), the new `stages`/`metrics`/`verification` fields, and that verification never claims success on a genuine failure |
| `test_interference.py` (additions) | The new `InterferenceGraph.edges()` public accessor |

Coverage from the original suite includes: straight-line/branch/loop/nested-loop CFGs
and predecessor/successor consistency across every benchmark; use/def and
fixed-point liveness including a diamond join; the interference graph against a
hand-verified edge set (see the correction note below); simplify/select at K = 1..4
including the "optimistic push beats naive Chaitin" case; Briggs coalescing (both a
safe merge and a correctly-refused interfering one); spill cost and its loop-depth
weighting; `choose_spill`'s cost/degree ratio, including the degree-0 guard;
fresh-name reload generation; a regression test for a slot-numbering bug the
spill/retry loop used to have (below); and full-pipeline convergence on every
benchmark.

### Regression protection

Nothing above changed the pre-existing algorithms — every new field on
`AllocationResult` (`coalesce_stats`, `coalesce_trace`) defaults to a zero/empty
value and every new function parameter (`coalesce()`'s `stats`/`trace`) defaults to
`None`, so the original 87 tests exercise the exact same code paths they always did.
In particular, these stay intact and still pinned by tests: the corrected 9-edge
`briggs_example.tac` interference graph, the spill/retry loop's non-convergence guard
(`MAX_ITERATIONS`), degree-0 spill-candidate handling, fresh-name reload generation,
safe-vs-refused Briggs coalescing, and CFG → liveness → interference ordering.

## Try it against every benchmark

```bash
for f in benchmarks/*.tac; do
  for k in 1 2 3 4 8; do
    python -m src.cli "$f" --k "$k"
  done
done
```

Or, with structured output instead of eyeballing the CLI text:

```bash
python scripts/run_benchmarks.py --k 1 2 3 4 8
```

K = 1 is expected to fail on every benchmark here — architecturally, not as a bug: our
IR's binary operations and `if..goto` always need two operands live at once, so no
amount of spilling can make one register enough. Every original benchmark succeeds at
K ≥ 2; `copy_heavy.tac` (added for the coalescing experiment) needs K ≥ 4 by design —
see [Benchmarks and experiments](#benchmarks-and-experiments).

## Design notes (found while implementing)

Two things came up during implementation that are worth knowing about before the viva,
because they are the kind of question a reviewer is likely to ask:

1. **The hand-worked `briggs_example` interference graph in
   `docs/briggs_example_solution.md` was missing an edge** (`t2`–`t4`). `t2` stays live
   from its own definition until `t5 = t2 + t3`, which is *after* `t4 = t1 + t3` — so
   `t2` and `t4` are simultaneously live and must interfere, even though neither
   instruction mentions the other. The doc now has a correction note, and
   `tests/test_interference.py::test_briggs_example_edge_set_matches_the_worked_example`
   pins down the verified 9-edge graph.

2. **A naive "spend cost information everywhere" instinct can break termination.**
   `colouring.allocator.simplify` accepts an optional `cost_fn` so its optimistic push
   can prefer the *cheapest* node instead of just the highest-degree one. Wiring
   `spill_cost` into the main pipeline this way looks strictly better — until it hits
   `briggs_example.tac` at K = 2: a single long-lived value is both the true source of
   register pressure *and* the most expensive node to spill, so a cost-biased push
   protects it forever and the loop thrashes on cheap, doomed reload temporaries
   instead, never converging (verified out to 40 rounds). Dropping the cost bias and
   using plain highest-degree converges in 4 rounds on the same input. `spiller.py`'s
   module docstring has the full writeup; `run_allocation` calls `allocate()` without a
   `cost_fn` for exactly this reason, even though `cost_fn` remains available for
   experimentation.

Both are explained in more detail right next to the material they concern — the first
in `docs/briggs_example_solution.md`'s correction note, the second in
`src/spilling/spiller.py`'s module docstring — specifically so they're easy to find and
explain rather than being buried in a commit message.

---

## Reproducibility

Every number in this README, in the web dashboard, or in `results/*.json`/`*.csv` was
produced by actually running the code in this repository — none of it is hand-typed
or simulated. To regenerate all of it from a clean checkout:

```bash
pip install -r requirements.txt
pytest -v                                                            # 139 passed
python scripts/run_benchmarks.py --json results/benchmark_results.json \
                                  --csv results/benchmark_results.csv
python scripts/coalescing_experiment.py --json results/coalescing_results.json \
                                         --csv results/coalescing_results.csv
python scripts/plot_results.py
python scripts/demo.py
```

`results/` is gitignored (same convention as the existing `*.dot`/`*.png` rule) since
it is entirely regenerable from the commands above — nothing under it is a source of
truth, `src/`, `benchmarks/` and the tests are.

---

## References

1. Chaitin, G. J. *Register allocation and spilling via graph coloring.* SIGPLAN, 1982.
2. Briggs, P., Cooper, K. D., Torczon, L. *Improvements to graph coloring register
   allocation.* ACM TOPLAS 16(3), 1994.
3. George, L., Appel, A. W. *Iterated register coalescing.* ACM TOPLAS 18(3), 1996.
4. Appel, A. W., Palsberg, J. *Modern Compiler Implementation in Java*, 2nd ed., Ch. 11.
5. Aho, Lam, Sethi, Ullman. *Compilers: Principles, Techniques and Tools*, 2nd ed., Ch. 8.
