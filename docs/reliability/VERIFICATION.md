# Recorded verification

Recorded October 14, 2026 (America/Denver), Python 3.12.14 on macOS ARM64.

- **208 tests passed**, zero failures/errors.
- **98.33% line coverage**, above the repository's 85% requirement.
- Ruff checks passed for source, tests and scripts.
- Ten additional replay seeds produced **40/40** expected domain outcomes within the same synthetic generator family.
- The replay CLI generated the full evidence bundle, technical review and executive brief.
- Matplotlib exported SVG and PNG figures; the PNG was visually inspected.
- Authenticated API tests cover persistence, session isolation, bounded requests and readiness decisions.
- The Gradio application mounted and its callback contracts passed; the local HTTP application returned 200.
- The published experiment explorer rendered all five Plotly charts and the architecture at 1280×900 and 390×844. Chart zoom/reset changed the displayed axis ticks, and the readiness disclosure opened. Both viewport widths had no page-level horizontal overflow.
- The **local Gradio** application rendered after correcting a static-asset route collision. Real frontend JS/CSS requests return 200. A browser run changed the seed to 2027 and fleet size to 100, then calculated 68 interruption episodes, 244.9 h observed MTBI and 70.3 lost GPU-hours. The actual app capture is linked from the illustrated guide.
- A regression test loads the frontend bundles and application-owned architecture SVG.
- Package 1.1.0 built and installed successfully.
- [GitHub CI](https://github.com/sivalinb/gpu-fleetops/actions/runs/38673271230) passed Python 3.12, Python 3.13 and the full Docker observability-stack smoke job for implementation commit `5cc52df`.
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
