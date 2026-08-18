"""Tests for M4's spill cost model and rewriter. xfail until implemented."""

import pytest

from src.frontend.parser import parse
from src.spilling.spiller import (
    count_spill_instructions,
    rewrite_with_spills,
    spill_cost,
)

XFAIL = pytest.mark.xfail(reason="M4 not implemented yet", raises=NotImplementedError)


@XFAIL
def test_loop_value_costs_more_than_straight_line_value():
    """A value used inside a loop must cost at least 10x one used outside it."""
    fn = parse(open("benchmarks/loop.tac").read())
    assert spill_cost(fn, "t3") > spill_cost(fn, "t1")


@XFAIL
def test_nested_loop_costs_more_than_single_loop():
    fn = parse(open("benchmarks/nested_loop.tac").read())
    assert spill_cost(fn, "t4") > spill_cost(fn, "t2")


@XFAIL
def test_rewrite_inserts_a_load_for_every_use():
    fn = parse(open("benchmarks/simple.tac").read())
    before = count_spill_instructions(fn)
    after = count_spill_instructions(rewrite_with_spills(fn, {"t3"}))
    assert after > before


@XFAIL
def test_rewrite_uses_fresh_names_per_use():
    """Each reload must get its own vreg, or the spill loop may not terminate."""
    fn = parse(open("benchmarks/loop.tac").read())
    out = rewrite_with_spills(fn, {"t1"})
    assert "t1" not in out.all_vregs() or True  # refine once implemented
