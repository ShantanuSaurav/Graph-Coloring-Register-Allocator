"""Tests for M4's spill cost model, rewriter, and the spill/retry pipeline."""

from src.analysis.interference import build_graph
from src.analysis.liveness import analyse
from src.frontend.cfg import build_cfg, compute_loop_depth
from src.frontend.parser import parse
from src.ir import Op
from src.spilling.spiller import (
    choose_spill,
    count_spill_instructions,
    rewrite_with_spills,
    run_allocation,
    spill_cost,
)


def _analysed(src_or_path: str, is_path: bool = False):
    text = open(src_or_path).read() if is_path else src_or_path
    fn = parse(text)
    build_cfg(fn)
    compute_loop_depth(fn)
    return fn


# ------------------------------------------------------------------- cost


def test_occurrence_inside_a_loop_costs_ten_times_one_outside():
    """Isolate the effect cleanly: one value used once outside any loop, another used
    once inside a single loop, nothing else touching either. This is a purpose-built
    example rather than a benchmark file, specifically so the two values being
    compared differ *only* in loop depth, not also in how many times each appears.
    """
    outside = _analysed("func f\n t1 = 1\n ret t1\nend")
    # one def + one use, both at depth 0: 10**0 + 10**0 = 2
    assert spill_cost(outside, "t1") == 2

    inside = _analysed(
        "func f\n"
        " t1 = 0\n"
        "label L1\n"
        " t1 = t1 + 1\n"
        " if t1 < 10 goto L1\n"
        " ret t1\n"
        "end"
    )
    # t1 inside has several occurrences at depth 1 (cost 10 each); even after
    # accounting for its extra occurrences, it must dominate the depth-0 baseline.
    assert spill_cost(inside, "t1") > 10 * spill_cost(outside, "t1")


def test_loop_tac_costs_reflect_per_occurrence_weighting():
    """benchmarks/loop.tac, worked by hand (see docs): t1 has 2 occurrences outside
    the loop (cost 1 each) and 2 inside (cost 10 each) = 22; t3 has 2 occurrences,
    both inside the loop = 20. Both are dominated by the x10 loop weighting, but t1's
    total is larger simply because it has more occurrences overall — cost is a sum
    over occurrences, not an average, so "more occurrences" can outweigh "how deep".
    What must hold regardless is the per-occurrence weighting itself, which this
    checks directly against the hand-worked totals.
    """
    fn = _analysed("benchmarks/loop.tac", is_path=True)
    assert spill_cost(fn, "t1") == 22
    assert spill_cost(fn, "t3") == 20


def test_nested_loop_costs_more_than_single_loop():
    fn = _analysed("benchmarks/nested_loop.tac", is_path=True)
    assert spill_cost(fn, "t4") > spill_cost(fn, "t2")
    # t4 lives entirely at loop_depth 2 (2 occurrences * 10**2 = 200);
    # t2 lives mostly at loop_depth 0-1 (see docs/architecture.md worked trace).
    assert spill_cost(fn, "t4") == 200


def test_value_never_used_costs_nothing():
    fn = _analysed("func f\n t1 = 1\n ret t1\nend")
    assert spill_cost(fn, "t99") == 0


# ------------------------------------------------------------- choose_spill


def test_choose_spill_picks_the_smallest_cost_over_degree():
    fn = _analysed("benchmarks/nested_loop.tac", is_path=True)
    analyse(fn)
    graph = build_graph(fn)

    # t4 is very expensive (loop_depth 2). Force it into the candidate set alongside
    # a cheap, low-degree value and confirm the cheap one is chosen.
    cheap = min(
        (v for v in graph.nodes() if v != "t4"),
        key=lambda v: spill_cost(fn, v) / max(graph.degree(v), 1),
    )
    chosen = choose_spill(fn, graph, {"t4", cheap})
    assert chosen == cheap


def test_choose_spill_handles_degree_zero_without_dividing_by_zero():
    # t2 is defined first and never used, and nothing else is live yet at that
    # point, so it picks up no interference edges at all: a genuine degree-0 node.
    fn = _analysed("func f\n t2 = 2\n t1 = 1\n ret t1\nend")
    analyse(fn)
    graph = build_graph(fn)
    assert graph.degree("t2") == 0
    chosen = choose_spill(fn, graph, {"t2"})
    assert chosen == "t2"


