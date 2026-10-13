"""Black-box HTTP check for a running local/container deployment."""

import os

import httpx


def main():
    url = os.getenv("FLEETOPS_URL", "http://127.0.0.1:7860")
    headers = {"Authorization": "Bearer " + os.environ["FLEETOPS_API_TOKEN"]}
    with httpx.Client(base_url=url, timeout=60) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/assets/architecture.svg").status_code == 200
        session = client.post("/api/v1/sessions", headers=headers)
        session.raise_for_status()
        headers["X-FleetOps-Session"] = session.json()["session_id"]
        fault = client.post("/api/v1/faults", headers=headers, json={"fault": "gpu_oom"})
        fault.raise_for_status()
        client.post("/api/v1/probes", headers=headers, json={"count": 40}).raise_for_status()
        incident = client.get("/api/v1/incidents", headers=headers).json()[0]
        report = client.post(f"/api/v1/incidents/{incident['id']}/investigate", headers=headers)
        report.raise_for_status()
        plan = report.json()["proposal"]
        response = client.post("/api/v1/recovery", headers=headers, json={"proposal_id": plan["id"], "approved": True, "actor": "smoke-operator"})
        response.raise_for_status()
        assert response.json()["verified"]
        assert "fleetops_inference_requests_total" in client.get("/metrics").text
    print("PASS: Gradio, health, inventory-backed investigation, approved recovery, and metrics")


if __name__ == "__main__":
    main()
