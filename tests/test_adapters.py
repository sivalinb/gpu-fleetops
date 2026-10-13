import pytest

from fleetops.adapters import parse_dcgm, parse_kubernetes_nodes

VALID = 'DCGM_FI_DEV_GPU_UTIL{UUID="GPU-DEMO-0001",gpu="0"} 80\nDCGM_FI_DEV_FB_USED{UUID="GPU-DEMO-0001"} 4096\n'


def test_real_dcgm_parser_preserves_source():
    metrics = parse_dcgm(VALID)
    assert len(metrics) == 2
    assert not metrics[0]["simulated"]
    assert metrics[0]["source"] == "dcgm"


@pytest.mark.parametrize("value", ["NaN", "+Inf", "-1", "1e20"])
def test_invalid_metric_values_rejected(value):
    with pytest.raises(ValueError):
        parse_dcgm('DCGM_FI_DEV_GPU_UTIL{UUID="GPU-X"} ' + value)


@pytest.mark.parametrize("payload", ["x" * 100001, "unsupported_metric 1", "DCGM_FI_DEV_GPU_UTIL 3"])
def test_invalid_dcgm_payload_rejected(payload):
    with pytest.raises(ValueError):
        parse_dcgm(payload)


def test_unknown_metrics_are_ignored():
    assert len(parse_dcgm(VALID + "unrelated_total 1\n")) == 2


def test_real_metrics_ingest_without_changing_simulated_workload(lab):
    result = lab.ingest_dcgm(VALID)
    assert result["accepted"] == 2 and not result["simulated"]
    assert lab.state["fault"] == "healthy"


def test_hardware_error_creates_incident_without_guessing_fix(lab):
    from fleetops.agent import Investigator
    from fleetops.config import Settings
    lab.ingest_dcgm('DCGM_FI_DEV_XID_ERRORS{UUID="GPU-DEMO-0001"} 79')
    assert len(lab.incidents()) == 1
    assert lab.incidents()[0]["source"] == "dcgm"
    result = Investigator(Settings()).investigate(lab, lab.incidents()[0]["id"])
    assert result["diagnosis"]["abstained"]


def test_unknown_gpu_requires_discovery(lab):
    with pytest.raises(ValueError, match="Discover"):
        lab.ingest_dcgm('DCGM_FI_DEV_GPU_UTIL{UUID="GPU-UNKNOWN"} 20')


def test_kubernetes_nodes_use_uid_and_ownership_label():
    document = {"kind": "NodeList", "items": [{"metadata": {"uid": "node-uid", "name": "gpu-node", "labels": {"fleetops.io/owner": "compute-team"}}}]}
    snapshots = parse_kubernetes_nodes(document, cluster_id="cluster", environment="cloud", observed_at=1000)
    assert snapshots[0].id == "node-uid"
    assert snapshots[0].owner == "compute-team"
    assert not snapshots[0].simulated


@pytest.mark.parametrize("document", [{"kind": "PodList", "items": []}, {"kind": "NodeList", "items": None}, {"kind": "NodeList", "items": [{}] * 2001}])
def test_invalid_kubernetes_documents_rejected(document):
    with pytest.raises(ValueError):
        parse_kubernetes_nodes(document, cluster_id="cluster", environment="cloud", observed_at=1000)
