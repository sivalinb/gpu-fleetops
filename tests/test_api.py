import pytest
from fastapi.testclient import TestClient

from fleetops.api import create_app
from fleetops.config import Settings


@pytest.fixture
def client():
    app = create_app(Settings(database_url="sqlite:///:memory:", api_token="operator-test-token"), mount_ui=False)
    app.state.service.telemetry.logger.disabled = True
    with TestClient(app) as instance:
        yield instance


@pytest.fixture
def headers(client):
    auth = {"Authorization": "Bearer operator-test-token"}
    session = client.post("/api/v1/sessions", headers=auth).json()["session_id"]
    return {**auth, "X-FleetOps-Session": session}


def test_health_readiness_and_metrics_are_available(client):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").status_code == 200
    assert "fleetops_http_requests_total" in client.get("/metrics").text


def test_authentication_required(client):
    assert client.post("/api/v1/sessions").status_code == 401
    assert client.post("/api/v1/sessions", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_operator_api_disabled_without_token():
    app = create_app(Settings(database_url="sqlite:///:memory:"), mount_ui=False)
    with TestClient(app) as client:
        assert client.post("/api/v1/sessions").status_code == 503


@pytest.mark.integration
def test_api_full_incident_lifecycle(client, headers):
    assert client.post("/api/v1/faults", json={"fault": "gpu_oom"}, headers=headers).status_code == 200
    probes = client.post("/api/v1/probes", json={"count": 40}, headers=headers).json()
    assert probes["successful"] == 0
    incident = client.get("/api/v1/incidents", headers=headers).json()[0]
    result = client.post(f"/api/v1/incidents/{incident['id']}/investigate", headers=headers).json()
    plan_id = result["proposal"]["id"]
    assert client.post("/api/v1/recovery", json={"proposal_id": plan_id, "approved": False}, headers=headers).status_code == 422
    fixed = client.post("/api/v1/recovery", json={"proposal_id": plan_id, "approved": True}, headers=headers)
    assert fixed.status_code == 200 and fixed.json()["verified"]
    assert client.post("/api/v1/recovery", json={"proposal_id": plan_id, "approved": True}, headers=headers).status_code == 409
    assert "recovery_verified" in client.get(f"/api/v1/incidents/{incident['id']}/postmortem", headers=headers).text
    assert client.get("/api/v1/slo", headers=headers).json()["availability"]["bad"] == 40


@pytest.mark.parametrize("route", ["summary", "inventory", "incidents", "slo", "evidence"])
def test_read_endpoints(client, headers, route):
    assert client.get("/api/v1/" + route, headers=headers).status_code == 200


@pytest.mark.parametrize("payload", [{"count": 0}, {"count": 501}, {"count": True}, {"count": 1.5}, {"count": 1, "text": ""}, {"count": 1, "extra": "not allowed"}])
def test_probe_contract_rejects_invalid_inputs(client, headers, payload):
    assert client.post("/api/v1/probes", json=payload, headers=headers).status_code == 422


def test_sessions_do_not_share_faults_or_inventory(client, headers):
    other = {"Authorization": headers["Authorization"], "X-FleetOps-Session": client.post("/api/v1/sessions", headers=headers).json()["session_id"]}
    client.post("/api/v1/faults", json={"fault": "node_down"}, headers=headers)
    assert client.get("/api/v1/summary", headers=other).json()["fault"] == "healthy"


def test_foreign_incident_cannot_be_investigated(client, headers):
    other = {"Authorization": headers["Authorization"], "X-FleetOps-Session": client.post("/api/v1/sessions", headers=headers).json()["session_id"]}
    client.post("/api/v1/faults", json={"fault": "node_down"}, headers=headers)
    client.post("/api/v1/probes", json={"count": 40}, headers=headers)
    incident_id = client.get("/api/v1/incidents", headers=headers).json()[0]["id"]
    assert client.post(f"/api/v1/incidents/{incident_id}/investigate", headers=other).status_code == 422


def test_bad_session_id_rejected(client, headers):
    assert client.get("/api/v1/summary", headers={**headers, "X-FleetOps-Session": "invalid"}).status_code == 422


def test_inventory_and_integrations(client, headers):
    now = client.get("/api/v1/summary", headers=headers).json()["simulation_time"]
    snapshot = {"id": "GPU-REAL", "name": "Real GPU", "kind": "gpu", "environment": "cloud", "source": "dcgm", "observed_at": now, "simulated": False}
    assert client.post("/api/v1/inventory", json=snapshot, headers=headers).status_code == 200
    payload = {"exposition": 'DCGM_FI_DEV_GPU_UTIL{UUID="GPU-REAL"} 40'}
    assert client.post("/api/v1/integrations/dcgm", json=payload, headers=headers).json()["accepted"] == 1
    nodes = {"document": {"kind": "NodeList", "items": [{"metadata": {"uid": "real-node", "name": "real-node"}}]}, "cluster_id": "cluster-cloud", "environment": "cloud"}
    assert client.post("/api/v1/integrations/kubernetes", json=nodes, headers=headers).status_code == 200


def test_alert_and_maintenance_api(client, headers):
    client.post("/api/v1/maintenance", json={"minutes": 30}, headers=headers)
    response = client.post("/api/v1/alerts", json={"fingerprint": "example", "summary": "Maintenance test"}, headers=headers)
    assert response.json()["suppressed"]


def test_openapi_and_architecture(client):
    assert "/api/v1/recovery" in client.get("/api/openapi.json").json()["paths"]
    response = client.get("/fleetops-assets/architecture.svg")
    assert response.status_code == 200
    assert "GPU FleetOps" in response.text
