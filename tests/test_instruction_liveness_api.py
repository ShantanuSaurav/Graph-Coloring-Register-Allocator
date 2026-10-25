"""Regression checks for instruction-level liveness exposed by the web API."""
from fastapi.testclient import TestClient
from api.index import app

client = TestClient(app)
CODE = """func main
 t1 = 1
 t2 = 2
 t3 = t1 + t2
 t4 = t3
 t5 = t4 * 2
 ret t5
end"""


def stage(k):
    response = client.post('/api/analyze', json={'code': CODE, 'k': k})
    assert response.status_code == 200
    result = response.json()
    assert not result['error']
    return result['stages']['iterations'][0]['liveness'][0]


def test_instruction_liveness_between_definitions():
    block = stage(4)
    assert block['in'] == [] and block['out'] == []
    rows = block['instructions']
    assert len(rows) == 6
    assert 't1' in rows[1]['after']
    assert 't2' in rows[1]['after']
    assert 't1' in rows[2]['before'] and 't2' in rows[2]['before']
    assert rows[-1]['after'] == []


def test_original_liveness_independent_of_k():
    assert stage(2) == stage(7)
