"""M1 — control-flow graph construction and loop-depth annotation.

Owner: Member 1
Status: implemented.

WHAT THIS MODULE DOES
---------------------
The parser gives you a flat list of instructions. This module chops that list into
basic blocks and works out which block can follow which.

A *basic block* is a straight-line run of instructions with one way in (at the top) and
one way out (at the bottom). A new block starts whenever we hit:
  - a `label` instruction, because someone can jump to it, or
  - the instruction right after a `goto`, `if..goto` or `ret`, because control might
    not reach it from the line above.

Then they are connected:
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
that appears earlier (or equal) in source order. Every block from the target of a back
edge up to its source is inside that loop, so bump all their depths by one.
"""

from __future__ import annotations

from src.ir import BasicBlock, Function, Instr, Op


def build_cfg(fn: Function) -> Function:
    """Split the parsed instruction list into basic blocks and connect them.

    Reads `fn._parsed_instrs` (set by the parser), fills in `fn.blocks` and `fn.entry`.
    Returns the same Function for convenient chaining.
    """
    instrs: list[Instr] = getattr(fn, "_parsed_instrs", None) or []
    if not instrs:
        raise ValueError(f"function {fn.name!r} has no instructions to build a CFG from")

    leaders = _find_leaders(instrs)

    # Slice the flat instruction list into one run per leader.
    runs: list[list[Instr]] = []
    for i, start in enumerate(leaders):
        end = leaders[i + 1] if i + 1 < len(leaders) else len(instrs)
        runs.append(instrs[start:end])

    # Number blocks B0, B1, ... in source order; remember which block a label opens.
    block_names = [f"B{n}" for n in range(len(runs))]
    label_to_block: dict[str, str] = {}
    for name, run in zip(block_names, runs):
        first = run[0]
        if first.op is Op.LABEL:
            label_to_block[first.label] = name

    fn.blocks = {name: BasicBlock(name=name, instrs=list(run))
                 for name, run in zip(block_names, runs)}
    fn.entry = block_names[0]

    # Wire up successors from each block's last instruction.
    for idx, (name, run) in enumerate(zip(block_names, runs)):
        block = fn.blocks[name]
        last = run[-1]
        fallthrough = block_names[idx + 1] if idx + 1 < len(block_names) else None

        if last.op is Op.GOTO:
            block.succs = [_resolve_label(label_to_block, last)]
        elif last.op is Op.IFGOTO:
            succs = [_resolve_label(label_to_block, last)]
            if fallthrough is not None:
                succs.append(fallthrough)
            block.succs = succs
        elif last.op is Op.RET:
            block.succs = []
        else:
            block.succs = [fallthrough] if fallthrough is not None else []

    # Invert succs -> preds.
    for block in fn.blocks.values():
        block.preds = []
    for block in fn.blocks.values():
        for s in block.succs:
            fn.blocks[s].preds.append(block.name)

    return fn


def _resolve_label(label_to_block: dict[str, str], instr: Instr) -> str:
    try:
        return label_to_block[instr.label]
    except KeyError:
        raise ValueError(f"line {instr.line}: undefined label {instr.label!r}") from None


def _find_leaders(instrs: list[Instr]) -> list[int]:
    """Indices in `instrs` where a new basic block must start."""
    leaders = {0}
    for i, instr in enumerate(instrs):
        if _starts_block(instr):
            leaders.add(i)
        if _ends_block(instr) and i + 1 < len(instrs):
            leaders.add(i + 1)
    return sorted(leaders)


def compute_loop_depth(fn: Function) -> None:
    """Annotate every block with its loop nesting depth.

    A back edge is a CFG edge B -> T where T does not come after B in source order
    (T's index <= B's index). Every block from T to B inclusive is part of the loop
    that edge closes, so each gets its `loop_depth` bumped by one. A block that is
    the body of two overlapping loops (nested, or two back edges sharing code) is
    bumped once per enclosing loop, which is exactly what we want.
    """
    order = fn.block_order()
    index = {b.name: i for i, b in enumerate(order)}

    for b in order:
        b.loop_depth = 0

    for b in order:
        for s in b.succs:
            if index[s] <= index[b.name]:
                lo, hi = index[s], index[b.name]
                for i in range(lo, hi + 1):
                    order[i].loop_depth += 1


def _starts_block(instr: Instr) -> bool:
    """A label always begins a new basic block."""
    return instr.op is Op.LABEL


def _ends_block(instr: Instr) -> bool:
    """Branches and returns always end a basic block."""
    return instr.op in (Op.GOTO, Op.IFGOTO, Op.RET)
