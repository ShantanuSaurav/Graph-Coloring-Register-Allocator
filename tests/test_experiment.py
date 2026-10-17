"""Regression tests for the empirical complexity endpoint."""
from fastapi.testclient import TestClient
from api.index import app

CLIENT = TestClient(app)
CODE = 'func main\n t1 = 1\n t2 = 2\n t3 = t1 + t2\n ret t3\nend'


def test_experiment_measures_multiple_register_counts():
    resp = CLIENT.post('/api/experiment', json={'code': CODE, 'register_counts': [2, 4], 'repeats': 2})
    assert resp.status_code == 200
    data = resp.json()
    assert [row['k'] for row in data['samples']] == [2, 4]
    assert all(row['runtime_ms'] >= 0 and row['peak_memory_kib'] > 0 for row in data['samples'])
    assert all(row['success'] for row in data['samples'])


def test_experiment_rejects_duplicate_register_count():
    resp = CLIENT.post('/api/experiment', json={'code': CODE, 'register_counts': [2, 2]})
    assert resp.status_code == 422


def test_experiment_rejects_invalid_program():
    resp = CLIENT.post('/api/experiment', json={'code': 'not-a-valid-instruction'})
    assert resp.status_code == 422


def test_experiment_limits_repeat_count():
    resp = CLIENT.post('/api/experiment', json={'code': CODE, 'repeats': 99})
    assert resp.status_code == 422
