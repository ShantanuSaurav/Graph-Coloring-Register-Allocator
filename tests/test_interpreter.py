import pytest
from src.analysis.interpreter import ExecutionError, execute
from src.frontend.parser import parse
from src.frontend.cfg import build_cfg
from src.spilling.spiller import rewrite_with_spills


def test_simple_execution():
    fn = parse('func main\n t1 = 4\n t2 = 6\n t3 = t1 * t2\n ret t3\nend')
    assert execute(fn) == 24


def test_spilling_preserves_value():
    fn = parse('func main\n t1 = 4\n t2 = 6\n t3 = t1 * t2\n ret t3\nend')
    assert execute(rewrite_with_spills(fn, {'t1', 't3'})) == execute(fn)


def test_branch_and_loop():
    fn = parse('func main\n t1 = 0\n t2 = 3\nlabel L\n t1 = t1 + 1\n if t1 < t2 goto L\n ret t1\nend')
    assert execute(fn) == 3
    assert execute(rewrite_with_spills(fn, {'t1'})) == 3


def test_step_budget():
    fn = parse('func main\n label L\n goto L\n ret 1\nend')
    with pytest.raises(ExecutionError, match='exceeded'):
        execute(fn, max_steps=100)


def test_undefined_operand():
    fn = parse('func main\n ret t4\nend')
    with pytest.raises(ExecutionError, match='undefined'):
        execute(fn)
