"""Command-line entry point.

    python -m src.cli benchmarks/simple.tac --dump-cfg
    python -m src.cli benchmarks/simple.tac --k 8 --dump-graph graph.dot

Runs the complete pipeline end to end: parse -> build the CFG -> liveness -> build the
interference graph -> coalesce/colour -> spill and retry if necessary -> print the final
allocated program. `--dump-cfg`, `--dump-live` and `--dump-graph` show the intermediate
stages; without them you just get the parsed program and the final result.
"""

from __future__ import annotations

import argparse
import sys

from src.colouring.allocator import AllocationResult
from src.frontend.parser import ParseError, parse_file
from src.ir import Function, Instr, is_vreg
from src.spilling.spiller import MAX_ITERATIONS, count_spill_instructions, run_allocation


def _vreg_sort_key(name: str):
    """Sort t1, t2, ..., t10 in numeric order instead of lexicographic."""
    return int(name[1:]) if is_vreg(name) else name


def _dump_cfg(fn: Function) -> None:
    print("basic blocks:")
    for block in fn.block_order():
        marker = " (entry)" if block.name == fn.entry else ""
        print(f"  {block.name}{marker}  loop_depth={block.loop_depth}  "
              f"preds={block.preds}  succs={block.succs}")
        for instr in block.instrs:
            print(f"      {instr}")


def _dump_live(fn: Function) -> None:
    print("liveness:")
    for block in fn.block_order():
        live_in = sorted(block.live_in, key=_vreg_sort_key)
        live_out = sorted(block.live_out, key=_vreg_sort_key)
        print(f"  {block.name}: live_in={live_in}  live_out={live_out}")


def _register_comment(instr: Instr, result: AllocationResult) -> str:
    """`# R2` for an instruction whose destination has been coloured, else ''."""
    if instr.dst is None or not is_vreg(instr.dst):
        return ""
    reg = result.register_of(instr.dst)
    return f"    # R{reg}" if reg is not None else ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="regalloc-a5",
        description="Chaitin-Briggs graph-colouring register allocator",
    )
    ap.add_argument("source", help="input .tac file")
    ap.add_argument("--k", type=int, default=8,
                    help="number of physical registers (default: 8)")
    ap.add_argument("--dump-cfg", action="store_true",
                    help="print the parsed instructions and control-flow graph")
    ap.add_argument("--dump-live", action="store_true",
                    help="print live_in/live_out for every basic block")
    ap.add_argument("--dump-graph", metavar="FILE",
                    help="write the interference graph as Graphviz DOT")
    ap.add_argument("--no-coalesce", action="store_true",
                    help="disable coalescing (for the O3 baseline comparison)")
    args = ap.parse_args(argv)

    if args.k < 1:
        print("error: --k must be at least 1", file=sys.stderr)
        return 2

    # ---- stage 1: parse ----
    try:
        fn = parse_file(args.source)
    except ParseError as e:
        print(f"parse error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"error: no such file: {args.source}", file=sys.stderr)
        return 1

    instrs = getattr(fn, "_parsed_instrs", [])
    print(f"parsed function {fn.name!r}: {len(instrs)} instructions")

    print("\ninput program:")
    for i, ins in enumerate(instrs):
        print(f"  {i:3d}  {ins}")
    vregs = sorted({v for ins in instrs for v in (ins.defs() | ins.uses())}, key=_vreg_sort_key)
    print(f"\nvirtual registers ({len(vregs)}): {', '.join(vregs)}")

    print(f"\ntarget: K = {args.k} physical register(s), "
          f"coalescing {'off' if args.no_coalesce else 'on'}")

    # ---- stages 2-6: CFG, liveness, interference, colouring, spilling ----
    def on_iteration(iteration, fn_i, graph, result) -> None:
        print(f"\n--- iteration {iteration} ---")
        if args.dump_cfg:
            _dump_cfg(fn_i)
        if args.dump_live:
            _dump_live(fn_i)

        print(f"interference graph: {graph}")
        if result.success:
            print("colouring: success")
            for v in sorted(result.colours, key=_vreg_sort_key):
                print(f"  {v} -> R{result.colours[v]}")
            if result.coalesced:
                print("coalesced (merged -> survivor):")
                for merged in sorted(result.coalesced, key=_vreg_sort_key):
                    survivor = result.coalesced[merged]
                    print(f"  {merged} -> {survivor}  (R{result.colours.get(survivor)})")
        else:
            print(f"colouring: {len(result.spilled)} actual spill(s): "
                  f"{sorted(result.spilled, key=_vreg_sort_key)}")

        if args.dump_graph:
            colours = result.colours if result.success else None
            with open(args.dump_graph, "w", encoding="utf-8") as fh:
                fh.write(graph.to_dot(colours))
            print(f"(wrote interference graph to {args.dump_graph})")

    pipeline = run_allocation(fn, args.k, do_coalesce=not args.no_coalesce,
                               on_iteration=on_iteration)

    print(f"\n{'=' * 60}")
    if pipeline.success:
        print(f"ALLOCATION SUCCEEDED after {pipeline.iterations} iteration(s)")
        print(f"spill load/store instructions inserted overall: "
              f"{count_spill_instructions(pipeline.function)}")
        print("\nfinal allocated program:")
        for block in pipeline.function.block_order():
            for instr in block.instrs:
                print(f"  {instr}{_register_comment(instr, pipeline.allocation)}")
        return 0

    print(f"ALLOCATION FAILED: no valid colouring found within "
          f"{pipeline.iterations} iteration(s) (max {MAX_ITERATIONS}) at K={args.k}")
    print(f"  still spilled at the last attempt: "
          f"{sorted(pipeline.allocation.spilled, key=_vreg_sort_key)}")
    print("  try a larger --k, or check whether every instruction genuinely needs "
          "that many simultaneous operands (a binary op always needs 2).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
