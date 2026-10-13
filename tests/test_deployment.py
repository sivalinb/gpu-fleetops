import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("file", ["docker-compose.yml", "observability/prometheus.yml", "observability/alerts.yml", "observability/otel-collector.yml", "observability/loki.yml", "observability/tempo.yml", "observability/grafana/datasources.yml", "observability/grafana/dashboard-provider.yml", ".github/workflows/ci.yml", ".github/workflows/container.yml"])
def test_yaml_configuration_parses(file):
    assert isinstance(yaml.safe_load((ROOT / file).read_text()), dict)


def test_compose_ports_are_local_and_api_secret_is_not_hardcoded():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    for service in compose["services"].values():
        assert all(port.startswith("127.0.0.1:") for port in service.get("ports", []))
    assert "${FLEETOPS_API_TOKEN" in compose["services"]["app"]["environment"]["FLEETOPS_API_TOKEN"]


def test_kubernetes_has_persistent_storage_and_probes():
    resources = list(yaml.safe_load_all((ROOT / "kubernetes/fleetops.yml").read_text()))
    deployment = next(resource for resource in resources if resource["kind"] == "Deployment")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert deployment["spec"]["replicas"] == 1
    assert "readinessProbe" in container and "livenessProbe" in container
    assert any(resource["kind"] == "PersistentVolumeClaim" for resource in resources)


def test_observability_has_all_three_signal_backends():
    collector = yaml.safe_load((ROOT / "observability/otel-collector.yml").read_text())
    assert "file_storage" in collector["extensions"]
    assert "traces" in collector["service"]["pipelines"]
    assert "logs" in collector["service"]["pipelines"]
    for exporter in collector["exporters"].values():
        assert exporter["sending_queue"]["storage"] == "file_storage"


def test_grafana_dashboard_has_slo_queue_logs_and_gpu_panels():
    dashboard = json.loads((ROOT / "observability/grafana/fleetops.json").read_text())
    titles = " ".join(panel["title"] for panel in dashboard["panels"])
    assert "SLI" in titles and "Telemetry" in titles and "GPU" in titles and "Logs" in titles


def test_prometheus_rule_denominators_match_app_objectives():
    rules = yaml.safe_load((ROOT / "observability/alerts.yml").read_text())["groups"][0]["rules"]
    availability = next(rule for rule in rules if rule.get("alert") == "FleetOpsAvailabilityFastBurn")
    latency = next(rule for rule in rules if rule.get("alert") == "FleetOpsLatencyFastBurn")
    assert "/ 0.005" in availability["expr"]
    assert "/ 0.01" in latency["expr"]
    good_latency = next(rule for rule in rules if rule.get("record") == "fleetops:latency_error_ratio:5m")
    assert 'outcome="success"' in good_latency["expr"]
