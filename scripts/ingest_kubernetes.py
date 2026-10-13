"""Read Kubernetes nodes with TLS verification and an operator service account."""

import os

import httpx


def main():
    headers = {"Authorization": "Bearer " + os.environ["KUBERNETES_TOKEN"]}
    kube_url = os.environ["KUBERNETES_API_URL"].rstrip("/")
    if not kube_url.startswith("https://"):
        raise SystemExit("Kubernetes discovery requires an HTTPS API server")
    # Optional custom CA is used through a verified SSLContext, never verify=False.
    import ssl
    context = ssl.create_default_context(cafile=os.getenv("KUBERNETES_CA_FILE") or None)
    with httpx.Client(timeout=10, verify=context, follow_redirects=False) as client:
        nodes = client.get(kube_url + "/api/v1/nodes", headers=headers)
        nodes.raise_for_status()
        response = client.post(os.getenv("FLEETOPS_URL", "http://127.0.0.1:7860").rstrip("/") + "/api/v1/integrations/kubernetes",
                               headers={"Authorization": "Bearer " + os.environ["FLEETOPS_API_TOKEN"],
                                        "X-FleetOps-Session": os.environ["FLEETOPS_SESSION"]},
                               json={"document": nodes.json(), "cluster_id": os.environ["FLEETOPS_CLUSTER_ID"],
                                     "environment": os.getenv("FLEETOPS_ENVIRONMENT", "on-prem")})
        response.raise_for_status()
        print("Reconciled nodes:", len(response.json()["results"]))


if __name__ == "__main__":
    main()
