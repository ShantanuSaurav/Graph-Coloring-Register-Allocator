"""Tests for M2's liveness analysis."""

from src.analysis.liveness import analyse, compute_use_def, live_ranges
from src.frontend.cfg import build_cfg, compute_loop_depth
from src.frontend.parser import parse


def _prepare(src: str):
    fn = parse(src)
    build_cfg(fn)
    compute_loop_depth(fn)
    analyse(fn)
    return fn


# ----------------------------------------------------------------- use/def


def test_use_def_simple_block():
    fn = parse("func f\n t3 = t1 + t2\n ret t3\nend")
    block = build_cfg(fn).blocks["B0"]
    use, defined = compute_use_def(block)
    assert use == {"t1", "t2"}
    assert defined == {"t3"}


def test_self_referencing_use_is_not_masked_by_its_own_def():
    """`t1 = t1 + 1`: t1 is read before this block writes it, so it belongs in USE."""
    fn = parse("func f\n t1 = t1 + 1\n ret t1\nend")
    block = build_cfg(fn).blocks["B0"]
    use, defined = compute_use_def(block)
    assert "t1" in use
    assert "t1" in defined


def test_def_before_use_does_not_count_as_use():
    """t1 is written before it is ever read in this block, so it is not a USE."""
    fn = parse("func f\n t1 = 5\n t2 = t1 + 1\n ret t2\nend")
    block = build_cfg(fn).blocks["B0"]
    use, defined = compute_use_def(block)
    assert "t1" not in use
    assert defined == {"t1", "t2"}


# -------------------------------------------------------------- multi-block


def test_value_live_across_a_fallthrough():
    fn = _prepare("func f\n t1 = 1\n label L1\n t2 = t1 + 1\n ret t2\nend")
    b0, b1 = fn.blocks["B0"], fn.blocks["B1"]
    assert "t1" in b0.live_out
    assert "t1" in b1.live_in


def test_diamond_join_merges_both_branches():
    """In diamond.tac, t3 is defined differently on each arm but used after the join,
    so it must be live-out of both THEN and the fallthrough arm, and live-in at JOIN.
    """
    fn = _prepare(open("benchmarks/diamond.tac").read())
    then_arm = fn.blocks["B1"]   # t3 = t1 + t1; goto JOIN
    else_arm = fn.blocks["B2"]   # label THEN; t3 = t2 + t2
    join = fn.blocks["B3"]       # label JOIN; t4 = t3 + t1; ret t4
    assert "t3" in then_arm.live_out
    assert "t3" in else_arm.live_out
    assert "t3" in join.live_in
    assert "t1" in join.live_in  # t4 = t3 + t1 also needs t1


def test_loop_header_is_live_in_on_itself():
    """loop.tac's single-block loop: t1 and t2 must be live on entry to the block
    that both defines and re-reads them every iteration.
    """
    fn = _prepare(open("benchmarks/loop.tac").read())
    header = fn.blocks["B1"]
    assert {"t1", "t2"} <= header.live_in
    assert {"t1", "t2"} <= header.live_out


def test_nested_loop_reaches_a_fixed_point():
    """Just needs to terminate and produce a plausible result — the real check is
    that this doesn't loop forever and that the outermost value (t1) is live
    everywhere inside both loops.
    """
    fn = _prepare(open("benchmarks/nested_loop.tac").read())
    for name in ("B1", "B2", "B3"):
        assert "t1" in fn.blocks[name].live_in


def test_dead_value_is_not_live_anywhere():
    """A value that is defined and never used again should not appear in any
    live_in/live_out set."""
    fn = _prepare("func f\n t1 = 1\n t2 = 2\n ret t1\nend")
    for block in fn.block_order():
        assert "t2" not in block.live_in
        assert "t2" not in block.live_out


# ------------------------------------------------------------- live_ranges


def test_live_ranges_records_points_for_a_live_value():
    fn = _prepare("func f\n t1 = 1\n t2 = t1 + 1\n ret t2\nend")
    ranges = live_ranges(fn)
    # t1 is live in before instruction 1 (t2 = t1 + 1), which reads it.
    assert ("B0", 1) in ranges["t1"]
    # t1 is dead before instruction 0 (its own definition) and after instruction 1.
    assert ("B0", 0) not in ranges.get("t1", set())
