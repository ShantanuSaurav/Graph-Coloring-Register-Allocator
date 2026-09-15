"""M4 — spill cost model, code rewriting, and the spill/retry pipeline.

Owner: Member 4
Status: implemented.

WHAT SPILLING IS
----------------
When K registers are not enough, some value has to live in memory instead. The program
still computes the right answer; it just runs slower, because every read becomes a load
from the stack and every write becomes a store.

WHICH VALUE TO SPILL
--------------------
Not the one used constantly. We pick the candidate that minimises

    cost / degree

where

    cost = sum over every definition and use of  10 ** loop_depth(that instruction)

The loop-depth weighting is the important part: an instruction inside one loop is
counted 10x, inside a nested loop 100x. So a value used in a hot loop is enormously
expensive to spill, and a value used once at the end of a function is cheap.

Dividing by degree favours spilling a node that relieves pressure on many neighbours —
one spill that unblocks ten nodes beats one that unblocks two. This same cost/degree
ratio is what `colouring.allocator.simplify` uses (via its optional `cost_fn`) to choose
which node to push optimistically when it gets stuck, so the two modules share one idea
of "how expensive is this vreg".

WHAT REWRITING DOES
-------------------
For a spilled vreg v, allocate a stack slot, then:
  - after every instruction that defines v, insert  `store slot, v`
  - before every instruction that uses v,  insert   `v' = load slot`  with a FRESH
    vreg name for each use

Using a fresh name per use is what makes this terminate: the new live ranges are only
one or two instructions long, so they interfere with almost nothing and colour easily.
Reusing the same name would leave a long live range and the loop could spin forever.

Then the whole pipeline runs again: rebuild the CFG, recompute liveness, rebuild the
interference graph, allocate again. `run_allocation` below is that loop.

A NOTE ON cost_fn AND TERMINATION
----------------------------------
`colouring.allocator.simplify` optionally accepts a `cost_fn`, so its optimistic push
can prefer the *cheapest* node (lowest cost/degree, the same ratio `choose_spill` uses)
instead of just the highest-degree one. It looks like a strict improvement — why ever
sacrifice an expensive node when a cheap one is available? — but wiring `spill_cost`
straight into it turned out to break termination on `benchmarks/briggs_example.tac` at
K=2: a single long-lived value (`t5`, live from its own definition all the way to the
final `ret`) is exactly the node whose spill would relieve the pressure, but it is also
the *most expensive* one, so a cost-biased optimistic push always protects it and pushes
some cheap, freshly-created reload temporary instead. That temporary gets spilled,
rewritten, and immediately replaced by an equally cheap, equally doomed one next round —
the real bottleneck (`t5`) is never touched, and the loop never converges (confirmed by
running it 40 rounds deep without success). Dropping the cost bias and using plain
highest-degree — the heuristic `colouring.allocator.simplify` suggests as its default —
converges on the same benchmark in 4 rounds, because a persistently high-degree node
now *is* eventually the one pushed optimistically.

So `run_allocation` below always calls `allocate()` without a `cost_fn`. The parameter
stays available on `simplify`/`allocate` for experimentation, but this pipeline does not
use it, precisely because guaranteeing the spill loop terminates matters more than
occasionally picking a marginally cheaper spill.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from src.analysis.interference import InterferenceGraph, build_graph
from src.analysis.liveness import analyse
from src.colouring.allocator import AllocationResult, allocate
from src.frontend.cfg import build_cfg, compute_loop_depth
from src.ir import Function, Instr, Op, is_vreg

MAX_ITERATIONS = 10  # safety cap from our risk register


def spill_cost(fn: Function, vreg: str) -> float:
    """Estimated dynamic cost of spilling `vreg`.

    cost = sum over every block, every instruction, of 10**block.loop_depth for each
    definition or use of `vreg` in that instruction (an instruction that both defines
    and uses it, like `t1 = t1 + 1`, counts both occurrences).

    Depends on `compute_loop_depth` having already filled in `block.loop_depth`.
    """
    total = 0.0
    for block in fn.block_order():
        weight = 10.0 ** block.loop_depth
        for instr in block.instrs:
            occurrences = (vreg in instr.defs()) + (vreg in instr.uses())
            total += occurrences * weight
    return total


def choose_spill(fn: Function, graph: InterferenceGraph, candidates: set[str]) -> str:
    """Pick the cheapest candidate to spill, by cost / degree.

    Guards against degree 0 (an isolated node cannot really need spilling, but we
    still must not divide by zero if asked about one). Ties are broken by vreg name
    so the choice is deterministic.
    """
    if not candidates:
        raise ValueError("choose_spill: no candidates given")

    def ratio(vreg: str) -> tuple[float, str]:
        degree = max(graph.degree(vreg), 1)
        return (spill_cost(fn, vreg) / degree, vreg)

    return min(candidates, key=ratio)


def _flat_instrs(fn: Function) -> list[Instr]:
    """The function's instructions in source order, whether or not the CFG has run."""
    if fn.blocks:
        return [instr for block in fn.block_order() for instr in block.instrs]
    return list(getattr(fn, "_parsed_instrs", None) or [])


def _next_temp_number(fn: Function) -> int:
    numbers = [int(v[1:]) for v in fn.all_vregs() if is_vreg(v)]
    return max(numbers, default=0) + 1


