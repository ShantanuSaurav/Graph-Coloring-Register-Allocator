"""Structured allocation metrics — the single source of truth for numbers reported
by the CLI, the web API, the benchmark runner, and the coalescing experiment.

Nothing here invents a number: every field is read straight off the real data
structures the pipeline already produces (`Function`, `InterferenceGraph`,
`AllocationResult`, `PipelineResult`). Graph-structure metrics (nodes, edges, degree,
move/coalescing counts) describe the *first* allocate() attempt — the original
program's interference problem, before any spill rewriting changed the code. Outcome
metrics (spills, loads, stores, iterations, final instruction count) describe the
*last* attempt, i.e. what the pipeline actually returned. Both are real, both are
useful, and conflating them would misreport either the problem size or the result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.analysis.interference import InterferenceGraph
from src.colouring.allocator import AllocationResult
from src.ir import Function, Instr, Op
from src.spilling.spiller import MAX_ITERATIONS, PipelineResult, run_allocation


@dataclass
class AllocationMetrics:
    """Everything measured about one `run_allocation()` call."""

    benchmark: str | None
    k: int
    coalescing_enabled: bool

    num_input_instructions: int
    num_virtual_registers: int

    num_cfg_blocks: int
    num_cfg_edges: int

    num_interference_nodes: int
    num_interference_edges: int
    max_interference_degree: int

    num_move_instructions: int
    num_coalescing_candidates: int
    num_coalescing_merges: int
    num_coalescing_refused: int
    # COPY instructions whose src and dst resolved (through the coalescing chain) to
    # the same physical register: real moves left in the instruction stream that are
    # now provably dead. This allocator assigns registers, it does not rewrite the
    # instruction stream, so these are not deleted — but counting them is an honest,
    # non-fabricated way to show coalescing's effect when the raw instruction count
    # does not move (see docs/architecture.md's coalescing-experiment note).
    num_redundant_move_instructions: int

    num_spilled_vregs: int
    num_spill_loads: int
    num_spill_stores: int
    num_retry_iterations: int

    num_final_physical_registers: int
    num_final_instructions: int

    success: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _flat_instrs(fn: Function) -> list[Instr]:
    if fn.blocks:
        return [instr for block in fn.block_order() for instr in block.instrs]
    return list(getattr(fn, "_parsed_instrs", None) or [])


def collect_metrics(
    original_fn: Function,
    k: int,
    do_coalesce: bool,
    pipeline: PipelineResult,
    first_graph: InterferenceGraph,
    first_result: AllocationResult,
    benchmark: str | None = None,
) -> AllocationMetrics:
    """Assemble an `AllocationMetrics` from one completed pipeline run.

    `original_fn` must be the *same* Function object passed into `run_allocation` —
    its first iteration calls `build_cfg`/`compute_loop_depth` on it in place, so by
    the time the pipeline returns, `original_fn.blocks` already holds the CFG for the
    original (pre-spill) program. `first_graph`/`first_result` are the interference
    graph and AllocationResult from that same first iteration (see
    `run_and_collect_metrics`, which captures them via `run_allocation`'s
    `on_iteration` hook).
    """
    input_instrs = _flat_instrs(original_fn)
    vregs = {v for i in input_instrs for v in (i.defs() | i.uses())}

    num_cfg_blocks = len(original_fn.blocks)
    num_cfg_edges = sum(len(b.succs) for b in original_fn.blocks.values())

    degrees = [first_graph.degree(n) for n in first_graph.nodes()]
    max_degree = max(degrees) if degrees else 0

    num_moves = sum(1 for i in input_instrs if i.op is Op.COPY)
    cstats = first_result.coalesce_stats

    final_instrs = _flat_instrs(pipeline.function)
    loads = sum(1 for i in final_instrs if i.op is Op.LOAD)
    stores = sum(1 for i in final_instrs if i.op is Op.STORE)

    redundant_moves = 0
    if pipeline.success:
        for i in final_instrs:
            if i.op is Op.COPY and i.dst and i.src1:
                if pipeline.allocation.register_of(i.dst) == pipeline.allocation.register_of(i.src1):
                    redundant_moves += 1

    spilled_vregs = {v for s in pipeline.spilled_history for v in s}

    return AllocationMetrics(
        benchmark=benchmark,
        k=k,
        coalescing_enabled=do_coalesce,
        num_input_instructions=len(input_instrs),
        num_virtual_registers=len(vregs),
        num_cfg_blocks=num_cfg_blocks,
        num_cfg_edges=num_cfg_edges,
        num_interference_nodes=len(first_graph.nodes()),
        num_interference_edges=first_graph.edge_count(),
        max_interference_degree=max_degree,
        num_move_instructions=num_moves,
        num_coalescing_candidates=cstats.get("candidates", 0),
        num_coalescing_merges=cstats.get("merged", 0),
        num_coalescing_refused=cstats.get("refused", 0),
        num_redundant_move_instructions=redundant_moves,
        num_spilled_vregs=len(spilled_vregs),
        num_spill_loads=loads,
        num_spill_stores=stores,
        num_retry_iterations=pipeline.iterations,
        num_final_physical_registers=len(set(pipeline.allocation.colours.values())),
        num_final_instructions=len(final_instrs),
        success=pipeline.success,
    )


def run_and_collect_metrics(
    fn: Function,
    k: int,
    do_coalesce: bool = True,
    benchmark: str | None = None,
    max_iterations: int = MAX_ITERATIONS,
) -> tuple[PipelineResult, AllocationMetrics]:
    """Run the full allocate/spill/retry pipeline once and return `(pipeline, metrics)`.

    This is the one place that both runs the allocator and collects metrics, so the
    CLI, web API, benchmark runner and coalescing experiment all see numbers computed
    the same way. It captures the first iteration's graph/result via `on_iteration`
    (see `collect_metrics`'s docstring for why the first iteration, not the last).
    """
    first: dict[str, object] = {}

    def on_iteration(iteration, fn_i, graph, result) -> None:
        if iteration == 1:
            first["graph"] = graph
            first["result"] = result

    pipeline = run_allocation(
        fn, k, do_coalesce=do_coalesce, max_iterations=max_iterations, on_iteration=on_iteration
    )
    metrics = collect_metrics(
        original_fn=fn,
        k=k,
        do_coalesce=do_coalesce,
        pipeline=pipeline,
        first_graph=first["graph"],
        first_result=first["result"],
        benchmark=benchmark,
    )
    return pipeline, metrics
