"""Tests for the InterferenceGraph container (M2).

The container is implemented, so these pass today. The build_graph tests below are
marked xfail until M2 implements it — they document the expected behaviour.
"""

import pytest

from src.analysis.interference import InterferenceGraph, build_graph
from src.frontend.parser import parse


def test_edge_is_symmetric():
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    assert g.interferes("t1", "t2") and g.interferes("t2", "t1")
    assert g.neighbours("t1") == {"t2"}


def test_self_edge_ignored():
    g = InterferenceGraph()
    g.add_edge("t1", "t1")
    assert g.degree("t1") == 0


def test_duplicate_edges_counted_once():
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    g.add_edge("t2", "t1")
    assert g.edge_count() == 1


def test_isolated_node_appears():
    g = InterferenceGraph()
    g.add_node("t9")
    assert "t9" in g.nodes() and g.degree("t9") == 0


def test_remove_node_updates_neighbours():
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    g.add_edge("t1", "t3")
    nbrs = g.remove_node("t1")
    assert nbrs == {"t2", "t3"}
    assert g.degree("t2") == 0
    assert not g.interferes("t1", "t2")


def test_copy_is_independent():
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    h = g.copy()
    h.remove_node("t1")
    assert g.degree("t2") == 1, "mutating the copy must not affect the original"


def test_move_pairs_recorded():
    g = InterferenceGraph()
    g.add_move("t1", "t2")
    assert frozenset(("t1", "t2")) in g.move_pairs


def test_dot_output_contains_nodes_and_edges():
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    dot = g.to_dot({"t1": 0, "t2": 1})
    assert dot.startswith("graph interference {") and dot.rstrip().endswith("}")
    assert '"t1" -- "t2"' in dot
    assert "R0" in dot and "R1" in dot


@pytest.mark.xfail(reason="M2: build_graph not implemented yet", raises=NotImplementedError)
def test_build_graph_simple():
    """t1 and t2 are both live at t3 = t1 + t2, so they must interfere."""
    fn = parse(open("benchmarks/simple.tac").read())
    g = build_graph(fn)
    assert g.interferes("t1", "t2")


@pytest.mark.xfail(reason="M2: build_graph not implemented yet", raises=NotImplementedError)
def test_copy_does_not_create_an_edge():
    """In `t4 = t3` the two hold the same value, so they must NOT interfere.

    This is the property that makes coalescing possible. If this test fails once
    build_graph is written, coalescing will never fire.
    """
    fn = parse(open("benchmarks/simple.tac").read())
    g = build_graph(fn)
    assert not g.interferes("t3", "t4")
