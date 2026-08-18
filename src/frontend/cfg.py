"""M1 — control-flow graph construction and loop-depth annotation.

Owner: Member 1
Status: TODO — this is your part to implement.

WHAT THIS MODULE DOES
---------------------
The parser gives you a flat list of instructions. This module chops that list into
basic blocks and works out which block can follow which.

A *basic block* is a straight-line run of instructions with one way in (at the top) and
one way out (at the bottom). You start a new block whenever you hit:
  - a `label` instruction, because someone can jump to it, or
  - the instruction right after a `goto`, `if..goto` or `ret`, because control might
    not reach it from the line above.

Then you connect them:
  - a block ending in `goto L`      has one successor: the block starting at label L
  - a block ending in `if .. goto L` has two: label L, and the next block in order
  - a block ending in `ret`         has no successors
  - any other block falls through to the next block in order

LOOP DEPTH
----------
Every block gets a `loop_depth`. Depth 0 means not in a loop, 1 means inside one loop,
2 means inside a loop inside a loop, and so on. The spiller (M4) uses this: cost is
`10 ** loop_depth` per use, so a value used inside a nested loop is 100x more expensive
to spill than one used at the top level.

The simple way to find loops in our IR: a *back edge* is an edge from a block to a block
that appears earlier in source order. Every block from the target of a back edge up to
its source is inside that loop, so bump all their depths by one.
"""

from __future__ import annotations

from src.ir import BasicBlock, Function, Instr, Op


def build_cfg(fn: Function) -> Function:
    """Split the parsed instruction list into basic blocks and connect them.

    Reads `fn._parsed_instrs` (set by the parser), fills in `fn.blocks` and `fn.entry`.
    Returns the same Function for convenient chaining.

    TODO(M1): implement.

    Suggested steps:
      1. Walk the instruction list and mark every index that starts a new block.
      2. Create a BasicBlock for each run, naming them "B0", "B1", ... or by their label.
      3. Build a map from label name -> block name.
      4. For each block, inspect its last instruction and fill in `succs`.
      5. Fill in `preds` by inverting `succs`.
      6. Set `fn.entry` to the first block.
    """
    raise NotImplementedError("M1: build_cfg is not implemented yet")


def compute_loop_depth(fn: Function) -> None:
    """Annotate every block with its loop nesting depth.

    TODO(M1): implement.

    Suggested approach:
      1. Number the blocks in source order.
      2. Find back edges: an edge B -> T where T's number <= B's number.
      3. For each back edge, every block numbered between T and B is in that loop —
         increment its `loop_depth`.
    """
    raise NotImplementedError("M1: compute_loop_depth is not implemented yet")


def _starts_block(instr: Instr) -> bool:
    """A label always begins a new basic block."""
    return instr.op is Op.LABEL


def _ends_block(instr: Instr) -> bool:
    """Branches and returns always end a basic block."""
    return instr.op in (Op.GOTO, Op.IFGOTO, Op.RET)
