"""Vercel serverless entry point for the web demo.

Runs the *real* pipeline (parse -> CFG -> liveness -> interference -> coalesce ->
colour -> spill/retry) rather than only parsing and building a graph.

Bug fixed here: the previous version called `build_graph(fn)` directly on the output
of `parse()`, before `build_cfg` or `analyse` had ever run. Because `fn.blocks` was
still empty at that point, `build_graph`'s test-only fallback path kicked in — it
treats the whole program as a single block with an empty `live_out`, which happens to
look reasonable for straight-line code but silently produces the wrong interference
graph for anything with a label, a branch, or a loop (no per-block liveness, no
merging at join points). Every benchmark except `simple.tac` and `briggs_example.tac`
would have been misanalysed by the deployed API. Running `build_cfg` and `analyse`
first, as the CLI already does, is the fix.
"""

import traceback

from fastapi import FastAPI
from pydantic import BaseModel

from src.analysis.interference import build_graph
from src.frontend.cfg import build_cfg, compute_loop_depth
from src.frontend.parser import ParseError, parse
from src.ir import is_vreg
from src.spilling.spiller import count_spill_instructions, run_allocation

app = FastAPI()


class CodeRequest(BaseModel):
    code: str
    k: int = 4


def _vreg_key(name: str):
    return int(name[1:]) if is_vreg(name) else name


@app.post("/api/analyze")
def analyze(req: CodeRequest):
    try:
        # Step 1: parse
        fn = parse(req.code)
        instrs = getattr(fn, "_parsed_instrs", [])

        summary = f"Parsed function {fn.name!r}: {len(instrs)} instructions\n\n"
        summary += "Instructions:\n"
        for i, ins in enumerate(instrs):
            summary += f"  {i:3d}  {ins}\n"

        vregs = sorted({v for ins in instrs for v in (ins.defs() | ins.uses())}, key=_vreg_key)
        summary += f"\nVirtual registers ({len(vregs)}): {', '.join(vregs)}\n"

        # Step 2: CFG + loop depth, so liveness (and therefore the interference
        # graph) is computed per-block instead of falling back to "one giant block".
        try:
            build_cfg(fn)
            compute_loop_depth(fn)
        except ValueError as e:
            return {"summary": summary, "dot": "", "error": f"CFG error: {e}"}

        summary += f"\nBasic blocks ({len(fn.blocks)}):\n"
        for block in fn.block_order():
            summary += (f"  {block.name}  loop_depth={block.loop_depth}  "
                        f"preds={block.preds}  succs={block.succs}\n")

        # Step 3: full allocate/spill/retry pipeline at the requested K.
        k = max(1, req.k)
        pipeline = run_allocation(fn, k)

        summary += f"\nRegister allocation (K={k}):\n"
        if pipeline.success:
            summary += f"  SUCCESS after {pipeline.iterations} iteration(s)\n"
            summary += (f"  spill load/store instructions inserted: "
                        f"{count_spill_instructions(pipeline.function)}\n")
            for v in sorted(pipeline.allocation.colours, key=_vreg_key):
                summary += f"    {v} -> R{pipeline.allocation.colours[v]}\n"
        else:
            summary += (f"  FAILED to colour within {pipeline.iterations} iteration(s) — "
                        f"still spilled: {sorted(pipeline.allocation.spilled, key=_vreg_key)}\n")
            summary += "  try a larger K.\n"

        # Step 4: DOT graph, tinted with the achieved colouring when we have one.
        try:
            colours = pipeline.allocation.colours if pipeline.success else None
            dot_code = pipeline.graph.to_dot(colours)
        except Exception as e:
            dot_code = f"Error building graph: {e}\n\n{traceback.format_exc()}"

        return {"summary": summary, "dot": dot_code, "error": None}

    except ParseError as e:
        return {"summary": "", "dot": "", "error": f"Parse Error: {e}"}
    except Exception as e:
        return {"summary": "", "dot": "", "error": f"Unexpected Error: {e}\n\n{traceback.format_exc()}"}
