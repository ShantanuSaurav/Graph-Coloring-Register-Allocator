"""M2 - live-variable analysis.

Owner: Member 2
Status: implemented.

WHAT "LIVE" MEANS
-----------------
A virtual register is *live* at a point in the program if its current value might still
be read later. It goes live when written and stops being live after its last read. If
two registers are never live at the same moment they can share a physical register -
that is the entire basis of this project.

WHY THE ANALYSIS RUNS BACKWARDS
-------------------------------
Whether a value is needed *here* depends on whether anything *later* reads it. So
information flows from uses backwards towards definitions.

THE EQUATIONS
-------------
For each basic block B:

    USE[B] = registers read in B before being written in B
    DEF[B] = registers written in B

    OUT[B] = union of IN[S] for every successor S of B
    IN[B]  = USE[B] | (OUT[B] - DEF[B])

Start with every set empty and apply the equations repeatedly until nothing changes
(a "fixed point"). Iterating blocks in reverse order converges faster.

Read IN[B] as: "these registers are live on entry to B."
"""

from __future__ import annotations

from collections import defaultdict

from src.ir import BasicBlock, Function


def compute_use_def(block: BasicBlock) -> tuple[set[str], set[str]]:
    """Return (USE, DEF) for a single block.

    Walk the instructions front to back, keeping two sets:
      - if a register is read and is not already in DEF, add it to USE
        (it was read before this block wrote it, so its value comes from outside)
      - then add whatever the instruction writes to DEF

    Doing it the other way round would give the wrong answer for `t1 = t1 + 1`.
    """
    use: set[str] = set()
    defined: set[str] = set()
    for instr in block.instrs:
        for reg in instr.uses():
            if reg not in defined:
                use.add(reg)
        defined |= instr.defs()
    return use, defined


def analyse(fn: Function) -> None:
    """Run liveness to a fixed point, filling in live_in and live_out on every block."""
    order = fn.block_order()

    use_of: dict[str, set[str]] = {}
    def_of: dict[str, set[str]] = {}
    for block in order:
        use_of[block.name], def_of[block.name] = compute_use_def(block)
        block.live_in = set()
        block.live_out = set()

    changed = True
    while changed:
        changed = False
        for block in reversed(order):
            new_out: set[str] = set()
            for succ_name in block.succs:
                new_out |= fn.blocks[succ_name].live_in
            new_in = use_of[block.name] | (new_out - def_of[block.name])

            if new_in != block.live_in or new_out != block.live_out:
                changed = True
            block.live_in = new_in
            block.live_out = new_out


def live_ranges(fn: Function) -> dict[str, set[tuple[str, int]]]:
    """Map each vreg to the (block name, instruction index) points where it is live.

    A vreg is recorded against index `i` when it is live *immediately before*
    instruction `i` executes (i.e. it is part of that instruction's IN set). This is
    the information the interference builder effectively uses, and it is handy for
    debugging or for annotating a Graphviz rendering of the CFG.

    Requires `analyse(fn)` to have already populated `live_in` / `live_out`.
    """
    ranges: dict[str, set[tuple[str, int]]] = defaultdict(set)
    for block in fn.block_order():
        live = set(block.live_out)
        for idx in range(len(block.instrs) - 1, -1, -1):
            instr = block.instrs[idx]
            live = (live - instr.defs()) | instr.uses()
            for vreg in live:
                ranges[vreg].add((block.name, idx))
    return dict(ranges)
