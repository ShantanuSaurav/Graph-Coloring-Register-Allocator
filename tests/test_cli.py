"""Tests for src/cli.py's Review 2 additions (--dump-coalesce, --dump-spill,
--metrics, --metrics-json). The pre-existing flags (--k, --dump-cfg, --dump-live,
--dump-graph, --no-coalesce) and default behaviour are exercised indirectly here
too, to guard against a regression in the CLI contract Review 2 must preserve.
"""

import json

import pytest

from src.cli import main


def _run(capsys, argv):
    code = main(argv)
    out = capsys.readouterr().out
    return code, out


def test_default_invocation_is_unchanged():
    code, out = 0, ""
    code = main(["benchmarks/simple.tac", "--k", "8"])
    assert code == 0


def test_dump_cfg_and_dump_live_still_work(capsys):
    code, out = _run(capsys, ["benchmarks/diamond.tac", "--k", "4", "--dump-cfg", "--dump-live"])
    assert code == 0
    assert "basic blocks:" in out
    assert "liveness:" in out


def test_no_coalesce_flag_still_works(capsys):
    code, out = _run(capsys, ["benchmarks/simple.tac", "--k", "4", "--no-coalesce"])
    assert code == 0
    assert "coalescing on" not in out
    assert "coalescing off" in out


def test_invalid_k_still_rejected(capsys):
    code, out = _run(capsys, ["benchmarks/simple.tac", "--k", "0"])
    assert code == 2


def test_dump_coalesce_prints_candidate_pairs_and_verdicts(capsys):
    code, out = _run(capsys, ["benchmarks/copy_heavy.tac", "--k", "8", "--dump-coalesce"])
    assert code == 0
    assert "coalescing:" in out
    assert "ACCEPTED" in out
    assert "total: 7 candidate(s)" in out


def test_dump_coalesce_with_no_coalesce_reports_disabled(capsys):
    code, out = _run(capsys, ["benchmarks/copy_heavy.tac", "--k", "8",
                               "--no-coalesce", "--dump-coalesce"])
    assert code == 0
    assert "coalescing: disabled (--no-coalesce)" in out


def test_dump_spill_shows_before_and_after(capsys):
    code, out = _run(capsys, ["benchmarks/high_pressure.tac", "--k", "4", "--dump-spill"])
    assert code == 0
    assert "BEFORE SPILL:" in out
    assert "AFTER SPILL REWRITE:" in out
    assert "spill[" in out


def test_dump_spill_reports_none_needed_when_it_succeeds_immediately(capsys):
    code, out = _run(capsys, ["benchmarks/simple.tac", "--k", "8", "--dump-spill"])
    assert code == 0
    assert "spilling: none needed" in out


def test_metrics_flag_prints_every_documented_field(capsys):
    code, out = _run(capsys, ["benchmarks/simple.tac", "--k", "4", "--metrics"])
    assert code == 0
    assert "METRICS" in out
    for field_name in ("num_interference_nodes", "num_spilled_vregs", "num_coalescing_merges",
                        "success"):
        assert field_name in out


def test_metrics_json_writes_a_valid_file(tmp_path, capsys):
    out_file = tmp_path / "metrics.json"
    code, out = _run(capsys, ["benchmarks/simple.tac", "--k", "4",
                               "--metrics-json", str(out_file)])
    assert code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["num_virtual_registers"] == 5
    assert data["success"] is True


def test_parse_error_still_exits_one(capsys):
    import pathlib
    bad = pathlib.Path("bad_input_for_cli_test.tac")
    bad.write_text("not a real program")
    try:
        code, out = 1, ""
        code = main([str(bad), "--k", "4"])
        assert code == 1
    finally:
        bad.unlink()


def test_missing_file_still_exits_one():
    code = main(["no_such_file.tac", "--k", "4"])
    assert code == 1
