# Improvements and verification (October 2026)

This repository incorporates the original project and the Phase 1 fixes.

## New in this package
- Reference TAC interpreter (`src/analysis/interpreter.py`) with bounded execution, branch and loop support, and explicit failures for undefined variables and invalid arithmetic.
- API semantic-equivalence check of original versus final spill-rewritten TAC when both can be executed within 10,000 instructions. **This checks value preservation, not real machine register execution.**
- Select an allocation iteration in the web UI to inspect its CFG, liveness, register assignments and interference structure.
- JSON result and CSV metric exports, with browser-only download functionality.
- Text fallback for graph visualization if Graphviz/D3 dependencies cannot load.
- Multi-version GitHub Actions (Python 3.11–3.13) and coverage output.
- Interpreter regression tests.
- Fixed fresh temporary IDs colliding with existing registers when spill rewriting a function before CFG construction.

## Remaining limitations
- Certain low-K or copy-heavy inputs can still exhaust the 10-round spill/retry cap. The UI reports this as non-convergence instead of falsely claiming success.
- Graph-color verification does not emulate physical register moves, instruction selection, or real machine code.
- Reference interpreter uses integer arithmetic and truncation-toward-zero division; it is not a production runtime.
- Runtime equivalence checks are skipped when source programs do not terminate within the instruction budget or contain invalid operations.
- The graph view needs its CDN-hosted libraries for SVG rendering. The textual fallback remains usable offline.

## Run
```bash
python -m pip install -r requirements.txt
python -m pytest
python scripts/dev_server.py
```
Open the URL printed by the development server. For Vercel deployment, see `vercel.json`.
