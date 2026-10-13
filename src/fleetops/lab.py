"""The reliability lab: workload -> telemetry -> detection -> incident -> recovery.

GPU health and service latency are explicitly simulated. The CPU classification
workload, database, pipeline, incident workflows, and recovery checks execute.
"""

import hashlib
import time
import uuid
from threading import RLock

import numpy as np

from .adapters import parse_dcgm
from .inventory import Inventory
from .models import SCENARIOS, AssetSnapshot, Fault
from .runbooks import RUNBOOKS
from .slo import OBJECTIVES, burn_alert, is_good, report
from .store import ConflictError, Store
from .telemetry import Telemetry

SERVICE = "inference-api"
QUEUE_LIMIT = 1000
PROBE_LIMIT = 2000
ACTIVE = {"open", "acknowledged", "mitigating"}


def identifier(prefix: str) -> str:
    return prefix + "-" + uuid.uuid4().hex[:16]


class Lab:
    def __init__(self, store: Store, namespace: str, telemetry: Telemetry, *, start_time: float | None = None):
        self.store, self.namespace, self.telemetry = store, namespace, telemetry
        self.lock = RLock()
        self.inventory = Inventory(store, namespace)
        self.weights = np.random.default_rng(2026).normal(size=(64, 4))
        if self.store.get(namespace, "state", "lab") is None:
            self._initialize(start_time or time.time())

    @property
    def state(self) -> dict:
        return self.store.get(self.namespace, "state", "lab")

    @property
    def now(self) -> float:
        return self.state["simulation_time"]

    def _save_state(self, **changes) -> None:
        old = self.state
        self.store.put(self.namespace, "state", {**old, **changes}, expected_revision=old["_revision"])

    def _initialize(self, now: float):
        self.store.put(self.namespace, "state", {
            "id": "lab", "timestamp": now, "simulation_time": now, "fault": "healthy",
            "change_revision": 0, "maintenance_until": 0, "collector_available": True,
            "live_investigations": 0,
            "probe_count": 0, "investigation_count": 0,
        })
        self.inventory.seed(now)
        self.store.add_observations(self.namespace, [
            {"id": identifier("seed"), "service_id": SERVICE, "timestamp": now - (240 - i) * 30,
             "status": 200, "latency_ms": 90 + i % 40, "execution_ms": 0,
             "trace_id": "seeded-baseline", "source": "synthetic-baseline"} for i in range(240)
        ])
        self.evidence("catalog", "Seeded three illustrative fleet environments", source="synthetic", assets=10)
        self.refresh_metrics()

    def reset(self):
        with self.lock:
            self.store.clear(self.namespace)
            self._initialize(time.time())
        return self.summary()

    def evidence(self, kind: str, message: str, *, source: str = "synthetic", **attributes) -> dict:
        item = {"id": identifier("ev"), "timestamp": self.now, "kind": kind,
                "service_id": SERVICE, "message": message, "source": source, **attributes}
        kind_table = "evidence"
        if not self.state["collector_available"] and kind in {"log", "trace", "metric"} and source != "control-plane":
            kind_table = "outbox"
            if len(self.store.list(self.namespace, "outbox", limit=QUEUE_LIMIT + 1)) >= QUEUE_LIMIT:
                self.telemetry.dropped.inc()
                return {**item, "dropped": True}
        self.store.put(self.namespace, kind_table, item)
        return item

    def timeline(self, incident_id: str, event: str, **attributes):
        self.store.put(self.namespace, "timeline", {
            "id": identifier("tl"), "incident_id": incident_id, "timestamp": self.now,
            "event": event, **attributes,
        })

    def inject(self, fault: Fault | str) -> dict:
        fault = Fault(fault)
        with self.lock:
            if any(incident["status"] in ACTIVE for incident in self.incidents()):
                raise ConflictError("Finish or reset the current incident before starting another drill")
            if fault == Fault.HEALTHY:
                raise ValueError("Use approved recovery or reset to restore a lab")
            self._save_state(fault=fault.value, change_revision=self.state["change_revision"] + 1,
                             collector_available=fault != Fault.TELEMETRY_OUTAGE)
            self.evidence("deployment", "Configuration revision changed", revision=self.state["change_revision"],
                          config_key="batch_size" if fault in {Fault.GPU_OOM, Fault.ALERT_STORM} else "dependency_config")
            if fault == Fault.TELEMETRY_OUTAGE:
                signal = self.evidence("metric", "Telemetry exporter unavailable", source="control-plane", code="EXPORTER_DOWN")
                self.emit_alert("telemetry-unavailable", "Telemetry delivery interrupted", [signal["id"]])
            elif fault == Fault.INVENTORY_DRIFT:
                gpu = self.store.get(self.namespace, "asset", "GPU-DEMO-0001")
                gpu["driver_version"] = "510.00"
                gpu["observed_at"] = self.now + 1
                snapshot = AssetSnapshot.model_validate({k: v for k, v in gpu.items() if k != "_revision"})
                self.inventory.reconcile(snapshot, self.now)
                signal = self.evidence("catalog", "Observed driver differs from desired driver", code="DRIVER_DRIFT", asset_id=gpu["id"],
                                       observed_driver="510.00", desired_driver=gpu["desired_driver"])
                self.emit_alert("inventory-driver-drift", "GPU driver inventory drift", [signal["id"]])
            self.telemetry.log("fault_injected", fault=fault.value, source="synthetic")
            return {"fault": fault.value, "description": SCENARIOS[fault][1]}

    def _infer(self, text: str, sequence: int) -> dict:
        started = time.perf_counter()
        features = np.frombuffer(hashlib.sha512(text.encode()).digest(), dtype=np.uint8) / 255
        prediction = int(np.argmax(features @ self.weights))
        execution = (time.perf_counter() - started) * 1000
        fault = Fault(self.state["fault"])
        status, latency, code = 200, 90.0 + sequence % 40, "OK"
        if fault in {Fault.GPU_OOM, Fault.ALERT_STORM}:
            status, latency, code = 503, 420.0, "CUDA_OUT_OF_MEMORY"
        elif fault == Fault.STORAGE_LATENCY:
            latency, code = 650.0 + sequence % 100, "ARTIFACT_STORE_SLOW"
        elif fault == Fault.NODE_DOWN:
            status, latency, code = 503, 500.0, "NODE_NOT_READY"
        elif fault == Fault.UNKNOWN:
            status, latency, code = 503, 400.0, "UNCLASSIFIED_FAILURE"
        return {"prediction": prediction, "execution_ms": execution, "latency_ms": latency,
                "status": status, "code": code, "simulated": True}

    def probe(self, count: int = 40, text: str = "reliable GPU infrastructure") -> dict:
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 500:
            raise ValueError("Probe count must be an integer from 1 to 500")
        if not isinstance(text, str) or not 1 <= len(text) <= 512:
            raise ValueError("Workload text must be between 1 and 512 characters")
        with self.lock, self.telemetry.tracer.start_as_current_span("lab.probe_batch"):
            if self.state.get("probe_count", 0) + count > PROBE_LIMIT:
                raise ValueError("This demo session reached its probe budget; reset your lab to continue")
            rows, signals = [], []
            for sequence in range(count):
                self._save_state(simulation_time=self.now + 6)
                with self.telemetry.tracer.start_as_current_span("workload.inference", attributes={"fleetops.simulated": True, "service.id": SERVICE}) as span:
                    result = self._infer(text, sequence)
                    trace_id = f"{span.get_span_context().trace_id:032x}"
                    row = {"id": identifier("req"), "service_id": SERVICE, "timestamp": self.now,
                           "status": result["status"], "latency_ms": result["latency_ms"],
                           "execution_ms": result["execution_ms"], "trace_id": trace_id, "source": "synthetic"}
                    rows.append(row)
                    signal = self.evidence("log", "Inference result", code=result["code"], status=result["status"], trace_id=trace_id)
                    self.evidence("trace", "Inference dependency span", trace_id=trace_id,
                                  dependency="artifact-store", duration_ms=550 if result["code"] == "ARTIFACT_STORE_SLOW" else 12,
                                  status=result["status"])
                    if not signal.get("dropped"):
                        signals.append(signal["id"])
                    self.telemetry.requests.labels(SERVICE, "success" if result["status"] == 200 else "failure").inc()
                    self.telemetry.latency.labels(SERVICE, "success" if result["status"] == 200 else "failure").observe(result["latency_ms"] / 1000)
                    self.telemetry.log("inference_completed", status=result["status"], code=result["code"], trace_id=trace_id, source="synthetic")
            self.store.add_observations(self.namespace, rows)
            self._save_state(probe_count=self.state.get("probe_count", 0) + count)
            slo = self.slo()
            for objective in OBJECTIVES:
                # A historical burn alone must not reopen a verified incident.
                # A new unhealthy batch is required for incident creation/updates.
                if any(not is_good(row, objective) for row in rows) and burn_alert(self.requests(), self.now, objective)["firing"]:
                    self.emit_alert("workload-slo", "Inference service is burning its error budget", signals[-20:])
                    if self.state["fault"] == Fault.ALERT_STORM:
                        for _ in range(25):
                            self.emit_alert("workload-slo", "Repeated inference alert", signals[-5:])
            self.escalate()
            self.refresh_metrics()
            return {"probes": count, "successful": sum(row["status"] == 200 for row in rows),
                    "last": result, "slo": slo, "open_incidents": len(self.incidents(active_only=True))}

    def requests(self) -> list[dict]:
        return self.store.requests(self.namespace, until=self.now)

    def slo(self) -> dict:
        return report(self.requests(), self.now)

    def incidents(self, *, active_only: bool = False) -> list[dict]:
        items = self.store.list(self.namespace, "incident")
        return [item for item in items if item["status"] in ACTIVE] if active_only else items

    def emit_alert(self, fingerprint: str, title: str, evidence_ids: list[str], *, service_id: str = SERVICE) -> dict:
        with self.lock:
            service = self.store.get(self.namespace, "service", service_id)
            if not service:
                raise ValueError("Alert references an unknown service")
            if any(self.store.get(self.namespace, "evidence", eid) is None for eid in evidence_ids):
                raise ValueError("Alert evidence must exist in this session")
            if self.now < self.state["maintenance_until"]:
                self.evidence("event", "Paging suppressed during maintenance", fingerprint=fingerprint)
                return {"suppressed": True, "fingerprint": fingerprint}
            for incident in self.incidents(active_only=True):
                if incident["fingerprint"] == fingerprint and incident["service_id"] == service_id:
                    incident["alert_count"] += 1
                    incident["evidence_ids"] = list(dict.fromkeys(incident["evidence_ids"] + evidence_ids))[-40:]
                    self.store.put(self.namespace, "incident", incident, expected_revision=incident["_revision"])
                    self.telemetry.dedup.inc()
                    return self.store.get(self.namespace, "incident", incident["id"])
            incident = {"id": identifier("inc"), "timestamp": self.now, "service_id": service_id,
                        "title": title, "fingerprint": fingerprint, "status": "open",
                        "owner": service["owner"], "escalation": service["escalation"],
                        "alert_count": 1, "evidence_ids": evidence_ids, "escalated": False,
                        "detected_at": self.now, "resolved_at": None,
                        "source": self.store.get(self.namespace, "evidence", evidence_ids[0])["source"] if evidence_ids else "operator"}
            self.store.put(self.namespace, "incident", incident)
            self.timeline(incident["id"], "incident_created", owner=incident["owner"])
            self.telemetry.incidents.inc()
            self.telemetry.log("incident_created", incident_id=incident["id"], owner=incident["owner"])
            return incident

    def maintenance(self, minutes: int) -> dict:
        if not 0 <= minutes <= 120:
            raise ValueError("Maintenance must be between zero and 120 minutes")
        with self.lock:
            self._save_state(maintenance_until=self.now + minutes * 60 if minutes else 0)
            self.evidence("event", "Maintenance window updated", minutes=minutes)
            return {"maintenance_until": self.state["maintenance_until"], "slo_exclusion": False}

    def advance(self, seconds: int) -> dict:
        if not 0 <= seconds <= 7200:
            raise ValueError("Clock advancement must be between zero and 7,200 seconds")
        with self.lock:
            self._save_state(simulation_time=self.now + seconds)
            self.escalate()
            return self.summary()

    def escalate(self):
        for incident in self.incidents(active_only=True):
            if incident["status"] == "open" and not incident["escalated"] and self.now - incident["detected_at"] >= 300:
                incident["escalated"] = True
                self.store.put(self.namespace, "incident", incident, expected_revision=incident["_revision"])
                self.timeline(incident["id"], "escalated", owner=incident["escalation"])

    def acknowledge(self, incident_id: str, actor: str) -> dict:
        with self.lock:
            incident = self.store.get(self.namespace, "incident", incident_id)
            if not incident or incident["status"] != "open":
                raise ConflictError("Only an open incident can be acknowledged")
            incident["status"] = "acknowledged"
            self.store.put(self.namespace, "incident", incident, expected_revision=incident["_revision"])
            self.timeline(incident_id, "acknowledged", actor=actor)
            return incident

    def ingest_dcgm(self, exposition: str) -> dict:
        with self.lock:
            metrics = parse_dcgm(exposition)
            unknown = {metric["gpu_id"] for metric in metrics if not self.store.get(self.namespace, "asset", metric["gpu_id"])}
            if unknown:
                raise ValueError("Discover GPU inventory before ingesting metrics for unknown UUIDs")
            for metric in metrics:
                evidence = self.evidence("metric", "NVIDIA DCGM observation", **metric)
                self.telemetry.gpu.labels(metric["gpu_id"], metric["name"]).set(metric["value"])
                if metric["name"] in {"DCGM_FI_DEV_XID_ERRORS", "DCGM_FI_DEV_ECC_DBE_VOL_TOTAL"} and metric["value"] > 0:
                    self.emit_alert("gpu-hardware-health", "GPU hardware health signal requires investigation", [evidence["id"]])
            return {"accepted": len(metrics), "source": "dcgm", "simulated": False}

    def create_proposal(self, incident_id: str, diagnosis: dict) -> dict | None:
        if diagnosis["abstained"] or diagnosis["action"] == "none":
            return None
        incident = self.store.get(self.namespace, "incident", incident_id)
        if not incident or incident["status"] not in ACTIVE:
            raise ConflictError("Incident is no longer active")
        proposal = {"id": identifier("plan"), "timestamp": self.now, "incident_id": incident_id,
                    "action": diagnosis["action"], "status": "awaiting_approval",
                    "change_revision": self.state["change_revision"], "incident_revision": incident["_revision"],
                    "evidence_ids": [eid for hypothesis in diagnosis["hypotheses"] for eid in hypothesis["evidence_ids"]]}
        self.store.put(self.namespace, "proposal", proposal)
        self.timeline(incident_id, "recovery_proposed", action=proposal["action"])
        return proposal

    def fix(self, proposal_id: str, *, approved: bool, actor: str) -> dict:
        if not approved:
            raise ValueError("Explicit operator approval is required")
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 80 or not actor.isprintable():
            raise ValueError("A printable operator name is required")
        with self.lock, self.telemetry.tracer.start_as_current_span("incident.recovery"):
            proposal = self.store.get(self.namespace, "proposal", proposal_id)
            if not proposal or proposal["status"] != "awaiting_approval":
                raise ConflictError("Recovery proposal does not exist or was already used")
            incident = self.store.get(self.namespace, "incident", proposal["incident_id"])
            if (not incident or incident["status"] not in ACTIVE
                or proposal["change_revision"] != self.state["change_revision"]
                or proposal["incident_revision"] != incident["_revision"]):
                raise ConflictError("Recovery proposal is stale; investigate again")
            action = proposal["action"]
            if action not in {book["action"] for book in RUNBOOKS.values()} - {"none"}:
                raise ValueError("Action is not in the runbook allowlist")
            if self.state.get("probe_count", 0) + 20 > PROBE_LIMIT:
                raise ValueError("Recovery needs 20 remaining probes; reset your lab to continue")
            proposal["status"] = "executed"
            self.store.put(self.namespace, "proposal", proposal, expected_revision=proposal["_revision"])
            incident["status"] = "mitigating"
            self.store.put(self.namespace, "incident", incident, expected_revision=incident["_revision"])
            self.timeline(incident["id"], "recovery_approved", actor=actor.strip(), action=action)
            recovered = 0
            expected_faults = {
                "rollback": {Fault.GPU_OOM, Fault.ALERT_STORM}, "restore_storage": {Fault.STORAGE_LATENCY},
                "restore_node": {Fault.NODE_DOWN}, "restore_telemetry": {Fault.TELEMETRY_OUTAGE},
                "reconcile_inventory": {Fault.INVENTORY_DRIFT},
            }
            if Fault(self.state["fault"]) in expected_faults[action]:
                if action == "restore_telemetry":
                    self._save_state(collector_available=True)
                    recovered = self.store.drain_outbox(self.namespace)
                if action == "reconcile_inventory":
                    gpu = self.store.get(self.namespace, "asset", "GPU-DEMO-0001")
                    gpu["driver_version"] = gpu["desired_driver"]
                    gpu["observed_at"] = self.now + 2
                    self.inventory.reconcile(AssetSnapshot.model_validate({k: v for k, v in gpu.items() if k != "_revision"}), self.now)
                self._save_state(fault="healthy", change_revision=self.state["change_revision"] + 1)
            verification = self.probe(20)
            checks = self.requests()[-20:]
            successful = all(row["status"] == 200 and row["latency_ms"] <= 300 for row in checks)
            if action == "restore_telemetry":
                successful = successful and not self.store.list(self.namespace, "outbox")
            if action == "reconcile_inventory":
                successful = successful and not any(asset["drift"] for asset in self.inventory.all(self.now))
            incident = self.store.get(self.namespace, "incident", incident["id"])
            if successful:
                incident.update(status="resolved", resolved_at=self.now)
                self.store.put(self.namespace, "incident", incident, expected_revision=incident["_revision"])
            self.timeline(incident["id"], "recovery_verified" if successful else "recovery_failed", probes=20, queued_records_replayed=recovered)
            self.telemetry.fixes.labels(action, "verified" if successful else "failed").inc()
            self.refresh_metrics()
            return {"verified": successful, "incident_id": incident["id"], "replayed": recovered, "verification": verification,
                    "error_budget_reset": False}

    def refresh_metrics(self):
        self.telemetry.update_lab(self.namespace, self.slo(), len(self.store.list(self.namespace, "outbox")))

    def summary(self) -> dict:
        return {"simulation": True, "simulation_time": self.now, "fault": self.state["fault"],
                "slo": self.slo(), "incidents": self.incidents(),
                "inventory": self.inventory.all(self.now),
                "queue_size": len(self.store.list(self.namespace, "outbox")),
                "maintenance_active": self.now < self.state["maintenance_until"]}

    def postmortem(self, incident_id: str) -> str:
        incident = self.store.get(self.namespace, "incident", incident_id)
        if not incident:
            raise ValueError("Unknown incident")
        timeline = sorted((row for row in self.store.list(self.namespace, "timeline") if row["incident_id"] == incident_id), key=lambda row: row["timestamp"])
        import datetime
        lines = [f"# Incident {incident_id}", "", f"Status: {incident['status']} | Owner: {incident['owner']}", "",
                 "This report describes a synthetic portfolio drill. Timestamps use the simulation clock.", "", "## Timeline", ""]
        for item in timeline:
            stamp = datetime.datetime.fromtimestamp(item["timestamp"], datetime.UTC).isoformat()
            details = ", ".join(f"{key}: {item[key]}" for key in ("owner", "actor", "action", "probes", "queued_records_replayed") if key in item)
            lines.append(f"- {stamp}: {item['event']}" + (f" — {details}" if details else ""))
        reports = [row for row in self.store.list(self.namespace, "investigation") if row["incident_id"] == incident_id]
        if reports:
            lines.extend(["", "## Investigation", "", reports[0]["diagnosis"]["summary"]])
        lines.extend(["", "## Prevention", "", "Add a deployment validation gate, test the failure in CI, and review the alert and runbook with the owning team.",
                      "", "## Reliability impact", "", "Recovery restores service. Historical failed and slow requests continue to consume the 30-day error budget."])
        return "\n".join(lines)
