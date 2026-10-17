"""M3 — the colouring engine: coalescing, simplify and select.

Owner: Member 3
Status: implemented. AllocationResult was provided from the start.

THE IDEA
--------
Assigning registers is exactly graph colouring: give every node a colour so that no two
connected nodes match, using at most K colours. One colour = one physical register.

Graph colouring is NP-complete, so we use a heuristic that rests on one observation:

    A node with fewer than K neighbours can ALWAYS be coloured.

Because even if all its neighbours take different colours, they use at most K-1 between
them, leaving at least one free. So we can safely set such a node aside and deal with it
last.

SIMPLIFY — take the graph apart
    Repeatedly find a node of degree < K, remove it from the graph, and push it onto a
    stack. Removing it lowers its neighbours' degrees, which often makes them removable
    too. Keep going until the graph is empty.

SELECT — put it back together
    Pop nodes off the stack one at a time. Add each back and give it any colour its
    neighbours are not using. Because of the removal order, a colour is nearly always
    available. We never guess — the stack ordering tells us the sequence that works.

THE BRIGGS PART
---------------
Sometimes simplify gets stuck: every remaining node has degree >= K. Chaitin's original
1981 algorithm spilled one immediately. Briggs (1994) noticed this is too pessimistic —
degree >= K does NOT mean uncolourable, because several of those neighbours may end up
sharing colours with each other.

So Briggs pushes such a node onto the stack anyway (an "optimistic" or "potential"
spill) and only spills if select later finds no free colour for it. That is an
*actual* spill. This one change is the core of our project.

When a real cost model is available (src.spilling.spiller.spill_cost), `simplify` can
be handed a `cost_fn` and will use cost/degree, exactly like M4's `choose_spill`, to pick
the *cheapest* node to push optimistically rather than just the highest-degree one. This
is optional and backward compatible: without a `cost_fn`, the highest-degree heuristic
described above is used.

Caution: `src.spilling.spiller` deliberately does NOT pass a `cost_fn` in its main
allocate/spill/retry loop. Always protecting the *cheapest* node from being pushed
optimistically can starve a persistently high-degree "hub" value — the one actually
responsible for the pressure — from ever being spilled, which can stop the spill loop
from converging at all. See the note in `spiller.py`'s module docstring for a concrete
example. `cost_fn` is kept here as an option because it is a reasonable idea and the
spec explicitly suggests it, but plain highest-degree is the safer default.

COALESCING
----------
Compilers emit lots of useless copies like `t4 = t3`. If the two do not interfere we can
merge their nodes, put both in one register, and delete the copy instruction entirely.

The catch: the merged node inherits both neighbour sets, so it has a higher degree and
is harder to colour. Briggs' conservative test says merging a and b is safe if the
merged node would have fewer than K neighbours of *significant degree* (degree >= K).
Under that test a merge can never turn a colourable graph into an uncolourable one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from src.analysis.interference import InterferenceGraph

CostFn = Callable[[str], float]


@dataclass
class AllocationResult:
    """What the colouring engine hands back.

    If `spilled` is non-empty, allocation did not succeed: M4 must rewrite the code with
    spill instructions and the whole pipeline runs again.
    """

    colours: dict[str, int] = field(default_factory=dict)   # vreg -> register number
    spilled: set[str] = field(default_factory=set)          # actual spills
    coalesced: dict[str, str] = field(default_factory=dict)  # merged vreg -> survivor
    k: int = 0
    # candidates/merged/refused move pairs from this allocation's coalesce() pass —
    # populated by allocate(); kept as an explicit dict (not new dataclass fields) so
    # existing positional/keyword construction of AllocationResult elsewhere is unaffected.
    coalesce_stats: dict[str, int] = field(
        default_factory=lambda: {"candidates": 0, "merged": 0, "refused": 0}
    )
    # Per-pair accepted/refused log from this allocation's coalesce() pass — see
    # coalesce()'s docstring. Populated by allocate() whenever do_coalesce is True.
    coalesce_trace: list[dict] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.spilled

    def register_of(self, vreg: str) -> int | None:
        """Follow coalescing chains to find the register a vreg ended up in."""
        seen = set()
        while vreg in self.coalesced and vreg not in seen:
            seen.add(vreg)
            vreg = self.coalesced[vreg]
        return self.colours.get(vreg)

    def verify(self, graph: InterferenceGraph) -> list[str]:
        """Check the colouring is valid. Returns a list of violations (empty = good).

        This is provided because it is the single most useful debugging tool you have:
        run it after every allocation and it will catch a wrong colouring immediately.
        """
        problems = []
        for u in graph.nodes():
            cu = self.register_of(u)
            if cu is None:
                if u not in self.spilled:
                    problems.append(f"{u} has no colour and was not spilled")
                continue
            if cu >= self.k or cu < 0:
                problems.append(f"{u} has colour {cu}, outside 0..{self.k - 1}")
            for v in graph.neighbours(u):
                if self.register_of(v) == cu:
                    problems.append(f"{u} and {v} interfere but both got register {cu}")
        return problems


def simplify(
    graph: InterferenceGraph,
    k: int,
    cost_fn: CostFn | None = None,
) -> tuple[list[str], set[str]]:
    """Remove nodes onto a stack. Returns (stack, optimistically_pushed).

    Repeatedly:
      - if some node has degree < k, remove the cheapest such node (ties broken by
        name, so the result is deterministic) — it is always colourable later;
      - otherwise every remaining node has "significant" degree >= k. Push one
        optimistically instead of declaring a spill: with a `cost_fn` (spill cost
        per unit of degree relieved) pick the node minimising cost/degree, the one
        least painful to actually spill if it comes to that; without one, fall back
        to the highest-degree node, a reasonable graph-only heuristic.

    The stack order matters: select() pops in reverse, so the last node removed here
    is the first one coloured.
    """
    work = graph.copy()
    stack: list[str] = []
    optimistic: set[str] = set()

    while work.nodes():
        low_degree = [n for n in work.nodes() if work.degree(n) < k]
        if low_degree:
            node = min(low_degree, key=lambda n: (work.degree(n), n))
        else:
            candidates = work.nodes()
            if cost_fn is not None:
                node = min(candidates, key=lambda n: (cost_fn(n) / max(work.degree(n), 1), n))
            else:
                node = max(candidates, key=lambda n: (work.degree(n), n))
            optimistic.add(node)
        work.remove_node(node)
        stack.append(node)

    return stack, optimistic


def select(graph: InterferenceGraph, stack: list[str], k: int) -> AllocationResult:
    """Pop the stack and assign colours. Nodes with no free colour become actual spills.

    Uses `graph.neighbours(n)` on the graph passed in — which must still have every
    node and edge intact, unlike the working copy `simplify` tore down internally.
    """
    result = AllocationResult(k=k)
    for node in reversed(stack):
        used = {result.colours[m] for m in graph.neighbours(node) if m in result.colours}
        free = set(range(k)) - used
        if free:
            result.colours[node] = min(free)
        else:
            result.spilled.add(node)
    return result


def briggs_can_coalesce(graph: InterferenceGraph, u: str, v: str, k: int) -> bool:
    """Briggs' conservative test: is merging u and v safe?

    Count the neighbours the merged node would have whose own degree is >= k
    ("significant degree"). If that count is < k, the merge is safe.

    Intuition: neighbours of degree < k will always find a colour for themselves, so
    they cannot be what makes the merged node uncolourable. Only the significant ones
    can, and if there are fewer than k of those, a colour remains free for the merged
    node no matter what its neighbours end up doing.
    """
    if graph.interferes(u, v):
        return False
    merged_neighbours = (graph.neighbours(u) | graph.neighbours(v)) - {u, v}
    significant = sum(1 for n in merged_neighbours if graph.degree(n) >= k)
    return significant < k


def _merge(graph: InterferenceGraph, mapping: dict[str, str], keep: str, drop: str) -> None:
    """Merge `drop` into `keep`: `keep` inherits `drop`'s edges, `drop` disappears."""
    neighbours = graph.remove_node(drop)
    for n in neighbours:
        graph.add_edge(keep, n)

    rewritten: set[frozenset[str]] = set()
    for pair in graph.move_pairs:
        items = {keep if name == drop else name for name in pair}
        if len(items) == 2:
            rewritten.add(frozenset(items))
        # len == 1 means the pair was {keep, drop} itself: it is now a self-move
        # (the copy this pair represented has effectively been coalesced away).
    graph.move_pairs = rewritten

    mapping[drop] = keep


