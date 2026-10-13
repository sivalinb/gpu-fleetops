"""Validated contracts shared by the API, adapters, and investigator."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Fault(StrEnum):
    HEALTHY = "healthy"
    GPU_OOM = "gpu_oom"
    STORAGE_LATENCY = "storage_latency"
    NODE_DOWN = "node_down"
    TELEMETRY_OUTAGE = "telemetry_outage"
    INVENTORY_DRIFT = "inventory_drift"
    ALERT_STORM = "alert_storm"
    UNKNOWN = "unknown"


SCENARIOS = {
    Fault.GPU_OOM: ("GPU memory exhaustion", "A batch-size change produces CUDA memory errors."),
    Fault.STORAGE_LATENCY: ("Storage dependency latency", "An artifact-store dependency makes requests slow."),
    Fault.NODE_DOWN: ("GPU node unavailable", "The simulated GPU node stops accepting requests."),
    Fault.TELEMETRY_OUTAGE: ("Telemetry backend outage", "Telemetry accumulates in a durable, bounded outbox."),
    Fault.INVENTORY_DRIFT: ("Driver inventory drift", "Discovery observes a driver different from the desired version."),
    Fault.ALERT_STORM: ("Duplicate alert storm", "Repeated GPU errors must converge on one open incident."),
    Fault.UNKNOWN: ("Insufficient evidence", "Requests fail without a diagnostic signal; investigation should abstain."),
}


class AssetSnapshot(Contract):
    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    kind: Literal["cluster", "node", "gpu", "storage"]
    name: str = Field(min_length=1, max_length=120)
    environment: Literal["on-prem", "cloud", "partner"]
    owner: str = Field(default="", max_length=80)
    source: Literal["seed", "kubernetes", "dcgm", "manual"] = "seed"
    observed_at: float = Field(ge=0)
    parent_id: str | None = None
    service_ids: list[str] = Field(default_factory=list, max_length=20)
    driver_version: str = Field(default="", max_length=60)
    desired_driver: str = Field(default="", max_length=60)
    simulated: bool = True


class ProbeRequest(Contract):
    count: int = Field(default=40, ge=1, le=500, strict=True)
    text: str = Field(default="reliable GPU infrastructure", min_length=1, max_length=512)


class FaultRequest(Contract):
    fault: Fault


class MaintenanceRequest(Contract):
    minutes: int = Field(ge=0, le=120)


class FixRequest(Contract):
    proposal_id: str = Field(min_length=1, max_length=80)
    approved: bool = False
    actor: str = Field(default="demo-operator", min_length=1, max_length=80)

    @field_validator("actor")
    @classmethod
    def actor_is_printable(cls, value: str) -> str:
        if not value.isprintable() or not value.strip():
            raise ValueError("Actor must contain printable text")
        return value.strip()


class Hypothesis(Contract):
    cause: Literal["gpu_oom", "storage_latency", "node_down", "telemetry_outage", "inventory_drift", "unknown"]
    explanation: str = Field(min_length=1, max_length=1200)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


class Diagnosis(Contract):
    summary: str = Field(min_length=1, max_length=2000)
    hypotheses: list[Hypothesis] = Field(default_factory=list, max_length=3)
    action: Literal["rollback", "restore_storage", "restore_node", "restore_telemetry", "reconcile_inventory", "none"]
    abstained: bool = False
    missing_evidence: list[str] = Field(default_factory=list, max_length=10)


class DCGMRequest(Contract):
    exposition: str = Field(min_length=1, max_length=100000)


class AlertRequest(Contract):
    fingerprint: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    service_id: str = Field(default="inference-api", max_length=80)
    summary: str = Field(min_length=1, max_length=300)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
