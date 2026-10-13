---
title: GPU FleetOps
emoji: 🛰️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: GPU reliability lab with telemetry, SLOs, and AI investigation
---

# GPU FleetOps

**Connect a failure signal to an affected service, an owner, a supported diagnosis, and verified recovery.**

GPU FleetOps combines a GPU infrastructure catalog, telemetry, request-based SLOs, incident workflows, and an evidence-grounded investigator. The Gradio reliability lab runs on a CPU laptop.

![GPU FleetOps architecture](src/fleetops/assets/architecture.svg)

## Run the demo

Requires **Python 3.12+**. From this checkout:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
fleetops
```

Open **http://127.0.0.1:7860**. No GPU or model API key is required for the default demo.

1. Select **GPU memory exhaustion** and click **Inject fault**.
2. Click **Run probes**. Inspect the failures, SLOs, and owned incident.
3. Click **Investigate incident**, then open **Investigation & recovery**. Inspect the tool trace and evidence citations.
4. Review the proposal, check the approval box, and click **Apply approved fix and verify**.
5. Run 80 healthy probes and read the incident report. Recovery does **not** erase historical error-budget consumption.

Each visitor gets an independent lab. The **insufficient evidence** scenario intentionally produces an abstention and no fix.

For a temporary public demo, run `fleetops --share`. Its link works while your process/computer stays running and expires after one week. Permanent hosting instructions are in the deployment guide.

## Implemented behavior

| Area | What executes |
|---|---|
| Workload | A deterministic NumPy CPU classification workload. GPU conditions and reported service latency are simulated; actual CPU time is recorded separately. |
| Catalog | Three illustrative environments, asset relationships, services, dependencies, owners, source precedence, provenance, stale records, and driver drift. |
| Telemetry | Evidence and trace IDs, JSON logs, Prometheus metrics, OpenTelemetry spans, and a bounded persistent outbox with atomic replay. |
| SLOs | Rolling 30-day availability and successful-latency SLIs, budgets, no-data handling, and paired fast/slow burn detection. |
| Incidents | Deduplication, ownership routing, acknowledgment, timed escalation records, maintenance suppression, proposals, revision checks, verification, and reports. |
| Investigation | Explicitly labeled deterministic rules, or a provider-backed tool loop with read-only tools, validated citations, action checks, quotas, and abstention. |
| Recovery | Allowlisted, operator-approved simulation actions. Twenty probes verify the result before the incident resolves. |
| Real inputs | Authenticated Kubernetes NodeList reconciliation and DCGM ingestion. External hardware errors require investigation; the app never resets real GPUs. |

This portfolio reference implementation does **not** establish experience operating physical GPU fleets. Real integration contracts are tested with representative fixtures. Physical GPU validation, live model evaluation, and an independent operator drill are further evidence to add when those resources are available.

## Full observability deployment

Requires Docker Compose. Generate local secrets and start PostgreSQL and the observability profile:

```bash
python scripts/setup_env.py
docker compose --profile observability up --build --wait --wait-timeout 240
```

| Tool | Local URL |
|---|---|
| Gradio | http://127.0.0.1:7860 |
| Grafana | http://127.0.0.1:3000 — GPU Reliability → GPU FleetOps |
| Prometheus | http://127.0.0.1:9090 |
| Operator API | http://127.0.0.1:7860/api/docs |

Loki and Tempo stay on the Compose network. Grafana links JSON trace IDs to Tempo. Published ports bind to loopback. Generated `.env` credentials are ignored by Git. The setup script preserves any existing credentials.

Stop with `docker compose --profile observability down`. Named volumes retain data. The app intentionally runs one worker; distributed concurrency requirements are documented in the architecture.

## Enable agentic AI

The default **baseline** uses deterministic rules and makes no model call. Live mode runs incident-scoped tools through a configured provider:

```bash
export FLEETOPS_AI_MODE=live
export FLEETOPS_AI_BASE_URL=https://integrate.api.nvidia.com/v1
export FLEETOPS_AI_MODEL='your-provider-tool-calling-model-id'
export FLEETOPS_AI_API_KEY='your-key'
fleetops
```

For Compose, set these in the ignored `.env` and recreate the app. Select a model supporting **Chat Completions function tools**. The provider model is intentionally not guessed. Credentials stay on the server. The investigator can read incidents, evidence, inventory, SLOs, and runbooks; it cannot execute recovery. Limits: six model steps, three live investigations/session, sixty/server/hour.

See [agent behavior and evaluation](docs/AGENT.md). The committed evaluation measures known synthetic baseline scenarios, not held-out LLM accuracy.

## Tests and reproducible evidence

```bash
pip install -r requirements-dev.txt
ruff check src tests scripts
pytest --cov=fleetops --cov-report=term-missing
python scripts/evaluate.py
python scripts/benchmark.py --assets 1000
```

Tests cover all seven failures, SLO boundaries, maintenance, concurrent duplicates, catalog conflicts, persistence, verification, stale plans, authentication, isolation, provider failures, fabricated citations, tool abuse, quotas, Gradio callbacks, and deployment configuration. CI includes a full container smoke test.

- [Verification status](docs/VERIFICATION.md): exactly what ran and what remains environment-dependent.
- [Scenario evaluation](reports/evaluation.json): actions, citations, recoveries, deduplication, and timing.
- [Local synthetic benchmark](reports/benchmark.json): 1,000 logical GPU records and 500 probes, with machine and scope.
- [Container image validation](reports/container-images.json): manifests used to pin deployment images.

## Documentation

- [Simple guide](docs/GUIDE.md)
- [Architecture and tradeoffs](docs/ARCHITECTURE.md)
- [Use cases and test map](docs/USE_CASES.md)
- [SLI/SLO policy](docs/SLO.md)
- [Break/fix runbooks](docs/RUNBOOKS.md)
- [Deployment and real integrations](docs/DEPLOYMENT.md)
- [Portfolio and interview guide](docs/PORTFOLIO.md)

Python · Gradio · FastAPI · SQLAlchemy · SQLite/PostgreSQL · NumPy · OpenTelemetry · Prometheus · Grafana · Loki · Tempo · Docker · Kubernetes

MIT licensed. NVIDIA is not affiliated with this project.
