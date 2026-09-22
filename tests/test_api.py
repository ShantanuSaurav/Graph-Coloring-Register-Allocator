"""Tests for api/index.py's FastAPI endpoint.

Exercises the API exactly as a client would (through FastAPI's TestClient, i.e. real
HTTP request/response handling), covering straight-line, branch and loop input, the
new stage/metrics/verification fields Review 2 added, and that build_cfg -> analyse ->
build_graph still runs in the correct order (the regression this module's docstring
describes fixing).
"""

import pytest
from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)

STRAIGHT_LINE = """func main
  t1 = 1
  t2 = 2
  t3 = t1 + t2
  t4 = t3
  t5 = t4 * 2
  ret t5
end"""

BRANCH = open("benchmarks/diamond.tac").read()
LOOP = open("benchmarks/loop.tac").read()
SPILL_HEAVY = open("benchmarks/high_pressure.tac").read()


def test_existing_endpoint_still_returns_summary_and_dot():
    resp = client.post("/api/analyze", json={"code": STRAIGHT_LINE, "k": 4})
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] is None
    assert "Parsed function" in data["summary"]
    assert data["dot"].startswith("graph interference {")


def test_straight_line_input():
    resp = client.post("/api/analyze", json={"code": STRAIGHT_LINE, "k": 8})
    data = resp.json()
    assert data["error"] is None
    assert data["verification"]["passed"] is True
    assert data["metrics"]["num_virtual_registers"] == 5


def test_branch_input_builds_a_real_multi_block_cfg():
    """Regression coverage for the bug this module's docstring describes: branch
    input must be analysed per-block (CFG -> liveness -> interference), not folded
    into one giant fallback block.
    """
    resp = client.post("/api/analyze", json={"code": BRANCH, "k": 4})
    data = resp.json()
    assert data["error"] is None
    first_iter = data["stages"]["iterations"][0]
    assert len(first_iter["cfg"]) == 4  # diamond.tac: B0 (if), B1 (then), B2 (else... )
    # t3 must be live-out of both branch arms -- only true with real per-block liveness.
    live = {b["block"]: b for b in first_iter["liveness"]}
    then_and_else = [b for name, b in live.items() if name in ("B1", "B2")]
    assert all("t3" in b["out"] for b in then_and_else)


def test_loop_input():
    resp = client.post("/api/analyze", json={"code": LOOP, "k": 4})
    data = resp.json()
    assert data["error"] is None
    assert data["verification"]["passed"] is True
    cfg = data["stages"]["iterations"][0]["cfg"]
    header = next(b for b in cfg if b["loop_depth"] == 1)
    assert header is not None


def test_spill_heavy_input_reports_before_after():
    resp = client.post("/api/analyze", json={"code": SPILL_HEAVY, "k": 4})
    data = resp.json()
    assert data["error"] is None
    spilling_stages = [it["spilling"] for it in data["stages"]["iterations"]]
    assert any(s["needed"] for s in spilling_stages)
    spilled_stage = next(s for s in spilling_stages if s["needed"])
    assert spilled_stage["before"]
    assert spilled_stage["after"]
    assert len(spilled_stage["after"]) > len(spilled_stage["before"])
    assert spilled_stage["spilled"]


def test_metrics_field_matches_cli_computable_values():
    resp = client.post("/api/analyze", json={"code": STRAIGHT_LINE, "k": 4})
    data = resp.json()
    m = data["metrics"]
    assert m["num_input_instructions"] == 6
    assert m["num_coalescing_merges"] == 1   # t3/t4 copy, safe merge
    assert m["success"] is True


def test_coalescing_flag_is_respected():
    on = client.post("/api/analyze", json={"code": STRAIGHT_LINE, "k": 4, "coalescing": True}).json()
    off = client.post("/api/analyze", json={"code": STRAIGHT_LINE, "k": 4, "coalescing": False}).json()
    assert on["metrics"]["num_coalescing_merges"] == 1
    assert off["metrics"]["num_coalescing_merges"] == 0


def test_verification_never_claims_success_on_failure():
    resp = client.post("/api/analyze", json={"code": STRAIGHT_LINE, "k": 1})
    data = resp.json()
    assert data["verification"]["passed"] is False
    assert data["verification"]["pipeline_converged"] is False


def test_parse_error_reported_cleanly():
    resp = client.post("/api/analyze", json={"code": "not a program", "k": 4})
    data = resp.json()
    assert data["error"] is not None
    assert "Parse Error" in data["error"]


def test_undefined_label_reported_as_cfg_error():
    resp = client.post("/api/analyze", json={"code": "func f\n goto NOWHERE\n ret t1\nend", "k": 4})
    data = resp.json()
    assert data["error"] is not None
    assert "CFG error" in data["error"]
