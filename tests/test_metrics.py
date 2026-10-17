"""Tests for src.metrics: AllocationMetrics collection.

Expected values here were derived by hand-tracing build_graph()/run_allocation() on
the named benchmark (the same way tests/test_interference.py and
tests/test_spilling.py hand-verify their own fixtures), then cross-checked by running
the real pipeline once during development. They are not copied from any script output.
"""

from src.frontend.parser import parse
from src.metrics import collect_metrics, run_and_collect_metrics
from src.spilling.spiller import run_allocation


def test_simple_benchmark_metrics_match_hand_trace():
    fn = parse(open("benchmarks/simple.tac").read())
    pipeline, m = run_and_collect_metrics(fn, k=4, do_coalesce=True, benchmark="simple")

    assert m.benchmark == "simple"
    assert m.k == 4
    assert m.coalescing_enabled is True
    assert m.num_input_instructions == 6
    assert m.num_virtual_registers == 5
    assert m.num_cfg_blocks == 1
    assert m.num_cfg_edges == 0
    # t1-t2 is the only interference edge (t3/t4/t5 form a copy-linked chain with no
    # other simultaneously-live value); see tests/test_interference.py for the same
    # graph checked directly.
    assert m.num_interference_nodes == 5
    assert m.num_interference_edges == 1
    assert m.max_interference_degree == 1
    assert m.num_move_instructions == 1          # t4 = t3
    assert m.num_coalescing_candidates == 1
    assert m.num_coalescing_merges == 1           # t3/t4 don't interfere: safe merge
    assert m.num_coalescing_refused == 0
    assert m.num_spilled_vregs == 0
    assert m.num_spill_loads == 0
    assert m.num_spill_stores == 0
    assert m.num_retry_iterations == 1
    assert m.num_final_instructions == 6
    assert m.success is True
    assert pipeline.success is True


def test_coalescing_candidates_equals_merged_plus_refused():
    """Sanity invariant collect_metrics must always satisfy, on any benchmark."""
    import pathlib
    for bench in sorted(pathlib.Path("benchmarks").glob("*.tac")):
        fn = parse(bench.read_text())
        _, m = run_and_collect_metrics(fn, k=4, do_coalesce=True, benchmark=bench.stem)
        assert m.num_coalescing_candidates == m.num_coalescing_merges + m.num_coalescing_refused, bench


def test_disabling_coalescing_reports_zero_merges():
    fn = parse(open("benchmarks/copy_heavy.tac").read())
    _, m = run_and_collect_metrics(fn, k=8, do_coalesce=False, benchmark="copy_heavy")
    assert m.coalescing_enabled is False
    assert m.num_coalescing_merges == 0
    assert m.num_coalescing_refused == 0
    # Candidates (copy pairs present in the graph) are still real information even
    # though none were attempted -- see allocate()'s do_coalesce=False branch.
    assert m.num_coalescing_candidates == 7


def test_briggs_example_node_and_edge_counts_match_the_regression_fixture():
    """Cross-check against the hand-verified 9-edge graph in test_interference.py."""
    fn = parse(open("benchmarks/briggs_example.tac").read())
    _, m = run_and_collect_metrics(fn, k=3, do_coalesce=True, benchmark="briggs_example")
    assert m.num_interference_nodes == 8
    assert m.num_interference_edges == 9
    assert m.max_interference_degree == 4          # t4 has degree 4 in the fixture


def test_spill_metrics_on_a_forced_spill_are_internally_consistent():
    fn = parse(open("benchmarks/high_pressure.tac").read())
    pipeline, m = run_and_collect_metrics(fn, k=4, do_coalesce=True, benchmark="high_pressure")

    assert m.success is True
    assert m.num_retry_iterations > 1
    assert m.num_spilled_vregs > 0
    assert m.num_spill_loads == m.num_spilled_vregs   # one use each in this benchmark
    assert m.num_spill_stores == m.num_spilled_vregs  # one def each in this benchmark
    assert m.num_final_physical_registers <= m.k
    # metrics.num_spill_loads/stores must agree with the pipeline's own counter.
    from src.spilling.spiller import count_spill_instructions
    assert m.num_spill_loads + m.num_spill_stores == count_spill_instructions(pipeline.function)
    assert pipeline.allocation.verify(pipeline.graph) == []


def test_no_fake_metrics_when_allocation_fails():
    """K=1 always fails on a benchmark with a binary op. Metrics must reflect the
    real, unsuccessful last attempt rather than silently reporting success.
    """
    fn = parse(open("benchmarks/simple.tac").read())
    pipeline, m = run_and_collect_metrics(fn, k=1, do_coalesce=True, benchmark="simple", max_iterations=10)
    assert m.success is False
    assert pipeline.success is False
    assert m.num_retry_iterations == 10


def test_collect_metrics_matches_manual_run_allocation_call():
    """collect_metrics() is meant to be usable standalone (not only through
    run_and_collect_metrics), given the first-iteration graph/result explicitly.
    """
    fn = parse(open("benchmarks/simple.tac").read())
    captured = {}

    def on_iteration(iteration, fn_i, graph, result):
        if iteration == 1:
            captured["graph"] = graph
            captured["result"] = result

    pipeline = run_allocation(fn, k=4, do_coalesce=True, on_iteration=on_iteration)
    m = collect_metrics(
        original_fn=fn, k=4, do_coalesce=True, pipeline=pipeline,
        first_graph=captured["graph"], first_result=captured["result"], benchmark="simple",
    )
    assert m.num_interference_nodes == 5
    assert m.success is True
