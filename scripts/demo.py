#!/usr/bin/env python
"""Faculty demonstration: runs one benchmark through the real pipeline, stage by
stage, and prints a compact summary. Everything printed is read off the actual
`Function`, `InterferenceGraph`, `AllocationResult` and `PipelineResult` produced by
that run -- there is no separate "demo data".

    python scripts/demo.py
    python scripts/demo.py --benchmark benchmarks/high_pressure.tac --k 2
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# Windows terminals often default to a legacy codepage (cp1252) that can't encode
# the checkmark characters this demo prints; force UTF-8 so the demo runs cleanly
# in a faculty presentation regardless of the host terminal's default encoding.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

from src.frontend.cfg import build_cfg, compute_loop_depth  # noqa: E402
from src.frontend.parser import ParseError, parse_file  # noqa: E402
from src.ir import is_vreg  # noqa: E402
from src.metrics import run_and_collect_metrics  # noqa: E402

DEFAULT_BENCHMARK = pathlib.Path(__file__).resolve().parent.parent / "benchmarks" / "high_pressure.tac"


def _vkey(name: str):
    return int(name[1:]) if is_vreg(name) else name


def _step(label: str, ok: bool) -> None:
    mark = "✓" if ok else "✗"
    print(f"[{label:<12}] {mark}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Faculty demonstration of the allocator pipeline.")
    ap.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--no-coalesce", action="store_true")
    args = ap.parse_args(argv)

    print("=" * 60)
    print("GRAPH-COLORING REGISTER ALLOCATOR")
    print("FACULTY DEMONSTRATION")
    print("=" * 60)
    print(f"\nBenchmark: {pathlib.Path(args.benchmark).name}")
    print(f"K: {args.k}")
    print(f"Coalescing: {'off' if args.no_coalesce else 'on'}\n")

    try:
        fn = parse_file(args.benchmark)
    except (ParseError, FileNotFoundError) as e:
        print(f"[PARSING     ] ✗  {e}")
        return 1
    _step("PARSING", True)

    try:
        build_cfg(fn)
        compute_loop_depth(fn)
    except ValueError as e:
        _step("CFG", False)
        print(f"  {e}")
        return 1
    _step("CFG", True)
    print(f"  {len(fn.blocks)} block(s): "
          + ", ".join(f"{b.name}(depth={b.loop_depth})" for b in fn.block_order()))

    pipeline, metrics = run_and_collect_metrics(
        fn, args.k, do_coalesce=not args.no_coalesce, benchmark=pathlib.Path(args.benchmark).stem
    )
    _step("LIVENESS", True)
    _step("INTERFERENCE", True)
    print(f"  {metrics.num_interference_nodes} node(s), {metrics.num_interference_edges} edge(s), "
          f"max degree {metrics.max_interference_degree}")

    _step("COALESCING", True)
    print(f"  candidates={metrics.num_coalescing_candidates}  "
          f"merged={metrics.num_coalescing_merges}  refused={metrics.num_coalescing_refused}")

    _step("COLORING", pipeline.success)
    _step("SPILLING", True)
    print(f"  spilled_vregs={metrics.num_spilled_vregs}  loads={metrics.num_spill_loads}  "
          f"stores={metrics.num_spill_stores}  iterations={metrics.num_retry_iterations}")

    problems = pipeline.allocation.verify(pipeline.graph)
    _step("VERIFICATION", not problems)

    print("\n" + "-" * 41)
    print("METRICS")
    print("-" * 41 + "\n")
    print(f"Virtual registers   : {metrics.num_virtual_registers}")
    print(f"Graph nodes         : {metrics.num_interference_nodes}")
    print(f"Graph edges         : {metrics.num_interference_edges}")
    print(f"Coalesced pairs     : {metrics.num_coalescing_merges}")
    print(f"Spills              : {metrics.num_spilled_vregs}")
    print(f"Loads               : {metrics.num_spill_loads}")
    print(f"Stores              : {metrics.num_spill_stores}")
    print(f"Iterations          : {metrics.num_retry_iterations}")

    print("\n" + "-" * 41)
    print("FINAL ALLOCATION")
    print("-" * 41 + "\n")
    for v in sorted(pipeline.allocation.colours, key=_vkey):
        print(f"{v} -> R{pipeline.allocation.colours[v]}")
    if pipeline.allocation.spilled:
        print(f"\nstill spilled: {sorted(pipeline.allocation.spilled, key=_vkey)}")

    print("\nAllocation Verification")
    if not problems:
        print("  ✓ All virtual registers handled")
        print("  ✓ No interfering nodes share a register")
        if metrics.num_spilled_vregs:
            print("  ✓ Spill rewrite completed")
        else:
            print("  ✓ No spilling required at this K")
        print("  ✓ No unresolved spill" if pipeline.success else "  ✗ Unresolved spill remains")
        print("  ✓ Pipeline converged" if pipeline.success else "  ✗ Pipeline did not converge")
    else:
        print("  ✗ Verification FAILED:")
        for p in problems:
            print(f"    - {p}")

    print(f"\nRESULT: {'SUCCESS' if pipeline.success and not problems else 'FAILURE'}")
    return 0 if pipeline.success and not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
