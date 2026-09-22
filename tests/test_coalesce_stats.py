"""Tests for the coalescing candidate/merged/refused instrumentation added to
`coalesce()` and `allocate()` in src/colouring/allocator.py for the Review 2 metrics
feature. These are additive to the existing tests in test_colouring.py, which already
cover coalesce()'s merge/refuse *behaviour*; these check the new *counters*.
"""

from src.analysis.interference import InterferenceGraph
from src.colouring.allocator import allocate, coalesce


def test_stats_dict_is_optional_and_backward_compatible():
    """The pre-existing call signature `coalesce(graph, k)` must keep working
    unchanged -- test_colouring.py relies on this.
    """
    g = InterferenceGraph()
    g.add_node("t1")
    g.add_node("t2")
    g.add_move("t1", "t2")
    mapping = coalesce(g, k=4)
    assert mapping in ({"t2": "t1"}, {"t1": "t2"})


def test_stats_counts_a_safe_merge():
    g = InterferenceGraph()
    g.add_node("t1")
    g.add_node("t2")
    g.add_move("t1", "t2")
    stats = {}
    coalesce(g, k=4, stats=stats)
    assert stats == {"candidates": 1, "merged": 1, "refused": 0}


def test_stats_counts_a_refused_merge():
    """An interfering move pair is a candidate that is never merged."""
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    g.add_move("t1", "t2")
    stats = {}
    coalesce(g, k=4, stats=stats)
    assert stats == {"candidates": 1, "merged": 0, "refused": 1}


def test_stats_candidates_always_equals_merged_plus_refused():
    g = InterferenceGraph()
    g.add_edge("t3", "t4")     # refused: interferes
    g.add_move("t1", "t2")     # merged: safe
    g.add_move("t3", "t4")     # refused: interferes
    stats = {}
    coalesce(g, k=4, stats=stats)
    assert stats["candidates"] == 2
    assert stats["merged"] + stats["refused"] == stats["candidates"]
    assert stats["merged"] == 1
    assert stats["refused"] == 1


def test_allocate_populates_coalesce_stats_when_enabled():
    g = InterferenceGraph()
    g.add_node("t1")
    g.add_node("t2")
    g.add_move("t1", "t2")
    result = allocate(g, k=4, do_coalesce=True)
    assert result.coalesce_stats["candidates"] == 1
    assert result.coalesce_stats["merged"] == 1
    assert result.coalesce_stats["refused"] == 0


def test_allocate_reports_candidates_but_no_merges_when_coalescing_disabled():
    g = InterferenceGraph()
    g.add_node("t1")
    g.add_node("t2")
    g.add_move("t1", "t2")
    result = allocate(g, k=4, do_coalesce=False)
    assert result.coalesced == {}
    assert result.coalesce_stats["candidates"] == 1
    assert result.coalesce_stats["merged"] == 0
    assert result.coalesce_stats["refused"] == 0
    assert result.coalesce_trace == []


def test_trace_records_an_accepted_pair_with_a_reason():
    g = InterferenceGraph()
    g.add_node("t1")
    g.add_node("t2")
    g.add_move("t1", "t2")
    trace: list = []
    coalesce(g, k=4, trace=trace)
    assert len(trace) == 1
    entry = trace[0]
    assert entry["pair"] == ("t1", "t2")
    assert entry["accepted"] is True
    assert "reason" in entry and entry["reason"]


def test_trace_records_a_refused_pair_and_names_the_reason():
    g = InterferenceGraph()
    g.add_edge("t1", "t2")
    g.add_move("t1", "t2")
    trace: list = []
    coalesce(g, k=4, trace=trace)
    assert len(trace) == 1
    assert trace[0]["accepted"] is False
    assert "interfere" in trace[0]["reason"]


def test_allocate_exposes_the_trace_on_the_result():
    g = InterferenceGraph()
    g.add_node("t1")
    g.add_node("t2")
    g.add_move("t1", "t2")
    result = allocate(g, k=4, do_coalesce=True)
    assert len(result.coalesce_trace) == 1
    assert result.coalesce_trace[0]["accepted"] is True
