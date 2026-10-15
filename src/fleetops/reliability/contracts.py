"""Versioned, source-explicit contracts. Times are hours from a dataset's epoch."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Interval(Strict):
    start: float = Field(ge=0)
    stop: float = Field(gt=0)
    state: Literal["maintenance", "unknown"]

    @model_validator(mode="after")
    def ordered(self):
        if self.stop <= self.start:
            raise ValueError("Interval stop must exceed start")
        return self


class Entity(Strict):
    id: str = Field(min_length=1, max_length=120)
    unit: Literal["gpu", "node", "job"] = "gpu"
    provider: str = Field(min_length=1, max_length=80)
    rack: str = Field(min_length=1, max_length=80)
    node: str = Field(min_length=1, max_length=80)
    model: str = "illustrative-accelerator"
    driver: str = "stable"
    firmware: str = "fw-a"
    workload: str = "training"
    age_band: str = "established"
    arm: str = "observational"
    start: float = Field(default=0, ge=0)
    stop: float = Field(gt=0)
    exclusions: list[Interval] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def ordered(self):
        if self.stop <= self.start:
            raise ValueError("Entity stop must exceed start")
        if any(x.start < self.start or x.stop > self.stop for x in self.exclusions):
            raise ValueError("Exclusions must lie within entity observation")
        return self


class Event(Strict):
    id: str = Field(min_length=1, max_length=160)
    entity_id: str = Field(min_length=1, max_length=120)
    incident_key: str = Field(min_length=1, max_length=160)
    start: float = Field(ge=0)
    stop: float = Field(gt=0)
    domain: Literal["compute", "memory", "interconnect", "power", "thermal", "software", "unknown"]
    signal: str = Field(min_length=1, max_length=120)
    interrupted: bool
    origin: Literal["synthetic", "replayed", "live"]

    @model_validator(mode="after")
    def ordered(self):
        if self.stop <= self.start:
            raise ValueError("Event stop must exceed start")
        return self


class Dataset(Strict):
    schema_version: Literal["1.0"] = "1.0"
    epoch: str = "2026-10-01T00:00:00Z"
    description: str = "Operator-supplied reliability observations"
    entities: list[Entity] = Field(max_length=5000)
    events: list[Event] = Field(max_length=50000)

    @model_validator(mode="after")
    def identities(self):
        entities = {x.id: x for x in self.entities}
        if len(entities) != len(self.entities):
            raise ValueError("Entity IDs must be unique")
        seen = {}
        for event in self.events:
            if event.entity_id not in entities:
                raise ValueError("Event references unknown entity")
            entity = entities[event.entity_id]
            if not entity.start <= event.start < event.stop <= entity.stop:
                raise ValueError("Event must lie within its entity observation")
            if event.id in seen and seen[event.id] != event:
                raise ValueError("Conflicting duplicate source event ID")
            seen[event.id] = event
        return self


class SimulationRequest(Strict):
    seed: int = Field(default=2026, ge=0, le=2**32 - 1)
    assets: int = Field(default=1000, ge=60, le=1500)


def union(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result = []
    for start, stop in sorted(intervals):
        if stop <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(stop, result[-1][1]))
        else:
            result.append((start, stop))
    return result


def overlap(intervals: list[tuple[float, float]], start: float, stop: float) -> float:
    return sum(max(0, min(b, stop) - max(a, start)) for a, b in union(intervals))