def coalesce(
    graph: InterferenceGraph,
    k: int,
    stats: dict[str, int] | None = None,
    trace: list[dict] | None = None,
) -> dict[str, str]:
    """Merge every copy pair that passes the conservative test. Mutates `graph`.

    Returns a map from merged-away vreg to the surviving vreg.

    Repeat passes over the current move pairs (sorted for determinism) until a full
    pass makes no merge. Each successful merge immediately rewrites `graph.move_pairs`
    so later passes see the up-to-date node names — no separate "resolve the chain"
    step is needed, since a name is only ever merged away once.

    If `stats` is given, it is filled in with the counts behind that mapping:
    `candidates` (move pairs present before any merge attempt), `merged` (successful
    merges — `len(mapping)`), and `refused` (candidates that never became a merge,
    whether Briggs' test rejected them outright or one side was consumed by a
    different pair first).

    If `trace` is given (a list), one dict is appended per pair *actually evaluated*
    (`{"pair": (u, v), "accepted": bool, "reason": str}`), in the order the loop
    evaluates them — this is a live log of what happened, for the CLI/demo's
    "candidate / accepted-or-refused / reason" debug view, not a reconstruction. A
    pair can appear more than once if an earlier pass refused it and a later merge
    elsewhere changed the picture (e.g. lowered a neighbour's degree), and the names
    shown already reflect any merge from an earlier pass in the same call.
    """
    candidates = len(graph.move_pairs)
    mapping: dict[str, str] = {}
    progress = True
    while progress:
        progress = False
        for pair in sorted(graph.move_pairs, key=lambda fs: tuple(sorted(fs))):
            if pair not in graph.move_pairs:
                continue  # consumed by an earlier merge this pass
            u, v = tuple(sorted(pair))
            if u not in graph.adj or v not in graph.adj:
                continue
            if briggs_can_coalesce(graph, u, v, k):
                keep, drop = sorted((u, v))
                _merge(graph, mapping, keep, drop)
                progress = True
                if trace is not None:
                    trace.append({"pair": (u, v), "accepted": True,
                                  "reason": "safe: merged node stays under k significant-degree neighbours"})
            elif trace is not None:
                if graph.interferes(u, v):
                    reason = "refused: u and v interfere"
                else:
                    reason = f"refused: merged node would have >= {k} significant-degree (>=k) neighbours"
                trace.append({"pair": (u, v), "accepted": False, "reason": reason})
    if stats is not None:
        stats["candidates"] = candidates
        stats["merged"] = len(mapping)
        stats["refused"] = candidates - len(mapping)
    return mapping


