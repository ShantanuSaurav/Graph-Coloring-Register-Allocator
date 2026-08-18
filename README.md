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

# Parse a program and dump its CFG (this part works today)
python -m src.cli benchmarks/simple.tac --dump-cfg

# Full allocation (once the analysis and colouring modules are implemented)
python -m src.cli benchmarks/simple.tac --k 8

# Run the tests
pytest -v
```

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
│   ├── frontend/              M1 — parser, CFG construction, loop depth
│   ├── analysis/              M2 — liveness dataflow, interference graph
│   ├── colouring/             M3 — coalescing, simplify, select
│   └── spilling/              M4 — spill cost model, code rewriter
├── tests/                     pytest suites, one per module
├── benchmarks/                .tac test inputs
├── docs/                      architecture notes, diagrams, report
└── .github/workflows/ci.yml   runs pytest on every push
```

Modules communicate through the shared classes in `src/ir.py` and
`src/analysis/interference.py`. Each module can be tested in isolation, so all four
members can work in parallel.

---

## Module ownership

| Module | Owner | Responsibility | Status |
|---|---|---|---|
| `frontend/` | M1 — \_\_\_\_\_\_ | Tokenize, parse, build CFG, compute loop depth | Parser done; CFG in progress |
| `analysis/` | M2 — \_\_\_\_\_\_ | Live-variable dataflow, interference graph | Not started |
| `colouring/` | M3 — \_\_\_\_\_\_ | Briggs coalescing, simplify, select | Not started |
| `spilling/` | M4 — \_\_\_\_\_\_ | Spill cost, candidate choice, code rewriting | Not started |

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
contention and the replacement ranges are very short. Capped at 10 iterations.

---

## References

1. Chaitin, G. J. *Register allocation and spilling via graph coloring.* SIGPLAN, 1982.
2. Briggs, P., Cooper, K. D., Torczon, L. *Improvements to graph coloring register
   allocation.* ACM TOPLAS 16(3), 1994.
3. George, L., Appel, A. W. *Iterated register coalescing.* ACM TOPLAS 18(3), 1996.
4. Appel, A. W., Palsberg, J. *Modern Compiler Implementation in Java*, 2nd ed., Ch. 11.
5. Aho, Lam, Sethi, Ullman. *Compilers: Principles, Techniques and Tools*, 2nd ed., Ch. 8.
