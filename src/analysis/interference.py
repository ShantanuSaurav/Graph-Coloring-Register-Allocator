"""M2 — interference graph construction.

Owner: Member 2
Status: implemented.

The InterferenceGraph class is a shared contract — M3 (colouring) and M4 (spilling)
both read it, so its interface stays stable.
"""

from __future__ import annotations

from src.ir import Function


class InterferenceGraph:
    """An undirected graph of live ranges.

    An edge between u and v means they are live at the same time and therefore must not
    receive the same physical register.

    Stores an adjacency list (for iteration) and a set of frozen pairs (for O(1)
    membership tests), because the colouring engine asks "do these interfere?" constantly.
    """

    def __init__(self) -> None:
        self.adj: dict[str, set[str]] = {}
        self._edges: set[frozenset[str]] = set()
        self.move_pairs: set[frozenset[str]] = set()  # copy instrs, for coalescing

    def add_node(self, v: str) -> None:
        self.adj.setdefault(v, set())

    def add_edge(self, u: str, v: str) -> None:
        """Record that u and v interfere. Self-edges are ignored."""
        if u == v:
            return
        self.add_node(u)
        self.add_node(v)
        self.adj[u].add(v)
        self.adj[v].add(u)
        self._edges.add(frozenset((u, v)))

    def add_move(self, u: str, v: str) -> None:
        """Record a copy instruction `u = v` as a coalescing candidate."""
        if u != v:
            self.add_node(u)
            self.add_node(v)
            self.move_pairs.add(frozenset((u, v)))

    def interferes(self, u: str, v: str) -> bool:
        return frozenset((u, v)) in self._edges

    def degree(self, v: str) -> int:
        return len(self.adj.get(v, ()))

    def neighbours(self, v: str) -> set[str]:
        return set(self.adj.get(v, ()))

    def nodes(self) -> set[str]:
        return set(self.adj)

    def edge_count(self) -> int:
        return len(self._edges)

    def remove_node(self, v: str) -> set[str]:
        """Remove v, returning the neighbours it had. Used by the simplify phase."""
        nbrs = self.adj.pop(v, set())
        for n in nbrs:
            self.adj[n].discard(v)
            self._edges.discard(frozenset((v, n)))
        return nbrs

    def copy(self) -> "InterferenceGraph":
        g = InterferenceGraph()
        g.adj = {k: set(v) for k, v in self.adj.items()}
        g._edges = set(self._edges)
        g.move_pairs = set(self.move_pairs)
        return g

    def to_dot(self, colours: dict[str, int] | None = None) -> str:
        """Render as Graphviz DOT. Pass a colour map to tint the nodes.

        This produces the pictures for the review. Write to a .dot file, then:
            dot -Tpng graph.dot -o graph.png
        """
        palette = ["#e15759", "#f2a541", "#3aa76d", "#3d7fd1",
                   "#9b5de5", "#00b4a6", "#d67ab1", "#8a8a8a"]
        out = ["graph interference {",
               '  node [shape=circle, style=filled, fontname="Helvetica"];']
        for v in sorted(self.adj):
            if colours and v in colours:
                fill = palette[colours[v] % len(palette)]
                out.append(f'  "{v}" [fillcolor="{fill}", label="{v}\\nR{colours[v]}"];')
            else:
                out.append(f'  "{v}" [fillcolor="#e8e8e8"];')
        for e in sorted(self._edges, key=lambda s: sorted(s)):
            a, b = sorted(e)
            out.append(f'  "{a}" -- "{b}";')
        out.append("}")
        return "\n".join(out)

    def __repr__(self) -> str:
        return f"InterferenceGraph({len(self.adj)} nodes, {len(self._edges)} edges)"


def build_graph(fn: Function) -> InterferenceGraph:
    """Build the interference graph from a function whose liveness has been computed.

    The standard construction, per block, walking backwards:

        live = set(block.live_out)
        for each instruction from last to first:
            if it is a copy `d = s`:
                graph.add_move(d, s)
                live.discard(s)          # s and d may share a register: no edge
            for d in instr.defs():
                for l in live:
                    graph.add_edge(d, l)
            live -= instr.defs()
            live |= instr.uses()

    Why discard the copy source before adding edges: `d = s` does not make d and s
    conflict — at that moment they hold the same value. Skipping that edge is exactly
    what makes coalescing possible later.

    Remember to add_node() every vreg in the function, so a value with no interferences
    still appears in the graph.
    """
    from src.ir import BasicBlock

    graph = InterferenceGraph()

    # Ensure every vreg in the function is added to the graph, even if it has no interferences
    for vreg in fn.all_vregs():
        graph.add_node(vreg)

    blocks = fn.blocks.values()
    # Test fallback: if cfg.py hasn't run but we have raw instructions (like in tests)
    if not blocks and hasattr(fn, '_parsed_instrs'):
        blocks = [BasicBlock("fallback", instrs=fn._parsed_instrs)]  # type: ignore

    # If the fallback is used, fn.all_vregs() might be empty because it relies on blocks.
    # So we should populate nodes from the instructions if needed.
    if not fn.blocks and hasattr(fn, '_parsed_instrs'):
        for i in fn._parsed_instrs:  # type: ignore
            for vreg in i.defs() | i.uses():
                graph.add_node(vreg)

    for block in blocks:
        live = set(block.live_out)
        for instr in reversed(block.instrs):
            if instr.is_copy() and instr.dst and instr.src1:
                d = instr.dst
                s = instr.src1
                graph.add_move(d, s)
                live.discard(s)

            for d in instr.defs():
                for l in live:
                    graph.add_edge(d, l)

            live -= instr.defs()
            live |= instr.uses()

    return graph
