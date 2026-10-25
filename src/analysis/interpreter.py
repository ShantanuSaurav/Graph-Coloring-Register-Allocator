"""Bounded reference interpreter for the educational TAC language.

Executes virtual-register IR before/after spill rewriting to validate semantics.
This does not emulate physical register assignments or machine-code execution.
"""
from __future__ import annotations

import operator
from src.ir import Function, Op


class ExecutionError(ValueError):
    """Invalid arithmetic, an undefined value, or exhausted execution budget."""


_ARITH = {"+": operator.add, "-": operator.sub, "*": operator.mul,
          "%": operator.mod}
_REL = {"<": operator.lt, "<=": operator.le, ">": operator.gt,
        ">=": operator.ge, "==": operator.eq, "!=": operator.ne}


def execute(fn: Function, *, max_steps: int = 100_000) -> int:
    """Run TAC and return the integer from RET, limiting runaway loops."""
    instructions = ([i for block in fn.block_order() for i in block.instrs]
                    if fn.blocks else list(getattr(fn, "_parsed_instrs", [])))
    labels = {i.label: pos for pos, i in enumerate(instructions) if i.op is Op.LABEL}
    registers: dict[str, int] = {}
    stack: dict[int, int] = {}

    def read(value: str | None) -> int:
        if value is None:
            raise ExecutionError("missing operand")
        try:
            return int(value)
        except ValueError:
            if value not in registers:
                raise ExecutionError(f"undefined register: {value}") from None
            return registers[value]

    pc = 0
    for _ in range(max_steps):
        if pc >= len(instructions):
            raise ExecutionError("program ended without returning")
        ins = instructions[pc]
        pc += 1
        if ins.op is Op.CONST:
            registers[ins.dst] = read(ins.const)
        elif ins.op is Op.COPY:
            registers[ins.dst] = read(ins.src1)
        elif ins.op is Op.BINOP:
            a, b = read(ins.src1), read(ins.src2)
            try:
                if ins.operator == "/":
                    # Integer division truncates toward zero. Avoid float
                    # conversion, which overflows on large Python integers.
                    if b == 0:
                        raise ZeroDivisionError("division by zero")
                    magnitude = abs(a) // abs(b)
                    value = -magnitude if (a < 0) != (b < 0) else magnitude
                else:
                    value = _ARITH[ins.operator](a, b)
            except (ZeroDivisionError, OverflowError) as exc:
                raise ExecutionError(str(exc)) from exc
            registers[ins.dst] = value
        elif ins.op is Op.IFGOTO:
            if _REL[ins.operator](read(ins.src1), read(ins.src2)):
                if ins.label not in labels:
                    raise ExecutionError(f"unknown label: {ins.label}")
                pc = labels[ins.label]
        elif ins.op is Op.GOTO:
            if ins.label not in labels:
                raise ExecutionError(f"unknown label: {ins.label}")
            pc = labels[ins.label]
        elif ins.op is Op.RET:
            return read(ins.src1)
        elif ins.op is Op.LOAD:
            if ins.slot not in stack:
                raise ExecutionError(f"uninitialized spill slot: {ins.slot}")
            registers[ins.dst] = stack[ins.slot]
        elif ins.op is Op.STORE:
            stack[ins.slot] = read(ins.src1)
    raise ExecutionError(f"execution exceeded {max_steps} instructions")
