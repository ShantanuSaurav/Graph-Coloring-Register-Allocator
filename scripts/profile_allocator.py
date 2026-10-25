"""Reproducible local timing and memory experiment.

Run: python scripts/profile_allocator.py --repeat 7 --output allocator_profile.csv
Results are measurements of this Python implementation, not a proof of
asymptotic complexity or an estimate of native CPU execution time.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import time
import tracemalloc
from pathlib import Path

# Support launching this script from its path, without installing the project.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.frontend.parser import parse
from src.spilling.spiller import run_allocation


def profile(path: Path, k: int, repeat: int) -> dict:
    code = path.read_text(encoding='utf-8')
    durations = []
    peaks = []
    status = None
    rounds = None
    for _ in range(repeat):
        fn = parse(code)
        tracemalloc.start()
        started = time.perf_counter_ns()
        try:
            result = run_allocation(fn, k)
        finally:
            elapsed = time.perf_counter_ns() - started
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        durations.append(elapsed / 1_000_000)
        peaks.append(peak / 1024)
        status = result.success
        rounds = result.iterations
    return dict(benchmark=path.name, k=k, repeats=repeat, success=status,
                iterations=rounds, median_runtime_ms=round(statistics.median(durations), 4),
                median_peak_kib=round(statistics.median(peaks), 2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeat', type=int, default=5)
    parser.add_argument('--output', default='allocator_profile.csv')
    parser.add_argument('--k', nargs='+', type=int, default=[2, 3, 4, 8])
    args = parser.parse_args()
    if args.repeat < 1 or any(k < 1 for k in args.k):
        parser.error('repeat and k must be positive')
    root = Path(__file__).resolve().parents[1]
    rows = [profile(path, k, args.repeat)
            for path in sorted((root / 'benchmarks').glob('*.tac'))
            for k in args.k]
    with open(args.output, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f'Wrote {len(rows)} measured experiments to {args.output}')


if __name__ == '__main__':
    main()
