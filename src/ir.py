"""Shared IR data types.

Every module in this project reads and writes these classes. Treat this file as the
contract between the four modules: changing it means telling the whole team.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Op(Enum):
    """The kinds of instruction our three-address IR supports."""

    CONST = "const"      # dst = 5
    COPY = "copy"        # dst = src1              (coalescing candidate)
    BINOP = "binop"      # dst = src1 <arith> src2
    LABEL = "label"      # label L1
    GOTO = "goto"        # goto L1
    IFGOTO = "ifgoto"    # if src1 <rel> src2 goto L1
    RET = "ret"          # ret src1
    LOAD = "load"        # dst = spill_slot        (inserted by the spiller)
    STORE = "store"      # spill_slot = src1       (inserted by the spiller)


ARITH_OPS = {"+", "-", "*", "/", "%"}
REL_OPS = {"<", "<=", ">", ">=", "==", "!="}


@dataclass
class Instr:
    """One three-address instruction.

    `dst` and the `src` fields hold virtual register names such as "t3", or None.
    Constants are stored in `const` (for CONST) or inline in `src1`/`src2` as literal
    strings for operands that are not registers.
    """

    op: Op
    line: int                          # 1-based source line, for error messages
    dst: str | None = None
    src1: str | None = None
    src2: str | None = None
    operator: str | None = None        # "+" for BINOP, "<" for IFGOTO
    label: str | None = None           # target for LABEL / GOTO / IFGOTO
    const: str | None = None           # literal value for CONST
    slot: int | None = None            # stack slot for LOAD / STORE

    def defs(self) -> set[str]:
        """Virtual registers this instruction writes."""
        return {self.dst} if self.dst and is_vreg(self.dst) else set()

    def uses(self) -> set[str]:
        """Virtual registers this instruction reads."""
        return {s for s in (self.src1, self.src2) if s and is_vreg(s)}

    def is_copy(self) -> bool:
        """True for `dst = src`, the instruction coalescing tries to remove."""
        return self.op is Op.COPY

    def __str__(self) -> str:
        if self.op is Op.CONST:
            return f"{self.dst} = {self.const}"
        if self.op is Op.COPY:
            return f"{self.dst} = {self.src1}"
        if self.op is Op.BINOP:
            return f"{self.dst} = {self.src1} {self.operator} {self.src2}"
        if self.op is Op.LABEL:
            return f"label {self.label}"
        if self.op is Op.GOTO:
            return f"goto {self.label}"
        if self.op is Op.IFGOTO:
            return f"if {self.src1} {self.operator} {self.src2} goto {self.label}"
        if self.op is Op.RET:
            return f"ret {self.src1}"
        if self.op is Op.LOAD:
            return f"{self.dst} = spill[{self.slot}]"
        if self.op is Op.STORE:
            return f"spill[{self.slot}] = {self.src1}"
        return f"<{self.op}>"


@dataclass
class BasicBlock:
    """A straight-line run of instructions with one entry and one exit.

    M1 builds these. M2 reads `instrs`, `succs` and `preds` to run liveness, and writes
    its results into `live_in` and `live_out`.
    """

    name: str
    instrs: list[Instr] = field(default_factory=list)
    succs: list[str] = field(default_factory=list)   # successor block names
    preds: list[str] = field(default_factory=list)   # predecessor block names

    loop_depth: int = 0                              # filled in by M1
    live_in: set[str] = field(default_factory=set)   # filled in by M2
    live_out: set[str] = field(default_factory=set)  # filled in by M2

    def __repr__(self) -> str:
        return f"BasicBlock({self.name!r}, {len(self.instrs)} instrs, succs={self.succs})"


@dataclass
class Function:
    """A parsed function: its blocks plus the CFG that connects them."""

    name: str
    blocks: dict[str, BasicBlock] = field(default_factory=dict)
    entry: str | None = None

    def block_order(self) -> list[BasicBlock]:
        """Blocks in source order — the order the parser created them."""
        return list(self.blocks.values())

    def all_vregs(self) -> set[str]:
        """Every virtual register mentioned anywhere in the function."""
        out: set[str] = set()
        for b in self.blocks.values():
            for i in b.instrs:
                out |= i.defs() | i.uses()
        return out

    def instruction_count(self) -> int:
        return sum(len(b.instrs) for b in self.blocks.values())


def is_vreg(name: str) -> bool:
    """A virtual register is `t` followed by one or more digits: t0, t1, t42.

    Anything else in an operand position is a literal constant.
    """
    return len(name) > 1 and name[0] == "t" and name[1:].isdigit()
