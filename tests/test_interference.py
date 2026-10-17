"""Tests for the InterferenceGraph container and build_graph (M2)."""

from src.analysis.interference import InterferenceGraph, build_graph
from src.analysis.liveness import analyse
from src.frontend.cfg import build_cfg
from src.frontend.parser import parse


def _analysed(path: str):
    fn = parse(open(path).read())
    build_cfg(fn)
    analyse(fn)
    return fn


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


def test_edges_accessor_matches_internal_edge_set():
    """Public accessor added for Review 2's web API stage dump -- must agree with the
    private `_edges` set the pre-existing tests already introspect directly.
    """
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    g.add_edge("t2", "t3")
    assert g.edges() == g._edges  # noqa: SLF001 (test-only introspection)
    assert frozenset(("t1", "t2")) in g.edges()


def test_edges_accessor_returns_a_copy_not_a_live_reference():
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    edges = g.edges()
    edges.add(frozenset(("t9", "t10")))
    assert frozenset(("t9", "t10")) not in g.edges()


def test_dot_output_contains_nodes_and_edges():
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    dot = g.to_dot({"t1": 0, "t2": 1})
    assert dot.startswith("graph interference {") and dot.rstrip().endswith("}")
    assert '"t1" -- "t2"' in dot
    assert "R0" in dot and "R1" in dot


def test_build_graph_simple():
    """t1 and t2 are both live at t3 = t1 + t2, so they must interfere."""
    fn = _analysed("benchmarks/simple.tac")
    g = build_graph(fn)
    assert g.interferes("t1", "t2")


def test_copy_does_not_create_an_edge():
    """In `t4 = t3` the two hold the same value, so they must NOT interfere.

    This is the property that makes coalescing possible: if this ever fails,
    coalescing will never fire, because build_graph would have already ruled out
    every copy pair as interfering.
    """
    fn = _analysed("benchmarks/simple.tac")
    g = build_graph(fn)
    assert not g.interferes("t3", "t4")
    assert frozenset(("t3", "t4")) in g.move_pairs


def test_every_vreg_appears_even_with_no_interferences():
    fn = _analysed("benchmarks/simple.tac")
    g = build_graph(fn)
    assert g.nodes() == fn.all_vregs()


def test_build_graph_is_deterministic():
    fn1 = _analysed("benchmarks/briggs_example.tac")
    fn2 = _analysed("benchmarks/briggs_example.tac")
    g1, g2 = build_graph(fn1), build_graph(fn2)
    assert g1.nodes() == g2.nodes()
    assert g1._edges == g2._edges  # noqa: SLF001 (test-only introspection)


def test_briggs_example_edge_set_matches_the_worked_example():
    """Cross-check build_graph against docs/briggs_example_solution.md.

    Note: the edge set here has one more edge than the version originally hand-worked
    in that doc (t2-t4). See the doc's "Correction" note — t2 is still live (it is
    used again by `t5 = t2 + t3`) at the exact point `t4 = t1 + t3` is defined, so a
    standard liveness-based interference construction must connect them. This test
    intentionally encodes the corrected, verified edge set, not the original guess.
    """
    fn = _analysed("benchmarks/briggs_example.tac")
    g = build_graph(fn)

    expected_edges = {
        frozenset(p) for p in [
            ("t1", "t2"), ("t1", "t3"), ("t2", "t3"),
            ("t2", "t4"),
            ("t3", "t4"),
            ("t4", "t5"), ("t4", "t6"),
            ("t5", "t6"), ("t5", "t7"),
        ]
    }
    assert g._edges == expected_edges  # noqa: SLF001 (test-only introspection)

    expected_degrees = {"t1": 2, "t2": 3, "t3": 3, "t4": 4, "t5": 3, "t6": 2, "t7": 1, "t8": 0}
    for vreg, degree in expected_degrees.items():
        assert g.degree(vreg) == degree, f"{vreg}: expected degree {degree}, got {g.degree(vreg)}"
