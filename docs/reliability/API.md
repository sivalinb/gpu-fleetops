# API and data contracts

All `/api/v1/reliability/*` routes require the existing operator bearer token and `X-FleetOps-Session` header. Create a session through `POST /api/v1/sessions`. Server credentials stay outside source control.

| Method | Route | Behavior |
|---|---|---|
| POST | `/api/v1/reliability/replay` | `{"seed":2026,"assets":1000}` → calculated synthetic bundle, persisted in this session |
| GET | `/api/v1/reliability/latest` | Last replay in this session; 404 before a replay |
| GET | `/api/v1/reliability/review` | Plain-text technical review from that replay |
| POST | `/api/v1/reliability/analyze?unit=gpu` | Validate and analyze an operator-supplied canonical dataset |
| POST | `/api/v1/reliability/readiness` | Assess a canonical diagnostic-evidence envelope |

Imports never execute hardware commands or infer native cloud access. Interactive OpenAPI documentation is at `/api/docs`. The public Gradio controls operate only on bounded synthetic inputs; they do not accept an operator token or expose live-write controls.

## Canonical dataset

`Dataset` version 1.0 contains an epoch, description, explicit entities and events. Entities supply unit, provider, rack, node, model, driver, firmware/configuration, workload, age band, observation window, and maintenance/unknown exclusions. Events supply source ID, entity ID, incident key, onset/recovery, domain, signal, actual interruption impact and `synthetic|replayed|live` provenance.

Use `examples/reliability/canonical.json` as a small runnable input:

```bash
fleetops-reliability analyze examples/reliability/canonical.json --unit gpu --output reports/custom-analysis.json
fleetops-reliability readiness examples/reliability/readiness-incomplete.json --output reports/custom-readiness.json
```

Three sample raw provider records and the normalized contract are included. Provider formats are fictional adapter exercises, not advertised native CSP integrations. An external collector must independently establish event impact and observation coverage.

## Observability

`/metrics` includes `fleetops_reliability_runs_total{origin="synthetic"}`, `fleetops_reliability_duration_seconds`, and `fleetops_reliability_last_observation{field="interruptions|operating_hours|unknown_hours"}`. The latter is a last-completed synthetic replay gauge, not a physical fleet metric or cumulative counter. GPU identities and arbitrary provider names are not added as labels by this extension.
