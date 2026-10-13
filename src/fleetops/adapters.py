"""Real discovery/telemetry parsers. No remote URL is accepted from a public UI."""

from math import isfinite

from prometheus_client.parser import text_string_to_metric_families

from .models import AssetSnapshot

DCGM_FIELDS = {
    "DCGM_FI_DEV_GPU_UTIL", "DCGM_FI_DEV_FB_USED", "DCGM_FI_DEV_FB_TOTAL",
    "DCGM_FI_DEV_GPU_TEMP", "DCGM_FI_DEV_POWER_USAGE", "DCGM_FI_DEV_XID_ERRORS",
    "DCGM_FI_DEV_ECC_DBE_VOL_TOTAL",
}


def parse_dcgm(exposition: str) -> list[dict]:
    if len(exposition) > 100000:
        raise ValueError("DCGM payload exceeds 100 KB")
    values = []
    for family in text_string_to_metric_families(exposition):
        for sample in family.samples:
            if sample.name not in DCGM_FIELDS:
                continue
            if not isfinite(sample.value) or sample.value < 0 or sample.value > 1e15:
                raise ValueError("DCGM value must be finite, nonnegative, and within field range")
            gpu_id = sample.labels.get("UUID", sample.labels.get("uuid", ""))
            if not gpu_id or len(gpu_id) > 120:
                raise ValueError("DCGM metric needs a valid GPU UUID")
            values.append({"name": sample.name, "value": sample.value, "gpu_id": gpu_id, "source": "dcgm", "simulated": False})
    if not values:
        raise ValueError("Payload contains no supported DCGM GPU metrics")
    return values


def parse_kubernetes_nodes(document: dict, *, cluster_id: str, environment: str, observed_at: float) -> list[AssetSnapshot]:
    if document.get("kind") != "NodeList" or not isinstance(document.get("items"), list):
        raise ValueError("Expected a Kubernetes NodeList")
    if len(document["items"]) > 2000:
        raise ValueError("Discovery batch exceeds 2,000 nodes")
    nodes = []
    for node in document["items"]:
        metadata = node.get("metadata", {})
        labels = metadata.get("labels", {})
        node_id = metadata.get("uid") or metadata.get("name")
        nodes.append(AssetSnapshot(
            id=node_id, name=metadata.get("name", ""), kind="node", environment=environment,
            parent_id=cluster_id, owner=labels.get("fleetops.io/owner", ""), source="kubernetes",
            observed_at=observed_at, service_ids=["inference-api"], simulated=False,
        ))
    return nodes
