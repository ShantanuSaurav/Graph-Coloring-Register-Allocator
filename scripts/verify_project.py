#!/usr/bin/env python3
"""Simple release self-check, independent of an external browser or Vercel.

Run from the repository root:
    python scripts/verify_project.py

This exercises the actual FastAPI app in process (no network or server required).
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from api.index import app  # noqa: E402


def main() -> int:
    client = TestClient(app)
    checks: list[tuple[str, bool]] = []
    for name, k in [('simple', 4), ('diamond', 3), ('high_pressure', 2), ('copy_heavy', 2)]:
        code = (ROOT / 'benchmarks' / f'{name}.tac').read_text(encoding='utf8')
        response = client.post('/api/analyze', json={'code': code, 'k': k})
        data = response.json()
        checks.append((f'Analyze {name} with K={k}', response.status_code == 200
                       and data.get('error') is None and data['verification']['passed']
                       and bool(data['stages']['iterations'][0]['interference']['nodes'])))
    source = (ROOT / 'benchmarks' / 'simple.tac').read_text(encoding='utf8')
    budget = client.post('/api/experiment', json={'code': source, 'register_counts': [2, 4], 'repeats': 1})
    checks.append(('Register-budget complexity API', budget.status_code == 200 and len(budget.json()['samples']) == 2))
    scale = client.post('/api/scale-study', json={'sizes': [8, 16], 'k': 4, 'repeats': 1})
    checks.append(('Input-size complexity API', scale.status_code == 200 and len(scale.json()['samples']) == 2))
    for asset in ('index.html', 'style.css', 'script.js', 'examples/simple.tac'):
        checks.append((f'Static asset public/{asset}', (ROOT / 'public' / asset).is_file()))
    for message, passed in checks:
        print(f'{"PASS" if passed else "FAIL"}: {message}')
    print(f'\n{sum(ok for _, ok in checks)} of {len(checks)} release checks passed.')
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
