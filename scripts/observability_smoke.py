"""Verify metrics, logs, and correlated OTLP traces through the Compose stack.

Run inside the app container after startup:
docker compose exec -T app python - < scripts/observability_smoke.py
"""

import os
import time

import httpx


def eventually(description, check, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            pass
        time.sleep(1)
    raise AssertionError("Observability verification failed: " + description)


def main():
    api = os.getenv("FLEETOPS_URL", "http://127.0.0.1:7860")
    headers = {"Authorization": "Bearer " + os.environ["FLEETOPS_API_TOKEN"]}
    with httpx.Client(timeout=10) as client:
        session = client.post(api + "/api/v1/sessions", headers=headers)
        session.raise_for_status()
        headers["X-FleetOps-Session"] = session.json()["session_id"]
        client.post(api + "/api/v1/probes", headers=headers, json={"count": 20}).raise_for_status()
        evidence = client.get(api + "/api/v1/evidence", headers=headers)
        evidence.raise_for_status()
        trace_id = next(row["trace_id"] for row in evidence.json() if row["kind"] == "log" and "trace_id" in row)

        def metrics_present():
            response = client.get("http://prometheus:9090/api/v1/query", params={"query": 'fleetops_inference_requests_total{service="inference-api",outcome="success"}'})
            response.raise_for_status()
            return any(float(result["value"][1]) > 0 for result in response.json()["data"]["result"])

        def logs_present():
            response = client.get("http://loki:3100/loki/api/v1/query_range", params={
                "query": '{service_name="gpu-fleetops"} |= "' + trace_id + '"',
                "start": str(int((time.time() - 300) * 1e9)), "end": str(int(time.time() * 1e9)),
            })
            response.raise_for_status()
            return any(stream["values"] for stream in response.json()["data"]["result"])

        def traces_present():
            response = client.get("http://tempo:3200/api/traces/" + trace_id, headers={"Accept": "application/json"})
            response.raise_for_status()
            return "workload.inference" in response.text and "gpu-fleetops" in response.text

        eventually("workload counters reached Prometheus", metrics_present)
        eventually("structured logs reached Loki with the trace ID", logs_present)
        eventually("matching workload spans reached Tempo", traces_present)
    print("PASS: Prometheus metrics, Loki logs, and correlated Tempo traces")


if __name__ == "__main__":
    main()
