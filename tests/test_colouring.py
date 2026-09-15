"""Tests for M3's colouring engine: simplify, select, and Briggs coalescing."""

from src.analysis.interference import InterferenceGraph
from src.colouring.allocator import (
    AllocationResult,
    allocate,
    briggs_can_coalesce,
    coalesce,
    select,
    simplify,
)


def triangle() -> InterferenceGraph:
    """Three mutually interfering nodes: needs exactly 3 colours."""
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    g.add_edge("t2", "t3")
    g.add_edge("t1", "t3")
    return g


def path() -> InterferenceGraph:
    """t1 - t2 - t3: 2-colourable."""
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    g.add_edge("t2", "t3")
    return g


# --- the verifier is implemented, so this one runs today -------------------

def test_verify_catches_a_bad_colouring():
    g = triangle()
    bad = AllocationResult(colours={"t1": 0, "t2": 0, "t3": 1}, k=3)
    problems = bad.verify(g)
    assert problems, "verify must reject two interfering nodes sharing a register"


def test_verify_accepts_a_good_colouring():
    g = triangle()
    good = AllocationResult(colours={"t1": 0, "t2": 1, "t3": 2}, k=3)
    assert good.verify(g) == []


def test_register_of_follows_coalescing_chain():
    r = AllocationResult(colours={"t1": 2}, coalesced={"t2": "t1"}, k=4)
    assert r.register_of("t2") == 2


# --- specifications for M3 -------------------------------------------------

def test_simplify_empties_the_graph():
    stack, _ = simplify(path(), k=3)
    assert sorted(stack) == ["t1", "t2", "t3"]


def test_path_needs_only_two_colours():
    g = path()
    stack, _ = simplify(g.copy(), k=2)
    result = select(g, stack, k=2)
    assert result.success
    assert result.verify(g) == []


def test_triangle_colours_with_three():
    g = triangle()
    result = allocate(g, k=3)
    assert result.success
    assert len(set(result.colours.values())) == 3


def test_triangle_spills_with_two():
    g = triangle()
    result = allocate(g, k=2)
    assert result.spilled, "a 3-clique cannot be 2-coloured"


def test_briggs_refuses_to_merge_interfering_nodes():
    g = triangle()
    assert briggs_can_coalesce(g, "t1", "t2", k=3) is False


def test_briggs_allows_a_safe_merge():
    g = InterferenceGraph()
    g.add_node("t1")
    g.add_node("t2")
    g.add_move("t1", "t2")
    assert briggs_can_coalesce(g, "t1", "t2", k=4) is True


def test_optimistic_push_beats_chaitin():
    """A node of degree >= K that is nonetheless colourable.

    t0 joins four nodes that all share one colour between them. Its degree is 4, so
    Chaitin would spill it at K=2. Briggs pushes it optimistically and colours it.
    """
    g = InterferenceGraph()
    for n in ("t1", "t2", "t3", "t4"):
        g.add_edge("t0", n)
    result = allocate(g, k=2)
    assert result.success, "optimistic colouring should avoid this spill"


# --------------------------------------------------------------- coalescing


def test_coalesce_merges_a_safe_copy_pair():
    g = InterferenceGraph()
    g.add_node("t1")
    g.add_node("t2")
    g.add_move("t1", "t2")
    mapping = coalesce(g, k=4)
    assert mapping in ({"t2": "t1"}, {"t1": "t2"})
    survivor = next(iter(mapping.values()))
    dropped = next(iter(mapping.keys()))
    assert dropped not in g.nodes()
    assert survivor in g.nodes()


def test_coalesce_refuses_an_interfering_move_pair():
    """A copy between two nodes that also interfere (a redundant/impossible copy in
    real code, but the graph doesn't know that) must never be merged — that would
    silently make a live range interfere with itself.
    """
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    g.add_move("t1", "t2")
    mapping = coalesce(g, k=4)
    assert mapping == {}
    assert g.interferes("t1", "t2")


def test_coalesce_transfers_the_merged_nodes_edges():
    """t2 = t3 (a move) where t3 also interferes with t4: after merging t3 into t2,
    t2 must inherit that interference (t2 and t4 must not end up sharing a colour).
    """
    g = InterferenceGraph()
    g.add_edge("t3", "t4")
    g.add_move("t2", "t3")
    mapping = coalesce(g, k=4)
    assert mapping == {"t3": "t2"}
    assert g.interferes("t2", "t4")
    assert "t3" not in g.nodes()


def test_allocate_with_coalescing_still_verifies_against_the_original_graph():
    """The real soundness property: even though coalesce() physically merges nodes
    in a working copy, the colouring it produces must respect every edge of the
    ORIGINAL, pre-coalesce graph once register_of() follows the merge chain back.
    """
    g = InterferenceGraph()
    g.add_edge("t1", "t3")   # t1 and t3 interfere
    g.add_move("t2", "t3")   # t2 is a copy of t3 and does not interfere with it
    original = g.copy()

    result = allocate(g, k=2)
    assert result.success
    assert result.verify(original) == []
