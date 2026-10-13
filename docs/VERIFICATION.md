# Verification status

Verified locally on October 13, 2026 with Python 3.12.14.

| Check | Result |
|---|---|
| Automated test suite | 176 passed; 99.2% line coverage. |
| Ruff | Passed across application, tests, and scripts. |
| Dependency consistency | `pip check` passed. |
| HTTP smoke | Gradio route, health/readiness, a complete investigation/recovery lifecycle, and metrics passed. |
| Scenario evaluation | 7/7 expected deterministic baseline actions; six verified recoveries; one intentional abstention. |
| Synthetic local benchmark | 1,000 logical GPU catalog records and 500 probes; timing and scope recorded. |
| Container image manifests | All eight deployment/base/helper images verified in the public registry and pinned by digest. |
| Browser | Public Gradio memory-failure drill, citations, approval rejection, approved recovery, and budget history exercised. A recurrence issue found here has a dedicated regression test. |

## Environment-dependent checks

The authoring machine has no Docker runtime or physical NVIDIA GPU. Container-stack startup, PostgreSQL integration, and external Grafana/Loki/Tempo operation are covered by a separate GitHub Actions container-smoke job; check that run's actual result before claiming it passed. Kubernetes deployment is supplied and structurally checked, not applied to a real cluster here.

The real model tool protocol is tested with scripted responses and HTTP mock transports. A live provider call was not made because no project provider key/model was supplied. The public demo runs the clearly labeled rules baseline. A held-out live-model benchmark and independent operator drill are not claimed.

## Reproduce

```bash
pip install -r requirements-dev.txt
pip install --no-deps -e .
ruff check src tests scripts
pytest --cov=fleetops --cov-report=term-missing
python scripts/evaluate.py
python scripts/benchmark.py --assets 1000
```

For the container profile, run the documented setup command and `scripts/smoke.py`. CI uses both Python 3.12 and 3.13. Workflow configuration is not evidence of a successful run; inspect CI results and artifacts.

The large raw local coverage/JUnit files are excluded from the public checkout. [verification.json](../reports/verification.json) contains a curated summary without local filesystem paths or machine hostnames.
