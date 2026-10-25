# Student's guide to Register Lab

## Getting started

1. Install Python dependencies and run `python scripts/dev_server.py`.
2. Open `http://127.0.0.1:8000`.
3. Click an example, choose register count **K**, then click **Run analysis**.
4. Select a compiler stage and, for spilled programs, choose a different **Round**.

## Four concepts to remember

- **Control-flow graph (CFG)**: basic blocks linked by possible branches and jumps.
- **Liveness**: a variable is live when its value could be read later. Block IN and OUT alone do not show liveness between adjacent instructions. Use the instruction-level table.
- **Interference graph**: an edge means two virtual-register live ranges conflict and must get different colors.
- **Graph coloring**: each color represents one register R0–R(K−1). Under pressure, the allocator spills values to numbered memory slots and retries.

## Important controls

| Action | Result |
|---|---|
| Set K | Changes the number of physical colors. It does *not* directly change original source liveness. |
| Enable coalescing | Tries to combine copy-related registers without introducing unsafe interference. |
| Select round | Views the CFG, liveness and interference for that particular allocation iteration. |
| Click a graph node | Inspects neighbors, graph degree, and register assignment. |
| Save SVG | Exports the displayed component/CFG as a vector image. |
| Export JSON | Downloads all raw compiler stages and verification results. |
| Complexity / Register budget | Holds TAC fixed while running the allocator at multiple K settings. |
| Complexity / Input size | Holds K fixed while increasing a synthetic TAC chain. |
| Register banks | Displays physical register groups as boxes, not hardware memory segments. |

## Example

```text
func main
  t1 = 4
  t2 = 7
  t3 = t1 + t2
  ret t3
end
```

The first two virtual registers are live simultaneously before `t3 = t1 + t2`. They interfere and require different colors in a two-register allocation. The other live ranges can reuse a register.

## Failure and safety conditions

For **K=1**, some instructions need two independent register operands; the instructional allocator cannot legalize them into target-specific memory-operand instructions. Such programs can reach the retry limit. With **K≥2**, the normal spill heuristic can struggle with particular graphs; the engine has a final conservative all-live-range-spill fallback. That fallback is correct for the tested bounded TAC programs but increases loads/stores, so it should not be presented as efficient machine-code generation.

A **Verified** status requires both an interference-consistent coloring and a completed comparison using the reference TAC interpreter. Programs that are nonterminating, have undefined virtual values, or exceed interpreter step limits cannot receive full semantic verification.

## Trouble-shooting

- **Graph absent**: run the analysis again; check whether an error appears in the result panel. Nodes without edges are drawn as isolated nodes by design.
- **Liveness appears unchanged after adjusting K**: that is normal for the same source TAC; inspect later rewrite rounds to see altered liveness.
- **Example cannot load after deployment**: open `/examples/simple.tac` directly and confirm Vercel serves bundled public assets.
- **API request fails**: inspect the browser Network tab for `/api/analyze`, then check the Vercel serverless function logs.
- **Charts vary between runs**: Python wall time and traced allocations are sensitive to server load; use repeated trials and report the environment.
