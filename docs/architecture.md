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

Compare `count_spill_instructions` on the two outputs. The target is a 20% reduction.
