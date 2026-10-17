"""Tests for benchmarks/copy_heavy.tac: the coalescing-focused benchmark added for
Review 2. These pin down the real properties the benchmark was designed to have
(real copy pairs, real register pressure, safe coalescing under Briggs' test) so a
future edit to the file can't silently drift away from them.
"""

import pathlib

from src.analysis.interference import build_graph
from src.analysis.liveness import analyse
from src.colouring.allocator import coalesce
from src.frontend.cfg import build_cfg, compute_loop_depth
from src.frontend.parser import parse
from src.metrics import run_and_collect_metrics
from src.spilling.spiller import run_allocation

BENCH = pathlib.Path("benchmarks/copy_heavy.tac")


def _analysed():
    fn = parse(BENCH.read_text())
    build_cfg(fn)
    compute_loop_depth(fn)
    analyse(fn)
    return fn


def test_benchmark_file_exists_and_parses():
    assert BENCH.exists()
    fn = parse(BENCH.read_text())
    assert fn.name == "copy_heavy"


def test_benchmark_contains_meaningful_copy_instructions():
    """At least the four base-value copies plus the three-hop chain at the end."""
    from src.ir import Op
    fn = parse(BENCH.read_text())
    copies = [i for i in fn._parsed_instrs if i.op is Op.COPY]  # noqa: SLF001
    assert len(copies) == 7


def test_the_four_base_value_copy_pairs_are_coalescing_candidates():
    """t1/t5, t2/t6, t3/t7, t4/t8 must each appear as a move pair -- the graph-level
    precondition for coalescing to have anything to do.
    """
    fn = _analysed()
    g = build_graph(fn)
    for src, dst in [("t1", "t5"), ("t2", "t6"), ("t3", "t7"), ("t4", "t8")]:
        assert frozenset((src, dst)) in g.move_pairs
        assert not g.interferes(src, dst)


def test_real_register_pressure_forces_a_spill_at_low_k():
    """The benchmark must not be trivially colourable -- it should force at least one
    real spill at a small K, the same way benchmarks/high_pressure.tac does.
    """
    fn = parse(BENCH.read_text())
    result = run_allocation(fn, k=3, do_coalesce=True)
    assert not result.success  # K=3 is not enough for the 8-value copy cluster


def test_coalescing_produces_safe_merges_on_this_benchmark():
    """Running the real coalesce() on the real interference graph must actually merge
    at least one of the four designed-safe pairs (not zero -- otherwise the benchmark
    would not be exercising coalescing at all).
    """
    fn = _analysed()
    g = build_graph(fn)
    stats = {}
    mapping = coalesce(g, k=8, stats=stats)
    assert stats["candidates"] == 7
    assert stats["merged"] > 0
    assert stats["merged"] + stats["refused"] == stats["candidates"]


def test_both_coalescing_on_and_off_converge_to_a_valid_allocation():
    """Feature 2's acceptance check: run through the real parser and pipeline with
    coalescing enabled and with --no-coalesce's equivalent, and confirm both produce
    a verified allocation (not just "doesn't crash").
    """
    for do_coalesce in (True, False):
        fn = parse(BENCH.read_text())
        pipeline = run_allocation(fn, k=8, do_coalesce=do_coalesce, max_iterations=10)
        assert pipeline.success, f"do_coalesce={do_coalesce} failed to converge at k=8"
        assert pipeline.allocation.verify(pipeline.graph) == []


def test_metrics_collection_works_end_to_end_on_this_benchmark():
    fn = parse(BENCH.read_text())
    _, m = run_and_collect_metrics(fn, k=4, do_coalesce=True, benchmark="copy_heavy")
    assert m.num_move_instructions == 7
    assert m.num_coalescing_candidates == 7
    assert m.num_virtual_registers == 18
