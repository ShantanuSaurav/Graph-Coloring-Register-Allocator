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
t3 — t4
t4 — t5
t5 — t6
t5 — t7
t6 — t4
```

Degrees: t1=2, t2=2, t3=3, t4=3, t5=3, t6=2, t7=1, t8=0

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

## TODO for M2 and M3

Once `build_graph` is implemented, add a test asserting the edge set above matches
exactly. That single test validates the whole liveness pipeline.
