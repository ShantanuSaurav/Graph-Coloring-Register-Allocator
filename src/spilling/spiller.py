"""M4 — spill cost model and code rewriting.

Owner: Member 4
Status: TODO — this is your part to implement.

WHAT SPILLING IS
----------------
When K registers are not enough, some value has to live in memory instead. The program
still computes the right answer; it just runs slower, because every read becomes a load
from the stack and every write becomes a store.

WHICH VALUE TO SPILL
--------------------
Not the one used constantly. We pick the candidate that minimises

    cost / degree

where

    cost = sum over every definition and use of  10 ** loop_depth(that instruction)

The loop-depth weighting is the important part: an instruction inside one loop is
counted 10x, inside a nested loop 100x. So a value used in a hot loop is enormously
expensive to spill, and a value used once at the end of a function is cheap.

Dividing by degree favours spilling a node that relieves pressure on many neighbours —
one spill that unblocks ten nodes beats one that unblocks two.

WHAT REWRITING DOES
-------------------
For a spilled vreg v, allocate a stack slot, then:
  - after every instruction that defines v, insert  `store slot, v`
  - before every instruction that uses v,  insert   `v' = load slot`  with a FRESH
    vreg name for each use

Using a fresh name per use is what makes this terminate: the new live ranges are only
one or two instructions long, so they interfere with almost nothing and colour easily.
Reusing the same name would leave a long live range and the loop could spin forever.

Then the whole pipeline runs again from the parser on the rewritten code.
"""

from __future__ import annotations

from src.analysis.interference import InterferenceGraph
from src.ir import Function

MAX_ITERATIONS = 10  # safety cap from our risk register


def spill_cost(fn: Function, vreg: str) -> float:
    """Estimated dynamic cost of spilling `vreg`.

    TODO(M4): implement.

        total = 0.0
        for each block, for each instruction in it:
            if vreg in instr.defs() or vreg in instr.uses():
                total += 10 ** block.loop_depth
        return total

    Depends on M1 having filled in block.loop_depth.
    """
    raise NotImplementedError("M4: spill_cost is not implemented yet")


def choose_spill(fn: Function, graph: InterferenceGraph, candidates: set[str]) -> str:
    """Pick the cheapest candidate to spill, by cost / degree.

    TODO(M4): implement. Guard against degree 0 — divide by max(degree, 1).
    """
    raise NotImplementedError("M4: choose_spill is not implemented yet")


def rewrite_with_spills(fn: Function, spilled: set[str]) -> Function:
    """Return a new Function with loads and stores inserted for every spilled vreg.

    TODO(M4): implement.

    For each spilled vreg, assign it a stack slot number. Then walk every block and
    build a new instruction list:
      - a use of v becomes: `v_fresh = load slot` inserted before, and the instruction
        rewritten to reference v_fresh
      - a def of v becomes: the instruction unchanged, followed by `store slot, v`

    Generate fresh names that cannot collide with existing ones — a counter starting
    above the highest existing t-number works.
    """
    raise NotImplementedError("M4: rewrite_with_spills is not implemented yet")


def count_spill_instructions(fn: Function) -> int:
    """Count LOAD and STORE instructions — the metric for objective O3.

    TODO(M4): implement. This is how we measure the 20% reduction claim, by comparing
    this number against a baseline allocator on the same input and the same K.
    """
    raise NotImplementedError("M4: count_spill_instructions is not implemented yet")
