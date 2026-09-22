#!/usr/bin/env python
"""Benchmark runner: executes every `.tac` file in `benchmarks/` at a sweep of K
values through the real pipeline (`src.metrics.run_and_collect_metrics`) and prints
a summary table. Every number in that table comes from an actual allocator run --
nothing here is precomputed or hard-coded.

    python scripts/run_benchmarks.py
    python scripts/run_benchmarks.py --k 1 2 3 4 8 --json results/benchmark_results.json
    python scripts/run_benchmarks.py --no-coalesce --csv results/benchmark_results.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.frontend.parser import ParseError, parse  # noqa: E402
from src.metrics import run_and_collect_metrics  # noqa: E402

DEFAULT_KS = [1, 2, 3, 4, 8]
BENCHMARKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "benchmarks"


def run_one(bench_path: pathlib.Path, k: int, do_coalesce: bool) -> dict:
    """Run one benchmark at one K. Never raises: a bad K or a pipeline that fails to
    converge is a valid, reportable outcome, not a script crash.
    """
    name = bench_path.stem
    if k < 1:
        return {
            "benchmark": name, "k": k, "status": "INVALID_K", "coalescing": do_coalesce,
            "spills": None, "loads": None, "stores": None, "iterations": None,
            "error": "K must be >= 1",
        }
    try:
        fn = parse(bench_path.read_text())
    except ParseError as e:
        return {
            "benchmark": name, "k": k, "status": "PARSE_ERROR", "coalescing": do_coalesce,
            "spills": None, "loads": None, "stores": None, "iterations": None,
            "error": str(e),
        }

    pipeline, metrics = run_and_collect_metrics(fn, k, do_coalesce=do_coalesce, benchmark=name)
    problems = pipeline.allocation.verify(pipeline.graph)
    status = "PASS" if pipeline.success and not problems else "FAIL"

    row = metrics.to_dict()
    row["status"] = status
    row["verification_problems"] = problems
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run every benchmark across a sweep of K values.")
    ap.add_argument("--k", type=int, nargs="+", default=DEFAULT_KS,
                     help=f"K values to sweep (default: {DEFAULT_KS})")
    ap.add_argument("--no-coalesce", action="store_true", help="disable coalescing")
    ap.add_argument("--benchmarks-dir", default=str(BENCHMARKS_DIR))
    ap.add_argument("--json", metavar="FILE", help="write results as JSON")
    ap.add_argument("--csv", metavar="FILE", help="write results as CSV")
    args = ap.parse_args(argv)

    bench_files = sorted(pathlib.Path(args.benchmarks_dir).glob("*.tac"))
    if not bench_files:
        print(f"no .tac files found in {args.benchmarks_dir}", file=sys.stderr)
        return 1

    rows: list[dict] = []
    for bench in bench_files:
        for k in args.k:
            rows.append(run_one(bench, k, do_coalesce=not args.no_coalesce))

    _print_table(rows)

    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=2))
        print(f"\n(wrote {out})")

    if args.csv:
        out = pathlib.Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        fieldnames: list[str] = []
        for r in rows:
            for key in r:
                if key not in fieldnames:
                    fieldnames.append(key)
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, restval="")
            writer.writeheader()
            writer.writerows(rows)
        print(f"(wrote {out})")

    return 0 if all(r["status"] == "PASS" for r in rows) else 1


def _print_table(rows: list[dict]) -> None:
    header = f"{'Benchmark':<16} {'K':>3}  {'Status':<8} {'Spills':>7} {'Loads':>6} " \
             f"{'Stores':>7} {'Iterations':>10} {'Merges':>7}"
    print(header)
    print("-" * len(header))
    for r in rows:
        spills = r.get("num_spilled_vregs", "-")
        loads = r.get("num_spill_loads", "-")
        stores = r.get("num_spill_stores", "-")
        iters = r.get("num_retry_iterations", "-")
        merges = r.get("num_coalescing_merges", "-")
        print(f"{r['benchmark']:<16} {r['k']:>3}  {r['status']:<8} {spills!s:>7} "
              f"{loads!s:>6} {stores!s:>7} {iters!s:>10} {merges!s:>7}")


if __name__ == "__main__":
    raise SystemExit(main())
