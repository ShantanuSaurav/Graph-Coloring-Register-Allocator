"""M1 — tokenizer and parser for our three-address IR.

This module is complete and tested. It turns a .tac file into a Function whose blocks
are filled in but whose CFG edges are left to cfg.py.

Owner: Member 1
"""

from __future__ import annotations

from src.ir import ARITH_OPS, REL_OPS, Function, Instr, Op


class ParseError(Exception):
    """Raised on malformed input. Always carries the offending line number."""

    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


def tokenize(text: str) -> list[tuple[int, list[str]]]:
    """Split source into (line_number, tokens) pairs.

    Blank lines and comments are dropped. Comments start with '#' and run to end of line.
    """
    out: list[tuple[int, list[str]]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if line:
            out.append((lineno, line.split()))
    return out


def parse(text: str) -> Function:
    """Parse a complete .tac source into a Function.

    Raises ParseError with a line number on any malformed instruction.
    """
    lines = tokenize(text)
    if not lines:
        raise ParseError(0, "empty program")

    lineno, toks = lines[0]
    if len(toks) != 2 or toks[0] != "func":
        raise ParseError(lineno, "program must start with 'func <name>'")

    fn = Function(name=toks[1])
    instrs: list[Instr] = []
    saw_end = False

    for lineno, toks in lines[1:]:
        if toks == ["end"]:
            saw_end = True
            break
        instrs.append(_parse_instr(lineno, toks))

    if not saw_end:
        raise ParseError(lines[-1][0], "missing 'end' at the end of the function")
    if not instrs:
        raise ParseError(lines[0][0], "function body is empty")

    fn._parsed_instrs = instrs  # type: ignore[attr-defined]
    return fn


def _parse_instr(lineno: int, t: list[str]) -> Instr:
    """Parse one instruction from its token list."""

    # label L1
    if t[0] == "label":
        if len(t) != 2:
            raise ParseError(lineno, "expected 'label <name>'")
        return Instr(Op.LABEL, lineno, label=t[1])

    # goto L1
    if t[0] == "goto":
        if len(t) != 2:
            raise ParseError(lineno, "expected 'goto <name>'")
        return Instr(Op.GOTO, lineno, label=t[1])

    # ret t5
    if t[0] == "ret":
        if len(t) != 2:
            raise ParseError(lineno, "expected 'ret <operand>'")
        return Instr(Op.RET, lineno, src1=t[1])

    # if t1 < t2 goto L1
    if t[0] == "if":
        if len(t) != 6 or t[4] != "goto":
            raise ParseError(lineno, "expected 'if <op> <rel> <op> goto <label>'")
        if t[2] not in REL_OPS:
            raise ParseError(lineno, f"unknown relational operator {t[2]!r}")
        return Instr(Op.IFGOTO, lineno, src1=t[1], src2=t[3], operator=t[2], label=t[5])

    # everything else is an assignment: dst = ...
    if len(t) < 3 or t[1] != "=":
        raise ParseError(lineno, f"unrecognised instruction {' '.join(t)!r}")

    dst = t[0]

    # dst = src1 OP src2
    if len(t) == 5:
        if t[3] not in ARITH_OPS:
            raise ParseError(lineno, f"unknown arithmetic operator {t[3]!r}")
        return Instr(Op.BINOP, lineno, dst=dst, src1=t[2], src2=t[4], operator=t[3])

    # dst = src   or   dst = 5
    if len(t) == 3:
        rhs = t[2]
        if _is_literal(rhs):
            return Instr(Op.CONST, lineno, dst=dst, const=rhs)
        return Instr(Op.COPY, lineno, dst=dst, src1=rhs)

    raise ParseError(lineno, f"malformed assignment {' '.join(t)!r}")


def _is_literal(tok: str) -> bool:
    """True for integer literals, including negatives."""
    return tok.lstrip("-").isdigit()


def parse_file(path: str) -> Function:
    """Convenience wrapper: read a file from disk and parse it."""
    with open(path, encoding="utf-8") as fh:
        return parse(fh.read())
