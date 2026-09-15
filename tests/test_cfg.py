"""Tests for M1's CFG builder and loop-depth analysis."""

import pytest

from src.frontend.cfg import build_cfg, compute_loop_depth
from src.frontend.parser import parse


def _build(src: str):
    fn = parse(src)
    build_cfg(fn)
    return fn


# --------------------------------------------------------------- basic shape


def test_straight_line_is_one_block():
    fn = _build("func f\n t1 = 1\n t2 = 2\n ret t1\nend")
    assert list(fn.blocks) == ["B0"]
    assert fn.entry == "B0"
    assert fn.blocks["B0"].succs == []
    assert fn.blocks["B0"].preds == []


def test_label_starts_a_new_block():
    fn = _build("func f\n t1 = 1\n label L1\n t2 = 2\n ret t2\nend")
    assert list(fn.blocks) == ["B0", "B1"]
    assert fn.blocks["B0"].instrs[0].op.name == "CONST"
    assert fn.blocks["B1"].instrs[0].op.name == "LABEL"


def test_goto_connects_to_its_target():
    fn = _build("func f\n goto L1\n label L1\n ret t1\nend")
    b0, b1 = fn.blocks["B0"], fn.blocks["B1"]
    assert b0.succs == ["B1"]
    assert b1.preds == ["B0"]


def test_ifgoto_has_target_and_fallthrough():
    src = "func f\n if t1 < t2 goto L1\n t3 = 1\n label L1\n ret t3\nend"
    fn = _build(src)
    b0, b1, b2 = fn.blocks["B0"], fn.blocks["B1"], fn.blocks["B2"]
    assert b0.succs == ["B2", "B1"]   # [target, fallthrough]
    assert sorted(b2.preds) == ["B0", "B1"]


def test_fallthrough_to_next_block_without_a_branch():
    fn = _build("func f\n t1 = 1\n label L1\n ret t1\nend")
    b0, b1 = fn.blocks["B0"], fn.blocks["B1"]
    assert b0.succs == ["B1"]
    assert b1.preds == ["B0"]


def test_return_block_has_no_successors():
    fn = _build("func f\n t1 = 1\n ret t1\nend")
    assert fn.blocks["B0"].succs == []


def test_undefined_label_raises_clear_error():
    fn = parse("func f\n goto NOWHERE\n ret t1\nend")
    with pytest.raises(ValueError):
        build_cfg(fn)


def test_preds_and_succs_are_consistent_on_every_benchmark():
    import pathlib
    for path in sorted(pathlib.Path("benchmarks").glob("*.tac")):
        fn = _build(path.read_text())
        for block in fn.block_order():
            for succ in block.succs:
                assert block.name in fn.blocks[succ].preds, (
                    f"{path}: {block.name} -> {succ} missing matching pred"
                )
            for pred in block.preds:
                assert block.name in fn.blocks[pred].succs, (
                    f"{path}: {pred} -> {block.name} missing matching succ"
                )


# --------------------------------------------------------------------- loops


def test_no_loop_has_depth_zero():
    fn = _build(open("benchmarks/diamond.tac").read())
    compute_loop_depth(fn)
    assert all(b.loop_depth == 0 for b in fn.block_order())


def test_single_loop_has_depth_one():
    fn = _build(open("benchmarks/loop.tac").read())
    compute_loop_depth(fn)
    depths = {b.name: b.loop_depth for b in fn.block_order()}
    # entry and exit blocks are outside the loop; the header/body is inside it.
    assert depths["B0"] == 0
    assert depths["B1"] == 1
    assert depths["B2"] == 0


def test_nested_loop_has_depth_two_in_the_inner_body():
    fn = _build(open("benchmarks/nested_loop.tac").read())
    compute_loop_depth(fn)
    depths = {b.name: b.loop_depth for b in fn.block_order()}
    assert depths["B0"] == 0    # before the loops
    assert depths["B1"] == 1    # outer loop header
    assert depths["B2"] == 2    # inner loop body
    assert depths["B3"] == 1    # back in the outer loop, after the inner loop
    assert depths["B4"] == 0    # after both loops


def test_branches_inside_a_loop_still_get_the_loop_depth():
    """An if/goto diamond nested inside a loop: every block in the loop is depth 1."""
    src = (
        "func f\n"
        " t1 = 0\n"
        "label L1\n"
        " if t1 < 10 goto EVEN\n"
        " t2 = 1\n"
        " goto MERGE\n"
        "label EVEN\n"
        " t2 = 2\n"
        "label MERGE\n"
        " t1 = t1 + t2\n"
        " if t1 < 100 goto L1\n"
        " ret t1\n"
        "end"
    )
    fn = _build(src)
    compute_loop_depth(fn)
    depths = {b.name: b.loop_depth for b in fn.block_order()}
    # B0 = init before the loop, B5 = "ret" after it; everything in between
    # (header, both arms of the branch, and the merge point) is inside the loop.
    assert depths["B0"] == 0
    assert depths["B5"] == 0
    for name in ("B1", "B2", "B3", "B4"):
        assert depths[name] == 1, f"{name} expected depth 1, got {depths[name]}"
