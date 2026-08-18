"""M3 — the colouring engine: coalescing, simplify and select.

Owner: Member 3
Status: TODO — this is your part to implement. AllocationResult is provided.

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

from dataclasses import dataclass, field

from src.analysis.interference import InterferenceGraph


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


def simplify(graph: InterferenceGraph, k: int) -> tuple[list[str], set[str]]:
    """Remove nodes onto a stack. Returns (stack, optimistically_pushed).

    TODO(M3): implement.

    Sketch:
        work = graph.copy()
        stack = []
        optimistic = set()
        while work.nodes():
            pick any node of degree < k
            if there is one:
                remove it, push onto stack
            else:
                pick the best optimistic candidate (highest degree is a reasonable
                heuristic; M4's spill cost is better once available)
                remove it, push onto stack, record it in `optimistic`
        return stack, optimistic

    Note the stack order matters: select pops in reverse, so the last node removed is
    the first one coloured.
    """
    raise NotImplementedError("M3: simplify is not implemented yet")


def select(graph: InterferenceGraph, stack: list[str], k: int) -> AllocationResult:
    """Pop the stack and assign colours. Nodes with no free colour become actual spills.

    TODO(M3): implement.

    Sketch:
        result = AllocationResult(k=k)
        while stack:
            n = stack.pop()
            used = { colour of m for m in graph.neighbours(n) if m already coloured }
            free = set(range(k)) - used
            if free:
                result.colours[n] = min(free)
            else:
                result.spilled.add(n)
        return result

    Use graph.neighbours(n) on the ORIGINAL graph, not the working copy simplify
    consumed — that is why simplify copies the graph rather than mutating it.
    """
    raise NotImplementedError("M3: select is not implemented yet")


def briggs_can_coalesce(graph: InterferenceGraph, u: str, v: str, k: int) -> bool:
    """Briggs' conservative test: is merging u and v safe?

    TODO(M3): implement.

    The rule: count the neighbours the merged node would have whose degree is >= k
    ("significant degree"). If that count is < k, the merge is safe.

        if graph.interferes(u, v): return False
        merged = graph.neighbours(u) | graph.neighbours(v)
        significant = sum(1 for n in merged if graph.degree(n) >= k)
        return significant < k

    Intuition: neighbours of degree < k will always find a colour for themselves, so
    they cannot be what makes the merged node uncolourable. Only the significant ones
    can, and if there are fewer than k of those, a colour remains.
    """
    raise NotImplementedError("M3: briggs_can_coalesce is not implemented yet")


def coalesce(graph: InterferenceGraph, k: int) -> dict[str, str]:
    """Merge every copy pair that passes the conservative test.

    Returns a map from merged-away vreg to the surviving vreg. Mutates `graph`.

    TODO(M3): implement.

    Sketch:
        repeat until no merge happened this pass:
            for each move pair (u, v):
                if briggs_can_coalesce(graph, u, v, k):
                    merge v into u: give u all of v's edges, remove v
                    record mapping[v] = u
                    rewrite any move pair mentioning v to mention u instead

    After every merge, assert that no node became its own neighbour — that is the
    invariant our risk register promises to check.
    """
    raise NotImplementedError("M3: coalesce is not implemented yet")


def allocate(graph: InterferenceGraph, k: int, do_coalesce: bool = True) -> AllocationResult:
    """Run the full colouring pipeline on one interference graph.

    TODO(M3): implement — this is just the four steps above wired together.

        original = graph.copy()
        merged = coalesce(graph, k) if do_coalesce else {}
        stack, optimistic = simplify(graph, k)
        result = select(original, stack, k)
        result.coalesced = merged
        return result
    """
    raise NotImplementedError("M3: allocate is not implemented yet")