def _next_slot_number(fn: Function) -> int:
    """One past the highest stack slot already used by a LOAD/STORE in `fn`.

    Spilling can run for several rounds (PART 12): each round rewrites the function
    produced by the previous one, so earlier rounds' LOAD/STORE instructions are still
    sitting in the instruction stream. Slot numbers must not restart at 0 each round —
    that would let a new spill's store silently clobber a slot an earlier round's load
    hasn't consumed yet.
    """
    used = [instr.slot for instr in _flat_instrs(fn)
            if instr.op in (Op.LOAD, Op.STORE) and instr.slot is not None]
    return (max(used) + 1) if used else 0


def rewrite_with_spills(fn: Function, spilled: set[str]) -> Function:
    """Return a new Function with loads and stores inserted for every spilled vreg.

    Each spilled vreg gets its own stack slot. Walking the instructions in order:
      - a use of a spilled v becomes `fresh = load slot` inserted immediately before,
        with the instruction rewritten to read `fresh` instead of `v`;
      - a def of a spilled v is left writing `v`, followed immediately by `store slot, v`.

    Every inserted load gets a brand new vreg name (never reused), which keeps the new
    live ranges tiny. The result has a flat `_parsed_instrs` list, ready to go back
    through `build_cfg` — block boundaries cannot have shifted, since LOAD/STORE are
    never branches, but rebuilding from scratch is simpler to reason about and matches
    the rest of the pipeline, which always re-derives the CFG after a rewrite.
    """
    instrs = _flat_instrs(fn)
    if not spilled:
        out = Function(name=fn.name)
        out._parsed_instrs = list(instrs)  # type: ignore[attr-defined]
        return out

    base_slot = _next_slot_number(fn)
    slots = {vreg: base_slot + i
             for i, vreg in enumerate(sorted(spilled, key=lambda v: int(v[1:])))}
    next_temp = _next_temp_number(fn)

    def fresh_temp() -> str:
        nonlocal next_temp
        name = f"t{next_temp}"
        next_temp += 1
        return name

    new_instrs: list[Instr] = []
    for instr in instrs:
        current = instr
        for field_name in ("src1", "src2"):
            operand = getattr(current, field_name)
            if operand is not None and operand in spilled and operand in current.uses():
                temp = fresh_temp()
                new_instrs.append(Instr(Op.LOAD, current.line, dst=temp, slot=slots[operand]))
                current = replace(current, **{field_name: temp})
        new_instrs.append(current)
        if current.dst is not None and current.dst in spilled and current.dst in current.defs():
            new_instrs.append(Instr(Op.STORE, current.line, src1=current.dst, slot=slots[current.dst]))

    out = Function(name=fn.name)
    out._parsed_instrs = new_instrs  # type: ignore[attr-defined]
    return out


def count_spill_instructions(fn: Function) -> int:
    """Count LOAD and STORE instructions — the metric for objective O3."""
    return sum(1 for instr in _flat_instrs(fn) if instr.op in (Op.LOAD, Op.STORE))


@dataclass
class PipelineResult:
    """Everything the full allocate/spill/retry loop produced."""

    function: Function                 # final IR (with any load/store rewrites)
    graph: InterferenceGraph           # interference graph of the final attempt
    allocation: AllocationResult       # colouring/spill result of the final attempt
    iterations: int                    # how many allocate-then-maybe-spill rounds ran
    spilled_history: list[set[str]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.allocation.success


def run_allocation(
    fn: Function,
    k: int,
    do_coalesce: bool = True,
    max_iterations: int = MAX_ITERATIONS,
    on_iteration=None,
) -> PipelineResult:
    """Run the complete pipeline, spilling and retrying until it succeeds or gives up.

    Each round:
      1. build_cfg + compute_loop_depth       (src.frontend.cfg)
      2. analyse                              (src.analysis.liveness)
      3. build_graph                          (src.analysis.interference)
      4. allocate                             (src.colouring.allocator)
      5. if there are actual spills, rewrite_with_spills and go around again.

    `on_iteration(iteration, function, graph, result)`, if given, is called after each
    round's allocate() — useful for a CLI to print per-round progress without this
    module needing to know anything about printing.

    Stops as soon as an allocation succeeds, or after `max_iterations` rounds — at
    which point the (still failing) result of the last round is returned rather than
    looping forever, so a caller can always tell success from failure by checking
    `.success` instead of the pipeline hanging.
    """
    current = fn
    spilled_history: list[set[str]] = []
    result: AllocationResult | None = None
    graph: InterferenceGraph | None = None

    for iteration in range(1, max_iterations + 1):
        build_cfg(current)
        compute_loop_depth(current)
        analyse(current)
        graph = build_graph(current)

        # Deliberately NOT passing a cost_fn here — see the module docstring's note
        # on why the plain highest-degree optimistic heuristic is the safe default.
        result = allocate(graph, k, do_coalesce=do_coalesce)

        if on_iteration is not None:
            on_iteration(iteration, current, graph, result)

        if result.success:
            return PipelineResult(current, graph, result, iteration, spilled_history)

        spilled_history.append(set(result.spilled))
        current = rewrite_with_spills(current, result.spilled)

    assert result is not None and graph is not None  # loop always runs >= 1 time
    return PipelineResult(current, graph, result, max_iterations, spilled_history)
