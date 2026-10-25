"""Regression tests for bounded exact fallback and semantic-preserving rewrites."""
import random

import pytest

from src.analysis.interference import InterferenceGraph
from src.analysis.interpreter import execute
from src.colouring.allocator import allocate, exact_colour_bounded, select, simplify
from src.frontend.parser import parse
from src.spilling.spiller import run_allocation


def _graph(edges, n):
    graph = InterferenceGraph()
    for i in range(1, n + 1):
        graph.add_node(f"t{i}")
    for a, b in edges:
        graph.add_edge(a, b)
    return graph


def test_exact_fallback_prevents_unnecessary_heuristic_spill():
    graph = _graph([
        ('t1', 't2'), ('t1', 't3'), ('t1', 't6'),
        ('t2', 't3'), ('t2', 't4'), ('t2', 't5'),
        ('t3', 't4'), ('t4', 't5'), ('t4', 't6'), ('t5', 't6'),
    ], 6)
    stack, _ = simplify(graph, 3)
    assert select(graph, stack, 3).spilled  # the greedy pass misses this coloring
    result = allocate(graph, 3, do_coalesce=False)
    assert result.success
    assert result.verify(graph) == []


def test_uncolourable_triangle_still_reports_spills():
    graph = _graph([('t1','t2'), ('t2','t3'), ('t1','t3')], 3)
    assert exact_colour_bounded(graph, 2) is None
    result = allocate(graph, 2, do_coalesce=False)
    assert not result.success


def test_search_limits_decline_large_graphs():
    graph = _graph([], 19)
    assert exact_colour_bounded(graph, 2) is None
    assert exact_colour_bounded(_graph([], 4), 2, search_budget=0) is None


@pytest.mark.parametrize('seed', range(25))
@pytest.mark.parametrize('k', [2, 3, 4])
def test_random_straightline_semantics_when_allocation_succeeds(seed, k):
    rng = random.Random(seed)
    lines = ['func main', 't1 = 3', 't2 = 7']
    for index in range(3, 12):
        a = f't{rng.randrange(1, index)}'
        b = f't{rng.randrange(1, index)}'
        operator = rng.choice(['+', '-', '*'])
        lines.append(f't{index} = {a} {operator} {b}')
    lines += ['ret t11', 'end']
    source = '\n'.join(lines)
    expected = execute(parse(source))
    pipeline = run_allocation(parse(source), k)
    if pipeline.success:
        assert pipeline.allocation.verify(pipeline.graph) == []
        assert execute(pipeline.function) == expected


def test_pipeline_reports_success_and_retry_limit_differently():
    simple = 'func main\n t1 = 3\n ret t1\nend'
    assert run_allocation(parse(simple), 2).stop_reason == 'success'
    # A 3-clique with only 2 registers will remain under pressure in the first round.
    hard = ('func main\n t1 = 1\n t2 = 2\n t3 = 3\n'
            ' t4 = t1 + t2\n t5 = t4 + t3\n ret t5\nend')
    result = run_allocation(parse(hard), 1, max_iterations=1)
    assert not result.success
    assert result.stop_reason == 'iteration_limit'
