# Register Lab — Graph-Coloring Register Allocator

An interactive **Chaitin–Briggs register-allocation compiler workbench** for custom three-address code (TAC). Parse, build a control-flow graph, calculate liveness, construct the interference graph, coalesce safe moves, color virtual registers, and rewrite spills.

## Features

| Workspace | Description |
|---|---|
| Allocation explorer | Interactive CFG and interference graphs rendered in native SVG, liveness sets, virtual-to-physical register mappings, spill transformations, iteration selection and verification |
| Complexity lab | Repeatable measurements of allocator wall-time and peak traced Python memory for different physical register budgets, plotted and downloadable as CSV |
| Register banks | Group physical registers into visual boxes and inspect which virtual registers map into each group |

**Note:** The register bank view groups register assignments for visualization; it does not implement segmented memory or register-bank hardware constraints. Complexity measurements are empirical allocator overhead, not compiled TAC execution time and not an asymptotic Big-O guarantee.

## Run locally

Prerequisites: Python 3.11+ (3.11–3.13 tested in CI).

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest
python scripts/dev_server.py
```

Open **http://127.0.0.1:8000**.

The web application calls the real Python allocation pipeline; it is not a mock or graph-only demonstration.

## Web API

- `POST /api/analyze` with `{"code": "func main\n t1 = 1\n ret t1\nend", "k": 4, "coalescing": true}`.
- `POST /api/experiment` with `{"code": "...", "register_counts": [2,3,4,6,8], "repeats": 3, "coalescing": true}`.

For the CLI, try `python -m src.cli --help`.

## Structure

```text
api/             FastAPI endpoints for interactive analysis and experiments
src/frontend/    TAC parser and CFG construction
src/analysis/    Liveness, interference graph and execution interpreter
src/colouring/   Briggs coalescing and simplify/select
src/spilling/    Spill rewrite and allocation retry loop
public/          Responsive dependency-free web dashboard
benchmarks/      TAC workloads
scripts/         Local web server, benchmarks and experiment utilities
tests/           Python regression suite
docs/            Architecture and academic notes
```

## Deploy

The repository includes `vercel.json` for Vercel's Python API and static assets. Import the GitHub repository into Vercel, configure Python support, and confirm the rewrite rules and API routes. No Vercel project is currently provisioned by this archive.

## Testing and project scope

Run `python -m pytest -q`. The presentation reviews define an **intra-procedural teaching compiler** rather than a full architecture-specific machine-code backend. See [docs/REDESIGN.md](docs/REDESIGN.md) and [docs/architecture.md](docs/architecture.md) for design and known limitations.

## Academic sources

The accompanying Review 1 and Review 2 materials document the objectives, implementation stages, benchmark methodology, and future work. Key background: Chaitin (1982), Briggs et al. (1994), and Aho et al., *Compilers: Principles, Techniques, and Tools*.
