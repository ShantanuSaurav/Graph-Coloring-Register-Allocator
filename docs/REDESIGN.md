# Register Lab — Workbench Redesign

## Design

The backend stays the real Chaitin–Briggs compiler implementation. The website was replaced with a cohesive three-view compiler workbench. No third-party graph renderer is required.

- **Allocation explorer**: editable TAC, benchmark loading, per-iteration CFG/interference SVG, liveness sets, assignments, spills and final output.
- **Complexity lab**: repeatable experiment that compares median allocator wall-time (ms) and traced Python peak memory (KiB) over configurable physical register counts. Export CSV. This is *not* runtime of the compiled program and is *not* a mathematical complexity proof.
- **Register banks**: organize R0…R(K−1) in display groups of 2, 4, or 8, showing assigned virtual registers. This does not change the actual allocator or model hardware segmentation.

## Graph implementation

The client renders native SVG using the `stages.iterations[].interference` and `.cfg` values returned by the Python API. It never relies on Graphviz WASM, D3, or an external CDN. Layout is deterministic and designed for small teaching examples; very large graphs may become crowded.

## Deployment

Run locally with `python scripts/dev_server.py`. `vercel.json` directs Vercel to FastAPI and to the static assets. Vercel may require project-specific framework settings; verify `/api/analyze`, `/api/experiment`, and `/benchmarks/simple.tac` after deployment. The user has deleted the previous deployment, so no live deployment is claimed.

## Attribution and history

The `.claude/` directory from the previous project was not carried forward. GitHub Contributors is calculated from *commit authors in git history*, not package contents. Uploading to the new empty repository and committing as the intended author starts a fresh history; it does not retroactively erase valid previous authors or change authorship rights.

## Scope and limitations

The Review 1 and Review 2 presentations define the core educational scope: intra-procedural TAC allocation, CFG, liveness, interference, Briggs conservative coalescing and spill rewriting. K=1 and some high-pressure cases can still fail to converge within the safety limit. Timing is host/load dependent and Python's memory tracing changes runtime measurements. Semantics of generated code are checked with the provided interpreter for supported terminating programs.
