"""Tests for M3's colouring engine.

These are xfail until M3 implements the module. They are written first on purpose:
they specify exactly what `simplify`, `select` and `briggs_can_coalesce` must do, so
M3 can work against them rather than guessing.
"""

import pytest

from src.analysis.interference import InterferenceGraph
from src.colouring.allocator import (
    AllocationResult,
    allocate,
    briggs_can_coalesce,
    select,
    simplify,
)

XFAIL = pytest.mark.xfail(reason="M3 not implemented yet", raises=NotImplementedError)


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

@XFAIL
def test_simplify_empties_the_graph():
    stack, _ = simplify(path(), k=3)
    assert sorted(stack) == ["t1", "t2", "t3"]


@XFAIL
def test_path_needs_only_two_colours():
    g = path()
    stack, _ = simplify(g.copy(), k=2)
    result = select(g, stack, k=2)
    assert result.success
    assert result.verify(g) == []


@XFAIL
def test_triangle_colours_with_three():
    g = triangle()
    result = allocate(g, k=3)
    assert result.success
    assert len(set(result.colours.values())) == 3


@XFAIL
def test_triangle_spills_with_two():
    g = triangle()
    result = allocate(g, k=2)
    assert result.spilled, "a 3-clique cannot be 2-coloured"


@XFAIL
def test_briggs_refuses_to_merge_interfering_nodes():
    g = triangle()
    assert briggs_can_coalesce(g, "t1", "t2", k=3) is False


@XFAIL
def test_briggs_allows_a_safe_merge():
    g = InterferenceGraph()
    g.add_node("t1")
    g.add_node("t2")
    g.add_move("t1", "t2")
    assert briggs_can_coalesce(g, "t1", "t2", k=4) is True


@XFAIL
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
