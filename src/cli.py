"""Command-line entry point.

    python -m src.cli benchmarks/simple.tac --dump-cfg
    python -m src.cli benchmarks/simple.tac --k 8 --dump-graph graph.dot

Today only parsing works; the later stages report which module still needs implementing.
That is deliberate — it means the tool runs end to end from day one and tells you
exactly where the pipeline stops.
"""

from __future__ import annotations

import argparse
import sys

from src.frontend.parser import ParseError, parse_file


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
    ap.add_argument("--dump-graph", metavar="FILE",
                    help="write the interference graph as Graphviz DOT")
    ap.add_argument("--no-coalesce", action="store_true",
                    help="disable coalescing (for the O3 baseline comparison)")
    args = ap.parse_args(argv)

    if args.k < 1:
        print("error: --k must be at least 1", file=sys.stderr)
        return 2

    # ---- stage 1: parse (M1, working) ----
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

    if args.dump_cfg:
        print("\ninstructions:")
        for i, ins in enumerate(instrs):
            print(f"  {i:3d}  {ins}")
        vregs = sorted({v for ins in instrs for v in (ins.defs() | ins.uses())},
                       key=lambda s: int(s[1:]))
        print(f"\nvirtual registers ({len(vregs)}): {', '.join(vregs)}")

    # ---- stage 2 onwards ----
    print(f"\ntarget: K = {args.k} physical registers")
    print("pipeline stops here — the next stage is not implemented yet:")
    print("  [ ] M1  build_cfg / compute_loop_depth   src/frontend/cfg.py")
    print("  [ ] M2  liveness / build_graph           src/analysis/")
    print("  [ ] M3  coalesce / simplify / select     src/colouring/allocator.py")
    print("  [ ] M4  spill cost / rewrite             src/spilling/spiller.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
