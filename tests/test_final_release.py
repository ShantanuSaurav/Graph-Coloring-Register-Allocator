"""Regression coverage for the final compiler workbench and safe fallback."""

import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.index import app
from src.analysis.interpreter import execute
from src.frontend.parser import parse
from src.spilling.spiller import run_allocation

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_copy_heavy_converges_with_conservative_fallback_k2():
    source = (ROOT / 'benchmarks/copy_heavy.tac').read_text()
    result = run_allocation(parse(source), 2)
    assert result.success
    assert result.stop_reason == 'conservative_spill_fallback'
    assert result.iterations == 11
    assert result.allocation.verify(result.graph) == []
    assert execute(parse(source)) == execute(result.function)


def test_copy_heavy_fallback_disabled_for_one_register():
    source = (ROOT / 'benchmarks/copy_heavy.tac').read_text()
    result = run_allocation(parse(source), 1, max_iterations=2)
    assert not result.success
    assert result.stop_reason == 'iteration_limit'


def test_api_resolves_coalesced_graph_vertices():
    source = (ROOT / 'benchmarks/simple.tac').read_text()
    data = client.post('/api/analyze', json={'code': source, 'k': 4}).json()
    stage = data['stages']['iterations'][0]
    assert all(node in stage['coloring'] for node in stage['interference']['nodes'])
    assert stage['simplify_stack']
    assert isinstance(stage['optimistic_nodes'], list)
    assert isinstance(stage['coalesced_map'], dict)
    assert data['verification']['passed']


def test_api_copy_heavy_accurate_fallback_verification():
    source = (ROOT / 'benchmarks/copy_heavy.tac').read_text()
    data = client.post('/api/analyze', json={'code': source, 'k': 2}).json()
    assert data['error'] is None
    assert data['stages']['stop_reason'] == 'conservative_spill_fallback'
    assert data['verification']['passed']
    assert data['verification']['semantic']['checked']
    assert len(data['stages']['iterations']) == 11


def test_scale_study_returns_ordered_empirical_measurements():
    result = client.post('/api/scale-study', json={'sizes': [8, 16, 32], 'k': 4, 'repeats': 1})
    assert result.status_code == 200
    data = result.json()
    assert [x['size'] for x in data['samples']] == [8, 16, 32]
    assert all(x['runtime_ms'] >= 0 and x['peak_memory_kib'] > 0 and x['success'] for x in data['samples'])


@pytest.mark.parametrize('sizes', [[8, 8], [3, 16], [8, 181], [10]])
def test_scale_study_rejects_invalid_samples(sizes):
    assert client.post('/api/scale-study', json={'sizes': sizes}).status_code == 422


def test_large_integer_division_does_not_use_float():
    value = 10**500
    source = f'func huge\n t1 = {value}\n t2 = t1 / 3\n ret t2\nend'
    assert execute(parse(source)) == value // 3


@pytest.mark.parametrize('seed', range(12))
def test_random_long_lived_values_preserve_semantics_at_k2(seed):
    rng = random.Random(seed)
    values = [rng.randrange(1, 100) for _ in range(6)]
    lines = ['func wide']
    for i, value in enumerate(values, start=1):
        lines.append(f't{i} = {value}')
    lines.extend([
        't7 = t1 + t2', 't8 = t3 + t4', 't9 = t5 + t6',
        't10 = t7 + t8', 't11 = t10 + t9', 'ret t11', 'end'
    ])
    source = '\n'.join(lines)
    result = run_allocation(parse(source), 2)
    assert result.success
    assert result.allocation.verify(result.graph) == []
    assert execute(parse(source)) == execute(result.function)


def test_web_assets_and_examples_are_bundled_locally():
    script = (ROOT / 'public/script.js').read_text()
    assert 'https://' not in script
    assert 'createElementNS' in script
    for path in (ROOT / 'benchmarks').glob('*.tac'):
        assert (ROOT / 'public/examples' / path.name).read_text() == path.read_text()


def test_mobile_accessibility_and_navigation_have_reachable_controls():
    page = (ROOT / 'public/index.html').read_text()
    for identifier in ('menu-toggle', 'guide-view', 'help-open', 'stage-content', 'iteration-select',
                       'scale-run', 'scale-time-chart', 'scale-memory-chart', 'bank-groups'):
        assert f'id="{identifier}"' in page
    assert 'role="tablist"' in page
    assert 'aria-live="polite"' in page
