#!/usr/bin/env python
"""Plot K-vs-spill and coalescing ON/OFF results.

Reads the CSV files `run_benchmarks.py` / `coalescing_experiment.py` already wrote --
it does not run the allocator itself and does not embed any numbers -- and renders
them with matplotlib.

    python scripts/run_benchmarks.py --csv results/benchmark_results.csv
    python scripts/coalescing_experiment.py --csv results/coalescing_results.csv
    python scripts/plot_results.py \\
        --benchmark-csv results/benchmark_results.csv \\
        --coalescing-csv results/coalescing_results.csv \\
        --out-dir results
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from collections import defaultdict

RESULTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "results"


def _read_csv(path: pathlib.Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def plot_k_vs_spills(rows: list[dict], out_path: pathlib.Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_bench: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for r in rows:
        if r.get("status") not in ("PASS", "FAIL"):
            continue
        spills = r.get("num_spilled_vregs", "")
        if spills in ("", None):
            continue
        by_bench[r["benchmark"]].append((int(r["k"]), int(spills)))

    fig, ax = plt.subplots(figsize=(8, 5))
    for bench, points in sorted(by_bench.items()):
        points.sort()
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        ax.plot(xs, ys, marker="o", label=bench)

    ax.set_xlabel("K (physical registers)")
    ax.set_ylabel("Spilled virtual registers")
    ax.set_title("K vs. spill count, per benchmark (real pipeline runs)")
    ax.legend(fontsize="small")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"(wrote {out_path})")


def plot_coalescing_on_off(rows: list[dict], out_path: pathlib.Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ks = [int(r["k"]) for r in rows]
    on_spills = [int(r["on_spilled_vregs"]) for r in rows]
    off_spills = [int(r["off_spilled_vregs"]) for r in rows]
    on_merges = [int(r["on_merges"]) for r in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    width = 0.35
    x = range(len(ks))
    ax1.bar([i - width / 2 for i in x], off_spills, width, label="coalescing OFF")
    ax1.bar([i + width / 2 for i in x], on_spills, width, label="coalescing ON")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels([str(k) for k in ks])
    ax1.set_xlabel("K")
    ax1.set_ylabel("Spilled virtual registers")
    ax1.set_title("Spills: coalescing ON vs OFF")
    ax1.legend(fontsize="small")
    ax1.grid(True, axis="y", alpha=0.3)

    ax2.plot(ks, on_merges, marker="o", color="tab:green")
    ax2.set_xlabel("K")
    ax2.set_ylabel("Successful coalescing merges")
    ax2.set_title("Merges accepted by Briggs' test, per K")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"(wrote {out_path})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Plot benchmark/coalescing CSV results with matplotlib.")
    ap.add_argument("--benchmark-csv", default=str(RESULTS_DIR / "benchmark_results.csv"))
    ap.add_argument("--coalescing-csv", default=str(RESULTS_DIR / "coalescing_results.csv"))
    ap.add_argument("--out-dir", default=str(RESULTS_DIR))
    args = ap.parse_args(argv)

    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("matplotlib is not installed; run `pip install matplotlib` "
              "(see requirements.txt) and try again.", file=sys.stderr)
        return 1

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    did_something = False

    bench_csv = pathlib.Path(args.benchmark_csv)
    if bench_csv.exists():
        plot_k_vs_spills(_read_csv(bench_csv), out_dir / "k_vs_spills.png")
        did_something = True
    else:
        print(f"(skipping k-vs-spills plot: {bench_csv} not found -- "
              f"run scripts/run_benchmarks.py --csv {bench_csv} first)")

    coal_csv = pathlib.Path(args.coalescing_csv)
    if coal_csv.exists():
        plot_coalescing_on_off(_read_csv(coal_csv), out_dir / "coalescing_on_off.png")
        did_something = True
    else:
        print(f"(skipping coalescing plot: {coal_csv} not found -- "
              f"run scripts/coalescing_experiment.py --csv {coal_csv} first)")

    return 0 if did_something else 1


if __name__ == "__main__":
    raise SystemExit(main())
