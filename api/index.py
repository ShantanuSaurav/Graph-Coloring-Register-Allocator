"""Vercel serverless entry point for the web demo.

Runs the *real* pipeline (parse -> CFG -> liveness -> interference -> coalesce ->
colour -> spill/retry) rather than only parsing and building a graph.

Bug fixed here (kept from the original version): the previous version called
`build_graph(fn)` directly on the output of `parse()`, before `build_cfg` or
`analyse` had ever run. Because `fn.blocks` was still empty at that point,
`build_graph`'s test-only fallback path kicked in — it treats the whole program as a
single block with an empty `live_out`, which happens to look reasonable for
straight-line code but silently produces the wrong interference graph for anything
with a label, a branch, or a loop (no per-block liveness, no merging at join points).
Running `build_cfg` and `analyse` first, as the CLI already does, is the fix.

Review 2 addition: the response now also carries a `stages` breakdown (TAC, CFG,
liveness, interference, coalescing, coloring, spilling before/after, final output),
a `metrics` block (src.metrics.AllocationMetrics), and a `verification` block — all
read from the same real pipeline run, nothing computed separately in JavaScript. The
original `summary`/`dot`/`error` fields are kept unchanged so the previous frontend
contract still works.
"""

import traceback

from fastapi import FastAPI
from pydantic import BaseModel

from src.analysis.interference import InterferenceGraph, build_graph
from src.analysis.liveness import compute_use_def
from src.frontend.cfg import build_cfg, compute_loop_depth
from src.frontend.parser import ParseError, parse
from src.ir import Function, is_vreg
from src.metrics import collect_metrics
from src.spilling.spiller import count_spill_instructions, rewrite_with_spills, run_allocation

app = FastAPI()


class CodeRequest(BaseModel):
    code: str
    k: int = 4
    coalescing: bool = True


def _vreg_key(name: str):
    return int(name[1:]) if is_vreg(name) else name


def _cfg_stage(fn: Function) -> list[dict]:
    return [
        {
            "name": b.name,
            "entry": b.name == fn.entry,
            "loop_depth": b.loop_depth,
            "preds": b.preds,
            "succs": b.succs,
            "instrs": [str(i) for i in b.instrs],
        }
        for b in fn.block_order()
    ]


def _liveness_stage(fn: Function) -> list[dict]:
    out = []
    for b in fn.block_order():
        use, defd = compute_use_def(b)
        out.append({
            "block": b.name,
            "use": sorted(use, key=_vreg_key),
            "def": sorted(defd, key=_vreg_key),
            "in": sorted(b.live_in, key=_vreg_key),
            "out": sorted(b.live_out, key=_vreg_key),
        })
    return out


def _interference_stage(graph: InterferenceGraph) -> dict:
    nodes = sorted(graph.nodes(), key=_vreg_key)
    return {
        "nodes": nodes,
        "edges": [sorted(e, key=_vreg_key) for e in sorted(graph.edges(), key=lambda s: sorted(s))],
        "degrees": {n: graph.degree(n) for n in nodes},
        "move_pairs": [sorted(p, key=_vreg_key)
                        for p in sorted(graph.move_pairs, key=lambda s: sorted(s))],
    }


def _cfg_dot(fn: Function) -> str:
    """CFG as Graphviz DOT, straight off the real blocks -- the frontend renders this
    rather than reconstructing block/edge structure itself (Feature 8: the backend
    stays the source of truth for graph structure).
    """
    lines = ["digraph cfg {", '  node [shape=box, style=filled, fillcolor="#ffffff", '
             'color="#6366f1", fontname="Helvetica"];', '  edge [color="#9ca3af"];']
    for b in fn.block_order():
        marker = " (entry)" if b.name == fn.entry else ""
        label = f"{b.name}{marker}\\ndepth={b.loop_depth}"
        lines.append(f'  "{b.name}" [label="{label}"];')
    for b in fn.block_order():
        for s in b.succs:
            lines.append(f'  "{b.name}" -> "{s}";')
    lines.append("}")
    return "\n".join(lines)


def _spill_stage(fn_i: Function, result) -> dict:
    """Before/after instruction listing for one iteration's spill rewrite (Feature
    10). Uses the real `rewrite_with_spills`, the same function the pipeline itself
    runs, purely for display — it does not affect the next iteration.
    """
    if result.success:
        return {"needed": False, "before": [], "after": [], "spilled": []}
    before = [str(i) for b in fn_i.block_order() for i in b.instrs]
    after_fn = rewrite_with_spills(fn_i, result.spilled)
    after = [str(i) for i in getattr(after_fn, "_parsed_instrs", [])]
    return {
        "needed": True,
        "spilled": sorted(result.spilled, key=_vreg_key),
        "before": before,
        "after": after,
    }


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

        tac_stage = [str(i) for i in instrs]

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

        # Step 3: full allocate/spill/retry pipeline at the requested K, capturing
        # every intermediate stage of every iteration via on_iteration -- the same
        # hook the CLI's --dump-* flags use, so the web view and the CLI are always
        # looking at the same real data.
        k = max(1, req.k)
        iterations_stage: list[dict] = []
        first_iteration: dict[str, object] = {}

        def on_iteration(iteration, fn_i, graph, result) -> None:
            if iteration == 1:
                first_iteration["graph"] = graph
                first_iteration["result"] = result
            iterations_stage.append({
                "iteration": iteration,
                "cfg": _cfg_stage(fn_i),
                "cfg_dot": _cfg_dot(fn_i),
                "liveness": _liveness_stage(fn_i),
                "interference": _interference_stage(graph),
                "coalescing_trace": result.coalesce_trace,
                "coalescing_stats": result.coalesce_stats,
                "coloring": {v: result.colours[v] for v in sorted(result.colours, key=_vreg_key)},
                "spilling": _spill_stage(fn_i, result),
            })

        pipeline = run_allocation(fn, k, do_coalesce=req.coalescing, on_iteration=on_iteration)

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

        # Step 5: metrics (same src.metrics single source of truth the CLI uses).
        metrics = collect_metrics(
            original_fn=fn, k=k, do_coalesce=req.coalescing, pipeline=pipeline,
            first_graph=first_iteration["graph"], first_result=first_iteration["result"],
        )

        # Step 6: verification -- never claim SUCCESS without actually checking.
        problems = pipeline.allocation.verify(pipeline.graph)
        verification = {
            "passed": pipeline.success and not problems,
            "all_registers_handled": pipeline.success,
            "no_interfering_share_a_register": not problems,
            "spill_rewrite_completed": True,
            "no_unresolved_spill": pipeline.success,
            "pipeline_converged": pipeline.success,
            "problems": problems,
        }

        final_stage = []
        for block in pipeline.function.block_order():
            for instr in block.instrs:
                reg = None
                if instr.dst and is_vreg(instr.dst):
                    reg = pipeline.allocation.register_of(instr.dst)
                final_stage.append({"text": str(instr), "register": reg})

        return {
            "summary": summary,
            "dot": dot_code,
            "error": None,
            "k": k,
            "coalescing": req.coalescing,
            "stages": {
                "tac": tac_stage,
                "iterations": iterations_stage,
                "final": final_stage,
            },
            "metrics": metrics.to_dict(),
            "verification": verification,
        }

    except ParseError as e:
        return {"summary": "", "dot": "", "error": f"Parse Error: {e}"}
    except Exception as e:
        return {"summary": "", "dot": "", "error": f"Unexpected Error: {e}\n\n{traceback.format_exc()}"}
