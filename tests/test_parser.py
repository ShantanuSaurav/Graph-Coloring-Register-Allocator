"""Tests for M1's parser. These pass today.

Test-plan categories, per our Review 1 test strategy:
  - valid    : well-formed programs that must parse
  - invalid  : malformed input that must raise ParseError with the right line number
  - boundary : minimal and edge-case programs
"""

import pytest

from src.frontend.parser import ParseError, parse, tokenize
from src.ir import Op, is_vreg

# --------------------------------------------------------------------- valid


def test_parses_minimal_function():
    fn = parse("func main\n  t1 = 1\n  ret t1\nend\n")
    assert fn.name == "main"
    assert len(fn._parsed_instrs) == 2


def test_recognises_every_instruction_form():
    src = """func f
      t1 = 5
      t2 = t1
      t3 = t1 + t2
    label L1
      goto L1
      if t1 < t2 goto L1
      ret t3
    end
    """
    ops = [i.op for i in parse(src)._parsed_instrs]
    assert ops == [Op.CONST, Op.COPY, Op.BINOP, Op.LABEL, Op.GOTO, Op.IFGOTO, Op.RET]


def test_binop_fields_are_correct():
    ins = parse("func f\n t3 = t1 + t2\n ret t3\nend")._parsed_instrs[0]
    assert (ins.dst, ins.src1, ins.operator, ins.src2) == ("t3", "t1", "+", "t2")


def test_copy_is_distinguished_from_const():
    body = parse("func f\n t1 = 7\n t2 = t1\n ret t2\nend")._parsed_instrs
    assert body[0].op is Op.CONST and body[0].const == "7"
    assert body[1].op is Op.COPY and body[1].is_copy()


def test_defs_and_uses():
    ins = parse("func f\n t3 = t1 + t2\n ret t3\nend")._parsed_instrs[0]
    assert ins.defs() == {"t3"}
    assert ins.uses() == {"t1", "t2"}


def test_constants_are_not_treated_as_registers():
    ins = parse("func f\n t2 = t1 + 100\n ret t2\nend")._parsed_instrs[0]
    assert ins.uses() == {"t1"}


def test_comments_and_blank_lines_ignored():
    src = "# header\nfunc f\n\n  t1 = 1   # trailing\n\n  ret t1\nend\n"
    assert len(parse(src)._parsed_instrs) == 2


@pytest.mark.parametrize("name,expected", [
    ("t0", True), ("t1", True), ("t42", True),
    ("t", False), ("x1", False), ("tx", False), ("100", False),
])
def test_is_vreg(name, expected):
    assert is_vreg(name) is expected


def test_all_benchmarks_parse():
    import pathlib
    for path in sorted(pathlib.Path("benchmarks").glob("*.tac")):
        fn = parse(path.read_text())
        assert fn._parsed_instrs, f"{path} produced no instructions"


# ------------------------------------------------------------------- invalid


def test_missing_func_header():
    with pytest.raises(ParseError):
        parse("t1 = 1\nret t1\nend")


def test_missing_end():
    with pytest.raises(ParseError):
        parse("func f\n t1 = 1\n ret t1\n")


def test_unknown_arithmetic_operator():
    with pytest.raises(ParseError) as e:
        parse("func f\n t3 = t1 ^ t2\n ret t3\nend")
    assert e.value.line == 2


def test_unknown_relational_operator():
    with pytest.raises(ParseError):
        parse("func f\n if t1 =< t2 goto L\n ret t1\nend")


def test_garbage_line_reports_its_number():
    with pytest.raises(ParseError) as e:
        parse("func f\n t1 = 1\n this is nonsense\n ret t1\nend")
    assert e.value.line == 3


def test_empty_program():
    with pytest.raises(ParseError):
        parse("")


def test_empty_body():
    with pytest.raises(ParseError):
        parse("func f\nend")


# ------------------------------------------------------------------ boundary


def test_negative_constant():
    ins = parse("func f\n t1 = -5\n ret t1\nend")._parsed_instrs[0]
    assert ins.op is Op.CONST and ins.const == "-5"


def test_self_referencing_assignment():
    ins = parse("func f\n t1 = t1 + 1\n ret t1\nend")._parsed_instrs[0]
    assert ins.defs() == {"t1"} and ins.uses() == {"t1"}


def test_tokenize_preserves_line_numbers():
    toks = tokenize("# comment\n\nfunc f\n  t1 = 1\n")
    assert [ln for ln, _ in toks] == [3, 4]
