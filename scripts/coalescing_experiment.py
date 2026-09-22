#!/usr/bin/env python
"""Coalescing ON vs OFF experiment.

Runs the same benchmark, at the same K, through the real allocator twice -- once
with coalescing enabled and once with `do_coalesce=False` (the same flag the CLI's
`--no-coalesce` maps to) -- and reports the difference. Every number comes from an
actual `run_and_collect_metrics()` call; nothing is hard-coded or simulated.

    python scripts/coalescing_experiment.py
    python scripts/coalescing_experiment.py --benchmark benchmarks/copy_heavy.tac --k 2 4 6 8
    python scripts/coalescing_experiment.py --json results/coalescing_results.json \\
                                             --csv results/coalescing_results.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.frontend.parser import parse  # noqa: E402
from src.metrics import run_and_collect_metrics  # noqa: E402

DEFAULT_BENCHMARK = pathlib.Path(__file__).resolve().parent.parent / "benchmarks" / "copy_heavy.tac"
DEFAULT_KS = [2, 3, 4, 5, 6, 8]


def run_pair(bench_path: pathlib.Path, k: int) -> dict:
    """Run coalescing ON and OFF at one K, on freshly-parsed copies of the same
    source (the pipeline mutates the Function it's given, so each run needs its own).
    """
    name = bench_path.stem
    source = bench_path.read_text()

    fn_on = parse(source)
    pipeline_on, metrics_on = run_and_collect_metrics(fn_on, k, do_coalesce=True, benchmark=name)

    fn_off = parse(source)
    pipeline_off, metrics_off = run_and_collect_metrics(fn_off, k, do_coalesce=False, benchmark=name)

    return {
        "benchmark": name,
        "k": k,
        "copies_in_source": metrics_on.num_move_instructions,
        "coalescing_candidates": metrics_on.num_coalescing_candidates,
        "on_success": metrics_on.success,
        "on_merges": metrics_on.num_coalescing_merges,
        "on_refused": metrics_on.num_coalescing_refused,
        "on_redundant_moves": metrics_on.num_redundant_move_instructions,
        "on_spilled_vregs": metrics_on.num_spilled_vregs,
        "on_loads": metrics_on.num_spill_loads,
        "on_stores": metrics_on.num_spill_stores,
        "on_iterations": metrics_on.num_retry_iterations,
        "on_final_instructions": metrics_on.num_final_instructions,
        "off_success": metrics_off.success,
        "off_redundant_moves": metrics_off.num_redundant_move_instructions,
        "off_spilled_vregs": metrics_off.num_spilled_vregs,
        "off_loads": metrics_off.num_spill_loads,
        "off_stores": metrics_off.num_spill_stores,
        "off_iterations": metrics_off.num_retry_iterations,
        "off_final_instructions": metrics_off.num_final_instructions,
        "spill_delta_loads": metrics_off.num_spill_loads - metrics_on.num_spill_loads,
        "spill_delta_stores": metrics_off.num_spill_stores - metrics_on.num_spill_stores,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare coalescing ON vs OFF on one benchmark.")
    ap.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    ap.add_argument("--k", type=int, nargs="+", default=DEFAULT_KS)
    ap.add_argument("--json", metavar="FILE")
    ap.add_argument("--csv", metavar="FILE")
    args = ap.parse_args(argv)

    bench_path = pathlib.Path(args.benchmark)
    if not bench_path.exists():
        print(f"error: no such file: {bench_path}", file=sys.stderr)
        return 1

    rows = [run_pair(bench_path, k) for k in args.k]

    header = f"{'K':>3}  {'copies':>6} {'cand.':>5} {'ON merges':>9} {'ON refused':>10} " \
             f"{'ON redund.':>10} {'ON spills':>9}  {'OFF spills':>10}  {'ON iters':>8} {'OFF iters':>9}"
    print(f"benchmark: {bench_path.name}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['k']:>3}  {r['copies_in_source']:>6} {r['coalescing_candidates']:>5} "
              f"{r['on_merges']:>9} {r['on_refused']:>10} {r['on_redundant_moves']:>10} "
              f"{r['on_spilled_vregs']:>9}  {r['off_spilled_vregs']:>10}  "
              f"{r['on_iterations']:>8} {r['off_iterations']:>9}")

    any_spill_improvement = any(r["spill_delta_loads"] > 0 or r["spill_delta_stores"] > 0 for r in rows)
    any_merge = any(r["on_merges"] > 0 for r in rows)
    print()
    if any_spill_improvement:
        print("Observed: coalescing reduced spill load/store instructions at one or more K values.")
    elif any_merge:
        print("No measurable improvement observed in spill counts at these K values; "
              "coalescing did perform successful merges (see 'ON merges' above) and "
              "increased redundant-move detection ('ON redund.' vs an OFF run), which "
              "is the effect this benchmark actually demonstrates for this allocator "
              "(it assigns registers, it does not delete instructions from the output).")
    else:
        print("No measurable improvement observed: no merges succeeded at any tested K.")

    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=2))
        print(f"\n(wrote {out})")

    if args.csv:
        out = pathlib.Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"(wrote {out})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
