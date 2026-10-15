# Recorded verification

Recorded October 14, 2026 (America/Denver), Python 3.12.14 on macOS ARM64.

- **207 tests passed**, zero failures/errors.
- **98.33% line coverage**, above the repository's 85% requirement.
- Ruff checks passed for source, tests and scripts.
- Ten additional replay seeds produced **40/40** expected domain outcomes within the same synthetic generator family.
- The replay CLI generated the full evidence bundle, technical review and executive brief.
- Matplotlib exported SVG and PNG figures; the PNG was visually inspected.
- Authenticated API tests cover persistence, session isolation, bounded requests and readiness decisions.
- The Gradio application mounted and its callback contracts passed; the local HTTP application returned 200.
- The computer-use browser preview displayed a blank page, so browser rendering, interactive Plotly behavior and responsive layout are **not verified by this run**. No browser screenshot is presented as successful UI evidence.
- The native GPU runner recorded **unavailable** because `dcgmi` is not installed. Native subprocess behavior is fixture-tested; it does not establish physical GPU operation.
- No independent engineer or CSP reviewed these results.

[Machine-readable verification](../../reports/reliability/verification.json) · [Classification cases](../../reports/reliability/classification-evaluation.json) · [Technical results](../../reports/reliability/TECHNICAL_REVIEW.md)

## Reproduce

```bash
pip install -r requirements-dev.txt
pip install --no-deps -e .
ruff check src tests scripts
pytest --cov=fleetops --cov-report=term-missing
fleetops-reliability replay --seed 2026 --assets 1000
pip install -r requirements-figures.txt
python scripts/reliability_figures.py
```

The original seven-scenario operational suite and Docker observability-stack CI remain configured. Historical v1.0 stack results are documented in the existing verification guide. This extension's publication triggers fresh GitHub checks; their status is independently inspectable on the commit.
