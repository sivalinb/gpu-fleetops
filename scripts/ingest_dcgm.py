"""Scrape an operator-configured exporter and send it to FleetOps.

Discover the GPU UUIDs in the catalog first. URLs and keys are supplied only by
the operator's environment, never from public Gradio input.
"""

import os

import httpx


def main():
    token = os.environ["FLEETOPS_API_TOKEN"]
    session = os.environ["FLEETOPS_SESSION"]
    exporter = os.environ["DCGM_EXPORTER_URL"]
    api = os.getenv("FLEETOPS_URL", "http://127.0.0.1:7860")
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        scrape = client.get(exporter.rstrip("/") + "/metrics")
        scrape.raise_for_status()
        response = client.post(api.rstrip("/") + "/api/v1/integrations/dcgm",
                               headers={"Authorization": "Bearer " + token, "X-FleetOps-Session": session},
                               json={"exposition": scrape.text})
        response.raise_for_status()
        print("Accepted DCGM observations:", response.json()["accepted"])


if __name__ == "__main__":
    main()
