# Contribution log

Required by the Review 1 checklist: meeting date, task assigned, task completed, evidence.

| Date | Attending | Task assigned | Owner | Completed | Evidence |
|---|---|---|---|---|---|
| | | Repository setup, IR grammar | M1 | | commit hash |
| | | Literature survey table | M2 | | docs/ |
| | | Architecture diagram | M3 | | docs/architecture.md |
| | | Test plan draft | M4 | | tests/ |

## Team responsibility matrix

| Member | Primary (technical) | Supporting | Review 1 evidence | Review 2 target | Review 3 target |
|---|---|---|---|---|---|
| M1 | IR parser, CFG, loop depth | Repo & README owner | Grammar, working parser | CFG + loop depth done | Integration support |
| M2 | Liveness, interference graph | Survey, Graphviz output | Survey table, worked example | Graph built and rendered | Benchmarking support |
| M3 | Coalesce, simplify, select | Architecture, algorithm review | Pseudocode, architecture | Colouring works at K=8 | Coalescing tuned |
| M4 | Spill cost, rewriter, harness | CI, integration, Gantt | Test plan, repo structure | Spill loop working | O3 measurement |

Signed by all members: ______________  ______________  ______________  ______________
