"""Tests for scripts/run_benchmarks.py: the benchmark runner used for the
K-scaling / reproducibility experiments (Review 2, Feature 4/5).
"""

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"


def _load(module_name: str, filename: str):
    """scripts/ isn't a package (it's a folder of standalone CLI entry points), so
    import its modules by file path rather than assuming `scripts` is importable.
    """
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


run_benchmarks = _load("run_benchmarks", "run_benchmarks.py")


def test_all_benchmarks_execute_at_k_equals_4():
    bench_files = sorted((ROOT / "benchmarks").glob("*.tac"))
    assert bench_files, "expected at least one .tac benchmark"
    for bench in bench_files:
        row = run_benchmarks.run_one(bench, k=4, do_coalesce=True)
        assert row["status"] == "PASS", f"{bench} failed to allocate at k=4: {row}"


def test_invalid_k_is_handled_without_crashing():
    bench = ROOT / "benchmarks" / "simple.tac"
    row = run_benchmarks.run_one(bench, k=0, do_coalesce=True)
    assert row["status"] == "INVALID_K"
    assert row["error"]


def test_k_equals_one_fails_cleanly_rather_than_crashing():
    """Documented, expected behaviour (README/architecture.md): K=1 cannot colour a
    binary op. The runner must report FAIL, not raise.
    """
    bench = ROOT / "benchmarks" / "simple.tac"
    row = run_benchmarks.run_one(bench, k=1, do_coalesce=True)
    assert row["status"] == "FAIL"
    assert row["success"] is False


def test_result_schema_has_the_documented_fields():
    bench = ROOT / "benchmarks" / "simple.tac"
    row = run_benchmarks.run_one(bench, k=4, do_coalesce=True)
    expected_fields = {
        "benchmark", "k", "status", "num_spilled_vregs", "num_spill_loads",
        "num_spill_stores", "num_retry_iterations", "num_coalescing_merges",
        "num_interference_nodes", "num_interference_edges", "success",
    }
    assert expected_fields <= row.keys()


def test_main_writes_json_and_csv(tmp_path):
    json_out = tmp_path / "bench.json"
    csv_out = tmp_path / "bench.csv"
    run_benchmarks.main([
        "--k", "4",
        "--benchmarks-dir", str(ROOT / "benchmarks"),
        "--json", str(json_out),
        "--csv", str(csv_out),
    ])
    assert json_out.exists()
    assert csv_out.exists()

    import json
    rows = json.loads(json_out.read_text())
    assert len(rows) == len(list((ROOT / "benchmarks").glob("*.tac")))
    assert all(r["status"] == "PASS" for r in rows)
