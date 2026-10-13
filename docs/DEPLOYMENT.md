# Deployment and real integrations

## Local Python

Use Python 3.12+, the locked runtime dependencies, and `pip install --no-deps -e .`. Run `fleetops --host 127.0.0.1 --port 7860`. The default database is `data/fleetops.db` relative to the current directory.

The API is disabled until `FLEETOPS_API_TOKEN` is set. It is independent of the public Gradio simulation. Put tokens in your environment, not source control. `scripts/setup_env.py` generates a local ignored `.env` for Compose; plain Python does not automatically load `.env`.

## Docker Compose

```bash
python scripts/setup_env.py
docker compose --profile observability config --quiet
docker compose --profile observability up --build --wait --wait-timeout 240
```

The app uses PostgreSQL. Grafana, Prometheus, Loki, Tempo, and the OTel Collector run in separate containers. Images are pinned to verified registry digests. A one-shot helper owns the Collector storage directory for its unprivileged user. The application runs as user 1000 with a read-only root filesystem and writable data/cache mounts.

Grafana provides an anonymous **local viewer** for the portfolio dashboard. There is no external host binding. Deployment beyond a local demo needs authenticated ingress, TLS, network policy, workload-specific retention, and a deliberate access model.

For HTTP smoke testing, load the generated local environment and run `python scripts/smoke.py`. It verifies the Gradio route, health/readiness, a full incident lifecycle, and metrics.

Run `docker compose exec -T app python - < scripts/observability_smoke.py` to verify actual signal arrival: Prometheus counters, Loki logs containing the probe trace ID, and matching spans in Tempo. CI includes this check.

The complete observability profile is the documented Compose configuration. Running only the application through plain Docker or Python works without external backends when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset.

## Operator API

Create a session with `POST /api/v1/sessions` and `Authorization: Bearer <server-token>`. Send the returned UUID in `X-FleetOps-Session` for subsequent calls. The OpenAPI document at `/api/docs` describes typed payloads.

Key endpoints: `/inventory`, `/integrations/kubernetes`, `/integrations/dcgm`, `/faults`, `/probes`, `/alerts`, `/maintenance`, `/slo`, `/incidents`, `/incidents/{id}/investigate`, `/recovery`, `/evidence`, and `/incidents/{id}/postmortem`, all under `/api/v1`.

An authenticated operator can supply known integration data. Public Gradio input cannot supply an arbitrary external URL, UUID for another session, or command.

## Kubernetes discovery

1. Discover/create the parent cluster asset with the operator API.
2. Configure a Kubernetes service-account token with read-only `get/list` access to nodes.
3. Set `KUBERNETES_API_URL`, `KUBERNETES_TOKEN`, and optional `KUBERNETES_CA_FILE`.
4. Set `FLEETOPS_URL`, `FLEETOPS_API_TOKEN`, `FLEETOPS_SESSION`, and `FLEETOPS_CLUSTER_ID`.
5. Run `python scripts/ingest_kubernetes.py`.

The script requires HTTPS, verifies certificates, and respects a supplied CA. It reads only `/api/v1/nodes`. Node UID is the stable identity. An optional `fleetops.io/owner` label supplies ownership.

## NVIDIA GPU telemetry

Use a supported NVIDIA GPU/driver/DCGM combination and [NVIDIA's DCGM Exporter installation instructions](https://docs.nvidia.com/datacenter/dcgm/latest/installation/install-dcgm-exporter.html). This project does not install drivers or modify a GPU host.

1. Discover each GPU UUID and its parent node/owner with `/api/v1/inventory`, setting `simulated: false`.
2. Configure `DCGM_EXPORTER_URL` to the exporter base URL.
3. Configure the FleetOps operator/session environment described above.
4. Run `python scripts/ingest_dcgm.py`.

Supported fields include utilization, framebuffer usage/total, temperature, power, Xid errors, and double-bit ECC observations. Unsupported fields are ignored; nonfinite values and unknown UUIDs are rejected. Real observations remain labeled `source: dcgm`, `simulated: false` and appear in the Prometheus GPU gauge. The workload drill remains simulated even after real input is ingested.

## Kubernetes application deployment

Build/publish the container with the manual **Publish container** workflow or push your own image. Update `kubernetes/fleetops.yml` to an image you have actually published, preferably a commit tag/digest. The manifest's default GHCR image is a destination, not proof an image already exists.

Apply the manifest and port-forward service `fleetops` in namespace `fleetops` to port 7860. It includes one replica, persistent SQLite storage, readiness/liveness probes, resource limits, a non-root user, and an optional existing operator-token Secret. It does not claim a multi-worker production deployment.

## Public Gradio hosting

`fleetops --share` publishes a temporary link for the isolated UI. The operator REST API is not part of this standalone share server. The link depends on the local process/computer and expires after one week. See [Gradio sharing](https://gradio.app/guides/sharing-your-app).

The README metadata and Dockerfile are ready for a **Hugging Face Docker Space**. Create a Space in your account, choose the Docker SDK, and upload/connect this repository. The app listens on port 7860. Baseline mode requires no GPU or model credential.

Keep provider keys in Space secrets if enabling live mode. Default anonymous public hosting should expose the simulation only. Persistent storage is optional; without it, restarting a Space resets local data. Sessions also expire normally. A hosted URL is a separate deployment and must be verified after upload; the repository does not imply it is already hosted.
