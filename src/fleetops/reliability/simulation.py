"""Seeded fictional fleet and a randomized follow-up; truth stays outside analysis."""

from collections import defaultdict

import numpy as np

from .adapters import encode, normalize
from .analysis import analyze
from .contracts import Dataset, Entity, Event, Interval
from .statistics import rate, rate_ratio

PROVIDERS = ["csp-aurora", "csp-borealis", "csp-cirrus"]


def simulate(
    seed: int = 2026, assets: int = 1000, *, phase: str = "before"
) -> tuple[Dataset, dict]:
    if not 60 <= assets <= 1500 or not 0 <= seed < 2**32 or phase not in {"before", "after"}:
        raise ValueError("Require 60–1500 GPUs, a uint32 seed, and before/after phase")
    layout = np.random.default_rng(seed)
    rng = np.random.default_rng(seed + (1 if phase == "after" else 0) + 100)
    entities, events = [], []
    truth = {
        "software": "systemic_candidate",
        "thermal": "environmental_candidate",
        "interconnect": "configuration_candidate",
        "memory": "unresolved",
    }
    for i in range(assets):
        provider = PROVIDERS[i % 3]
        rack = f"{provider}-rack-{i // 3 % 4}"
        candidate = bool(layout.random() < 0.5)
        canary = bool(layout.random() < 0.5)
        configured = bool(layout.random() < 0.18)
        exclusions = []
        if layout.random() < 0.1:
            exclusions.append(Interval(start=12, stop=14, state="maintenance"))
        if layout.random() < 0.08:
            exclusions.append(Interval(start=80, stop=88, state="unknown"))
        eligible = candidate and provider != "csp-cirrus"
        entity = Entity(
            id=f"gpu-{i:04}",
            provider=provider,
            rack=rack,
            node=f"{rack}-node-{i // 96}",
            model=f"lab-gpu-{i % 2}",
            driver="candidate" if candidate else "stable",
            firmware="fabric-profile-b" if configured else "fw-a",
            workload="training" if layout.random() < 0.6 else "inference",
            age_band="new" if layout.random() < 0.25 else "established",
            arm=("canary" if canary else "control") if eligible else "unaffected",
            stop=168,
            exclusions=exclusions,
        )
        entities.append(entity)

        def emit(
            start,
            duration,
            domain,
            signal,
            key,
            interrupted=True,
            *,
            entity=entity,
            provider=provider,
        ):
            stop = min(entity.stop, start + duration)
            if stop <= start:
                return
            event = Event(
                id=f"{phase}:{entity.id}:{key}:0",
                entity_id=entity.id,
                incident_key=key,
                start=float(start),
                stop=float(stop),
                domain=domain,
                signal=signal,
                interrupted=interrupted,
                origin="synthetic",
            )
            for repeat in range(3):
                copy = event.model_copy(update={"id": f"{event.id}:{repeat}"})
                events.append(normalize(provider, encode(provider, copy)))

        for domain, intensity, duration, signal in [
            ("memory", 0.0004, 0.5, "LAB_MEMORY_INTERRUPT"),
            (
                "software",
                0.007 if eligible and not (phase == "after" and canary) else 0.00015,
                0.35,
                "LAB_DRIVER_INTERRUPT",
            ),
            ("interconnect", 0.0025 if configured else 0, 0.8, "LAB_FABRIC_CONFIG_INTERRUPT"),
        ]:
            for k in range(int(rng.poisson(intensity * 168))):
                start = float(rng.uniform(1, 166))
                if any(x.start <= start < x.stop for x in exclusions):
                    continue
                emit(start, duration, domain, signal, f"{domain}-{i}-{k}")
        if rack == "csp-cirrus-rack-0":
            emit(60, 5, "thermal", "LAB_COOLING_INTERRUPT", "shared-cooling-episode")
        if i % 25 == 0:
            emit(40, 0.01, "memory", "LAB_MEMORY_WARNING", f"warning-{i}", False)
        if exclusions and exclusions[0].state == "maintenance":
            emit(12.5, 0.1, "software", "LAB_PLANNED_RESTART", f"maintenance-{i}")

    # Explicit node/job observation schedules. A job occupies one node for this lab.
    by_node = defaultdict(list)
    for entity in entities:
        by_node[entity.node].append(entity)
    gpu_events = list(events)
    for node, gpus in by_node.items():
        prototype = gpus[0]
        exclusion_intervals = sorted(
            {(x.start, x.stop, x.state) for g in gpus for x in g.exclusions}
        )
        for unit in ("node", "job"):
            entity_id = f"{unit}:{node}"
            entities.append(
                prototype.model_copy(
                    update=dict(
                        id=entity_id,
                        unit=unit,
                        driver="mixed",
                        firmware="mixed",
                        arm="unaffected",
                        exclusions=[
                            Interval(start=a, stop=b, state=s) for a, b, s in exclusion_intervals
                        ],
                    )
                )
            )
            ids = {g.id for g in gpus}
            for event in gpu_events:
                if event.entity_id in ids:
                    events.append(
                        event.model_copy(update=dict(id=f"{unit}:{event.id}", entity_id=entity_id))
                    )
    data = Dataset(
        description=f"Synthetic {phase} fleet, seed {seed}; fictional CSPs and GPU models",
        entities=entities,
        events=events,
    )
    return data, dict(
        seed=seed,
        phase=phase,
        assets=assets,
        expected_patterns=truth,
        intervention="Randomized driver mitigation in eligible canary GPUs; concurrent controls retain regression",
        caution="Generator assumptions demonstrate methodology; they establish no real hardware failure rates",
    )


def controlled_experiment(seed: int = 2026, assets: int = 1000) -> dict:
    before, _ = simulate(seed, assets)
    after, _ = simulate(seed, assets, phase="after")
    baseline = analyze(before, fit_weibull=False)
    followup = analyze(after, fit_weibull=False)
    phases = {}
    for name, analysis in (("before", baseline), ("after", followup)):
        phases[name] = {}
        for arm in ("canary", "control"):
            rows = [r for r in analysis["entity_metrics"] if r["arm"] == arm]
            phases[name][arm] = rate(
                sum(r["interruptions"] for r in rows), sum(r["operating_hours"] for r in rows)
            )
    a, b = phases["after"]["canary"], phases["after"]["control"]
    ratio = rate_ratio(
        a["interruptions"], a["operating_hours"], b["interruptions"], b["operating_hours"]
    )
    reduction = 1 - ratio["ratio"] if ratio["ratio"] is not None else None
    return dict(
        origin="synthetic",
        seed=seed,
        assets=assets,
        phases=phases,
        contemporaneous_canary_to_control=ratio,
        relative_rate_reduction=reduction,
        acceptance=dict(
            min_relative_reduction=0.3,
            ci_upper_below_one=True,
            passed=bool(reduction is not None and reduction >= 0.3 and ratio["ci95"][1] < 1),
        ),
        method="Randomized assignment fixed before outcomes; compare concurrent eligible canary/control cohorts",
        limits="Synthetic independent driver outcomes; no production effectiveness, rare-event or long-term reliability claim",
    )
