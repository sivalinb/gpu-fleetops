"""Discovery reconciliation, ownership, provenance, and dependency lookup."""

import uuid

from .models import AssetSnapshot
from .store import Store

PRIORITY = {"seed": 0, "kubernetes": 10, "dcgm": 20, "manual": 30}
STALE_SECONDS = 86400


class Inventory:
    def __init__(self, store: Store, namespace: str):
        self.store = store
        self.namespace = namespace

    def reconcile(self, snapshot: AssetSnapshot, now: float) -> dict:
        if snapshot.observed_at > now + 300:
            raise ValueError("Discovery timestamp is more than five minutes in the future")
        if snapshot.parent_id and not self.store.get(self.namespace, "asset", snapshot.parent_id):
            raise ValueError("Parent asset must exist before child discovery")
        if any(not self.store.get(self.namespace, "service", sid) for sid in snapshot.service_ids):
            raise ValueError("Discovery references an unknown service")
        old = self.store.get(self.namespace, "asset", snapshot.id)
        incoming = snapshot.model_dump()
        status = "created"
        if old:
            if incoming["observed_at"] < old["observed_at"]:
                return {"status": "stale", "asset": old}
            if PRIORITY[incoming["source"]] < PRIORITY[old["source"]]:
                return {"status": "rejected_priority", "asset": old}
            conflicting = incoming["owner"] and old["owner"] and incoming["owner"] != old["owner"]
            if conflicting:
                self.store.put(self.namespace, "conflict", {
                    "id": uuid.uuid4().hex, "timestamp": now, "asset_id": snapshot.id,
                    "previous_owner": old["owner"], "observed_owner": incoming["owner"],
                    "source": incoming["source"], "resolved": False,
                })
            if incoming["observed_at"] == old["observed_at"] and conflicting:
                return {"status": "conflict", "asset": old}
            incoming["owner"] = incoming["owner"] or old["owner"]
            incoming["desired_driver"] = incoming["desired_driver"] or old["desired_driver"]
            status = "updated"
        result = self.store.put(self.namespace, "asset", incoming, expected_revision=old["_revision"] if old else None)
        return {"status": status, "asset": result}

    def all(self, now: float) -> list[dict]:
        assets = self.store.list(self.namespace, "asset")
        return [{**asset,
                 "stale": now - asset["observed_at"] > STALE_SECONDS,
                 "drift": bool(asset["desired_driver"] and asset["driver_version"] != asset["desired_driver"]),
                 "ownership_gap": not bool(asset["owner"])} for asset in assets]

    def for_service(self, service_id: str, now: float) -> dict:
        service = self.store.get(self.namespace, "service", service_id)
        if not service:
            raise ValueError("Unknown service")
        assets = [asset for asset in self.all(now) if service_id in asset["service_ids"]]
        return {"service": service, "assets": assets, "dependencies": service["dependencies"]}

    def seed(self, now: float) -> None:
        self.store.put(self.namespace, "service", {
            "id": "inference-api", "name": "GPU inference API", "owner": "ml-platform",
            "escalation": "compute-oncall", "dependencies": ["artifact-store"],
            "runbook": "inference-recovery", "timestamp": now,
        })
        self.store.put(self.namespace, "service", {
            "id": "artifact-store", "name": "Model artifact store", "owner": "storage-platform",
            "escalation": "storage-oncall", "dependencies": [], "runbook": "storage-recovery", "timestamp": now,
        })
        for environment, cluster, node, gpu in [
            ("on-prem", "cluster-denver", "node-dgx-01", "GPU-DEMO-0001"),
            ("cloud", "cluster-cloud", "node-cloud-01", "GPU-DEMO-0002"),
            ("partner", "cluster-partner", "node-partner-01", "GPU-DEMO-0003"),
        ]:
            for entity_id, kind, parent in [(cluster, "cluster", None), (node, "node", cluster), (gpu, "gpu", node)]:
                self.reconcile(AssetSnapshot(
                    id=entity_id, kind=kind, name=entity_id, environment=environment,
                    owner="compute-platform", observed_at=now, parent_id=parent,
                    service_ids=["inference-api"], driver_version="550.54.15" if kind == "gpu" else "",
                    desired_driver="550.54.15" if kind == "gpu" else "",
                ), now)
        self.reconcile(AssetSnapshot(id="storage-01", kind="storage", name="Model artifacts", environment="cloud",
                                     owner="storage-platform", observed_at=now, service_ids=["artifact-store"]), now)
