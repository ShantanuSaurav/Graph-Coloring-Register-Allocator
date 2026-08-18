"""M2 - live-variable analysis.

Owner: Member 2
Status: TODO - this is your part to implement.

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

from src.ir import BasicBlock, Function


def compute_use_def(block: BasicBlock) -> tuple[set[str], set[str]]:
    """Return (USE, DEF) for a single block.

    TODO(M2): implement.

    Careful with ordering. Walk the instructions front to back, keeping two sets:
      - if a register is read and is not already in DEF, add it to USE
        (it was read before this block wrote it, so its value comes from outside)
      - then add whatever the instruction writes to DEF

    Doing it the other way round gives the wrong answer for `t1 = t1 + 1`.
    """
    raise NotImplementedError("M2: compute_use_def is not implemented yet")


def analyse(fn: Function) -> None:
    """Run liveness to a fixed point, filling in live_in and live_out on every block.

    TODO(M2): implement.

    Suggested loop:
        compute USE/DEF for every block once, up front
        repeat:
            changed = False
            for each block in reverse order:
                new_out = union of live_in of its successors
                new_in  = USE | (new_out - DEF)
                if either differs from what is stored:
                    store it and set changed = True
        until not changed
    """
    raise NotImplementedError("M2: analyse is not implemented yet")


def live_ranges(fn: Function) -> dict[str, set[tuple[str, int]]]:
    """Optional helper: map each vreg to the (block name, instruction index) points
    where it is live. Useful for debugging and for the Graphviz output.

    TODO(M2): implement if you find it helpful.
    """
    raise NotImplementedError("M2: live_ranges is not implemented yet")
