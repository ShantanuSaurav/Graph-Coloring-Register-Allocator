#!/usr/bin/env python
"""Local development server for the web demo.

`vercel.json` rewrites `/api/(.*)` to `api/index.py` when deployed on Vercel; this
script gives the same combined behaviour locally (serve `public/` and mount the same
FastAPI app at `/api`) without needing the Vercel CLI.

    python scripts/dev_server.py
    python scripts/dev_server.py --port 8080
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from api.index import app  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Registered after /api/analyze (already defined on `app`), so those explicit routes
# still win; /benchmarks/*.tac backs the web UI's "load a benchmark" buttons, and
# everything else falls through to the static files in public/.
app.mount("/benchmarks", StaticFiles(directory=str(ROOT / "benchmarks")), name="benchmarks")
app.mount("/", StaticFiles(directory=str(ROOT / "public"), html=True), name="static")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the register allocator's web demo locally.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    print(f"serving public/ and /api on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