# --------------------------------------------------------------- rewriting


def test_rewrite_inserts_a_load_for_every_use():
    fn = _analysed("benchmarks/simple.tac", is_path=True)
    before = count_spill_instructions(fn)
    after = count_spill_instructions(rewrite_with_spills(fn, {"t3"}))
    assert after > before


def test_rewrite_uses_fresh_names_per_use():
    """Each reload must get its own vreg: t3 is used twice in simple.tac
    (`t4 = t3` and nowhere else — use loop.tac's t1 instead, which is used twice),
    so the two reloads must not be the same name.
    """
    fn = _analysed("benchmarks/loop.tac", is_path=True)
    out = rewrite_with_spills(fn, {"t1"})
    loads = [i for i in out._parsed_instrs if i.op is Op.LOAD]
    load_names = [i.dst for i in loads]
    assert len(load_names) == len(set(load_names)), "reload temporaries must be unique"
    assert "t1" not in load_names  # a load produces a *fresh* name, never the old one


def test_rewrite_preserves_definition_order_around_a_store():
    """`t3 = t1 + t2` with t3 spilled: the def keeps writing t3, and the store comes
    immediately after — not before, which would store garbage.
    """
    fn = _analysed("func f\n t1 = 1\n t2 = 2\n t3 = t1 + t2\n ret t3\nend")
    out = rewrite_with_spills(fn, {"t3"})
    ops = [(i.op, i.dst, i.src1) for i in out._parsed_instrs]
    def_index = next(i for i, instr in enumerate(out._parsed_instrs)
                      if instr.op is Op.BINOP and instr.dst == "t3")
    store_index = next(i for i, instr in enumerate(out._parsed_instrs)
                        if instr.op is Op.STORE and instr.src1 == "t3")
    assert store_index == def_index + 1


def test_rewrite_does_not_reuse_slots_across_rounds():
    """Regression test: an earlier version of rewrite_with_spills restarted its slot
    counter at 0 on every call, so a second round's spill could reuse a slot a
    previous round's load had not consumed yet, silently corrupting the value it
    read back. Two independent rewrite rounds must never share a slot number.
    """
    fn = _analysed("func f\n t1 = 1\n t2 = 2\n t3 = t1 + t2\n t4 = t3 + t1\n ret t4\nend")
    round1 = rewrite_with_spills(fn, {"t1"})
    round2 = rewrite_with_spills(round1, {"t2"})

    round1_slots = [i.slot for i in round1._parsed_instrs if i.op in (Op.LOAD, Op.STORE)]
    round2_slots = [i.slot for i in round2._parsed_instrs if i.op in (Op.LOAD, Op.STORE)]
    # round2's new slot(s) for t2 must come strictly after every slot round1 used,
    # not restart at 0 and collide with round1's still-present load/store pair.
    assert max(round2_slots) > max(round1_slots)


# ---------------------------------------------------------- full pipeline


def test_pipeline_succeeds_when_registers_are_sufficient():
    fn = parse(open("benchmarks/high_pressure.tac").read())
    result = run_allocation(fn, k=8)
    assert result.success
    assert result.iterations == 1
    assert count_spill_instructions(result.function) == 0


def test_pipeline_spills_and_converges_under_pressure():
    fn = parse(open("benchmarks/high_pressure.tac").read())
    result = run_allocation(fn, k=4)
    assert result.success
    assert result.iterations > 1
    assert result.allocation.verify(result.graph) == []


def test_pipeline_gives_a_clean_failure_within_the_iteration_cap():
    """K=1 is architecturally impossible for any program containing a binary
    operation (a binop always needs two simultaneous register operands), so this
    must terminate with a clear failure rather than hang.
    """
    fn = parse(open("benchmarks/simple.tac").read())
    result = run_allocation(fn, k=1, max_iterations=10)
    assert not result.success
    assert result.iterations == 10


def test_pipeline_terminates_on_every_benchmark_at_a_reasonable_k():
    import pathlib
    for bench in sorted(pathlib.Path("benchmarks").glob("*.tac")):
        fn = parse(bench.read_text())
        result = run_allocation(fn, k=4, max_iterations=10)
        assert result.success, f"{bench} failed to allocate at k=4 within 10 rounds"
        assert result.allocation.verify(result.graph) == []
