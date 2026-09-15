# Hand-worked solution: benchmarks/briggs_example.tac

Worked by the team before implementation, so we have a known-correct answer to test
`build_graph` and `allocate` against. Adapted from the example in Briggs et al. (1994).

## The program

```
t1 = 1
t2 = 2
t3 = t1 + t2
t4 = t1 + t3
t5 = t2 + t3
t6 = t4 + t5
t7 = t4 + t6
t8 = t5 + t7
ret t8
```

## Live ranges

| vreg | live from | live until |
|---|---|---|
| t1 | after `t1 = 1` | its use in `t4 = t1 + t3` |
| t2 | after `t2 = 2` | its use in `t5 = t2 + t3` |
| t3 | after `t3 = ...` | its use in `t5 = t2 + t3` |
| t4 | after `t4 = ...` | its use in `t7 = t4 + t6` |
| t5 | after `t5 = ...` | its use in `t8 = t5 + t7` |
| t6 | after `t6 = ...` | its use in `t7 = t4 + t6` |
| t7 | after `t7 = ...` | its use in `t8 = t5 + t7` |
| t8 | after `t8 = ...` | `ret t8` |

## Expected interference edges

```
t1 — t2
t1 — t3
t2 — t3
t2 — t4
t3 — t4
t4 — t5
t5 — t6
t5 — t7
t6 — t4
```

Degrees: t1=2, t2=3, t3=3, t4=4, t5=3, t6=2, t7=1, t8=0

**Correction (post-implementation):** the table above originally omitted the `t2 — t4`
edge. Walking the liveness by hand: `t2` is defined by `t2 = 2` and not used again
until `t5 = t2 + t3`, so it is live across everything in between — including
`t4 = t1 + t3`, which sits right before it. `t4` is defined at that exact point. Two
values simultaneously live at the same program point must interfere by definition, so
`t2` and `t4` do interfere, even though neither instruction mentions the other by
name. `build_graph`'s standard construction (walk each block backwards, add an edge
from every definition to everything currently live) finds this edge; the original
hand trace missed it because it only looked at each instruction's own operands, not
everything still live around it. `tests/test_interference.py::test_briggs_example_edge_set_matches_the_worked_example`
checks the corrected 9-edge set exactly. The K = 3 and K = 2 conclusions below are
unaffected — K = 3 still colours cleanly (verified by
`tests/test_colouring.py`) and K = 2 still forces a spill.

## Expected result at K = 3

Colourable without spilling. One valid assignment:

| vreg | register |
|---|---|
| t1 | R0 |
| t2 | R1 |
| t3 | R2 |
| t4 | R0 |
| t5 | R1 |
| t6 | R2 |
| t7 | R0 |
| t8 | R0 |

Any assignment satisfying the edge constraints is acceptable — the test should call
`AllocationResult.verify()` rather than compare against this exact table, since the
choice among free colours is arbitrary.

## Expected result at K = 2

Not 2-colourable: t1, t2 and t3 form a triangle. At least one node must spill. Under our
cost model the cheapest candidate should be the one with the lowest cost/degree ratio.

## Status

`build_graph` is implemented and `tests/test_interference.py` asserts the (corrected)
edge set above matches exactly, so this fixture now validates the whole
parse -> CFG -> liveness -> interference pipeline in one test.