def allocate(
    graph: InterferenceGraph,
    k: int,
    do_coalesce: bool = True,
    cost_fn: CostFn | None = None,
) -> AllocationResult:
    """Run the full colouring pipeline on one interference graph.

    1. Work on a private copy so the caller's graph is untouched.
    2. Coalesce copies (mutates the copy: merged-away nodes disappear from it).
    3. Simplify: `simplify` copies the (already-coalesced) graph again internally, so
       the copy we hold here is still intact afterwards — exactly what `select` needs
       to look up true neighbour sets.
    4. Select: colour or actually-spill every surviving node.

    The returned result's `coalesce_stats`/`coalesce_trace` fields are always filled
    in (from this call's own coalesce() pass, or left at their zero/empty defaults
    when `do_coalesce` is False) — see AllocationResult and coalesce()'s docstrings.
    Used by the CLI's `--dump-coalesce`, the web API and the faculty demo.
    """
    working = graph.copy()
    if do_coalesce:
        coalesce_stats: dict[str, int] = {"candidates": 0, "merged": 0, "refused": 0}
        coalesce_trace: list[dict] = []
        merged = coalesce(working, k, stats=coalesce_stats, trace=coalesce_trace)
    else:
        # Coalescing was never attempted, so nothing was "refused" — but the move
        # pairs that *could* have been tried are still real information (used by the
        # coalescing on/off experiment), so report them as candidates with 0 merges.
        merged = {}
        coalesce_stats = {"candidates": len(working.move_pairs), "merged": 0, "refused": 0}
        coalesce_trace = []
    stack, _optimistic = simplify(working, k, cost_fn=cost_fn)
    result = select(working, stack, k)
    result.coalesced = merged
    result.coalesce_stats = coalesce_stats
    result.coalesce_trace = coalesce_trace
    return result
