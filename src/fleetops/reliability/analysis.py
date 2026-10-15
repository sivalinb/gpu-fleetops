"""Exposure-aware summaries. Classification outputs are hypotheses, not causal verdicts."""

from collections import defaultdict

from .contracts import Dataset, Entity, overlap
from .statistics import kaplan_meier, rate, rate_ratio, weibull


def episodes(data: Dataset, unit: str = "gpu") -> list[dict]:
    entities = {e.id: e for e in data.entities if e.unit == unit}
    grouped = defaultdict(list)
    seen = set()
    for e in data.events:
        if e.id in seen:
            continue
        seen.add(e.id)
        entity = entities.get(e.entity_id)
        if not entity or not e.interrupted:
            continue
        if any(x.start <= e.start < x.stop for x in entity.exclusions):
            continue
        grouped[(e.entity_id, e.incident_key)].append(e)
    result = []
    for (entity_id, key), rows in grouped.items():
        # A reused incident key cannot silently collapse disconnected outages.
        current = None
        for event in sorted(rows, key=lambda e: e.start):
            if current is None or event.start > current["stop"] + 1 / 120:
                current = dict(
                    entity_id=entity_id,
                    incident_key=key,
                    start=event.start,
                    stop=event.stop,
                    domains=set(),
                    signals=set(),
                    origins=set(),
                    incident_keys={key},
                    source_records=0,
                )
                result.append(current)
            current["stop"] = max(current["stop"], event.stop)
            current["domains"].add(event.domain)
            current["signals"].add(event.signal)
            current["origins"].add(event.origin)
            current["source_records"] += 1
    merged = []
    for row in sorted(result, key=lambda e: (e["entity_id"], e["start"])):
        if (
            merged
            and merged[-1]["entity_id"] == row["entity_id"]
            and row["start"] <= merged[-1]["stop"]
        ):
            previous = merged[-1]
            previous["stop"] = max(previous["stop"], row["stop"])
            for key in ("domains", "signals", "origins", "incident_keys"):
                previous[key].update(row[key])
            previous["source_records"] += row["source_records"]
        else:
            merged.append(row)
    for e in merged:
        e["domain"] = next(iter(e["domains"])) if len(e["domains"]) == 1 else "unknown"
        for key in ("domains", "signals", "origins", "incident_keys"):
            e[key] = sorted(e[key])
    return sorted(merged, key=lambda e: (e["start"], e["entity_id"]))


def entity_summary(entity: Entity, rows: list[dict]) -> dict:
    excluded = [(x.start, x.stop) for x in entity.exclusions]
    down = [(r["start"], r["stop"]) for r in rows]
    observed = entity.stop - entity.start - overlap(excluded, entity.start, entity.stop)
    operating = entity.stop - entity.start - overlap(excluded + down, entity.start, entity.stop)
    unknown = overlap(
        [(x.start, x.stop) for x in entity.exclusions if x.state == "unknown"],
        entity.start,
        entity.stop,
    )
    # First-event survival ends at the first unknown telemetry interval.
    censor = min([x.start for x in entity.exclusions if x.state == "unknown"] + [entity.stop])
    first = min([r["start"] for r in rows if r["start"] < censor] + [censor])
    survival_hours = first - entity.start - overlap(excluded, entity.start, first)
    return dict(
        entity_id=entity.id,
        unit=entity.unit,
        provider=entity.provider,
        rack=entity.rack,
        driver=entity.driver,
        firmware=entity.firmware,
        workload=entity.workload,
        model=entity.model,
        age_band=entity.age_band,
        arm=entity.arm,
        interruptions=len(rows),
        operating_hours=max(0, operating),
        lost_hours=max(0, observed - operating),
        unknown_hours=unknown,
        observed_hours=max(0, observed),
        span_hours=entity.stop - entity.start,
        survival_hours=max(0, survival_hours),
        failed=first < censor,
    )


def pareto_loss(entities: list[Entity], eps: list[dict]) -> list[dict]:
    """Episodes are disjoint; multi-domain episodes retain an unknown attribution."""
    totals = defaultdict(float)
    by_entity = defaultdict(list)
    for row in eps:
        by_entity[row["entity_id"]].append(row)
    for entity in entities:
        excluded = [(x.start, x.stop) for x in entity.exclusions]
        for row in by_entity[entity.id]:
            totals[row["domain"]] += (
                row["stop"] - row["start"] - overlap(excluded, row["start"], row["stop"])
            )
    total = sum(totals.values())
    running = 0
    result = []
    for domain, hours in sorted(totals.items(), key=lambda pair: -pair[1]):
        running += hours
        result.append(
            dict(
                domain=domain,
                lost_hours=hours,
                share=hours / total if total else 0,
                cumulative_share=running / total if total else 0,
            )
        )
    return result


def compare_drivers(rows: list[dict], suspect="candidate", baseline="stable") -> dict:
    # Exact stratum matching controls measured workload, environment, model and age.
    strata = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
    for row in rows:
        if row["driver"] not in (suspect, baseline):
            continue
        key = tuple(
            row[x] for x in ("provider", "rack", "model", "firmware", "workload", "age_band")
        )
        value = strata[key][row["driver"]]
        value[0] += row["interruptions"]
        value[1] += row["operating_hours"]
    common = [
        (key, value)
        for key, value in strata.items()
        if all(value[d][1] > 0 for d in (suspect, baseline))
    ]
    weight_total = sum(sum(v[d][1] for d in (suspect, baseline)) for _, v in common)
    if not weight_total:
        return dict(status="no_common_support", matched_strata=0, by_provider=[])
    standardized = {
        d: sum(
            sum(v[k][1] for k in (suspect, baseline)) / weight_total * v[d][0] / v[d][1]
            for _, v in common
        )
        * 1000
        for d in (suspect, baseline)
    }
    by_provider = []
    for provider in sorted({key[0] for key, _ in common}):
        subset = [v for key, v in common if key[0] == provider]
        a = [sum(v[suspect][i] for v in subset) for i in (0, 1)]
        b = [sum(v[baseline][i] for v in subset) for i in (0, 1)]
        weight = sum(v[suspect][1] + v[baseline][1] for v in subset)
        std_a = (
            sum(
                (v[suspect][1] + v[baseline][1]) / weight * v[suspect][0] / v[suspect][1]
                for v in subset
            )
            * 1000
        )
        std_b = (
            sum(
                (v[suspect][1] + v[baseline][1]) / weight * v[baseline][0] / v[baseline][1]
                for v in subset
            )
            * 1000
        )
        by_provider.append(
            dict(
                provider=provider,
                suspect=rate(int(a[0]), a[1]),
                baseline=rate(int(b[0]), b[1]),
                standardized_suspect=std_a,
                standardized_baseline=std_b,
                raw_rate_ratio=rate_ratio(int(a[0]), a[1], int(b[0]), b[1]),
            )
        )
    return dict(
        status="exploratory_matched_comparison",
        matched_strata=len(common),
        matched_exposure_hours=weight_total,
        standardized_per_1000_hours=standardized,
        standardized_ratio=standardized[suspect] / standardized[baseline]
        if standardized[baseline]
        else None,
        by_provider=by_provider,
        limits="Measured strata only; residual confounding and correlated events remain. No causal or significance claim.",
    )


def classify_patterns(eps: list[dict], rows: list[dict], comparison: dict) -> list[dict]:
    entities = {r["entity_id"]: r for r in rows}
    groups = defaultdict(list)
    for e in eps:
        groups[e["domain"]].append(e)
    results = []
    for domain, events in groups.items():
        providers = sorted({entities[e["entity_id"]]["provider"] for e in events})
        racks = sorted({entities[e["entity_id"]]["rack"] for e in events})
        firmware = sorted({entities[e["entity_id"]]["firmware"] for e in events})
        support = [
            r
            for r in comparison.get("by_provider", [])
            if r["standardized_suspect"] > r["standardized_baseline"]
            and r["suspect"]["interruptions"] >= 5
        ]
        if len(events) < 5:
            category, reason = "insufficient_evidence", "Fewer than five interruption episodes"
        elif domain == "software" and len(support) >= 2:
            category, reason = (
                "systemic_candidate",
                "Candidate driver has higher matched software-interruption rates in ≥2 providers; reproduce on hardware",
            )
        elif len(racks) == 1:
            category, reason = (
                "environmental_candidate",
                "Observed interruptions concentrate in one rack; compare cooling, power and placement",
            )
        elif len(firmware) == 1 and len({r["firmware"] for r in rows}) > 1:
            category, reason = (
                "configuration_candidate",
                "Episodes concentrate in one firmware/configuration cohort; validate a matched configuration experiment",
            )
        else:
            category, reason = (
                "unresolved",
                "Observed pattern does not distinguish the competing causes",
            )
        results.append(
            dict(
                domain=domain,
                classification=category,
                episodes=len(events),
                providers=providers,
                racks=racks,
                firmware=firmware,
                explanation=reason,
                evidence_ids=sorted({e["incident_key"] for e in events})[:12],
                confidence="hypothesis_for_validation",
            )
        )
    return sorted(results, key=lambda r: -r["episodes"])


def analyze(data: Dataset, unit: str = "gpu", *, fit_weibull: bool = True) -> dict:
    if unit not in {"gpu", "node", "job"}:
        raise ValueError("Unit must be gpu, node, or job")
    entities = [e for e in data.entities if e.unit == unit]
    eps = episodes(data, unit)
    grouped = defaultdict(list)
    for e in eps:
        grouped[e["entity_id"]].append(e)
    rows = [entity_summary(e, grouped[e.id]) for e in entities]
    summary = rate(len(eps), sum(r["operating_hours"] for r in rows))
    span = sum(r["span_hours"] for r in rows)
    entity_ids = {x.id for x in entities}
    summary.update(
        unit=unit,
        entities=len(entities),
        unique_incidents=len({key for e in eps for key in e["incident_keys"]}),
        raw_records=sum(e.entity_id in entity_ids for e in data.events),
        lost_hours=sum(r["lost_hours"] for r in rows),
        unknown_hours=sum(r["unknown_hours"] for r in rows),
        coverage_ratio=1 - sum(r["unknown_hours"] for r in rows) / span if span else None,
        origins=sorted({o for e in eps for o in e["origins"]}),
    )
    cohorts = []
    for provider in sorted({r["provider"] for r in rows}):
        for driver in sorted({r["driver"] for r in rows if r["provider"] == provider}):
            subset = [r for r in rows if r["provider"] == provider and r["driver"] == driver]
            cohorts.append(
                dict(
                    provider=provider,
                    driver=driver,
                    entities=len(subset),
                    **rate(
                        sum(r["interruptions"] for r in subset),
                        sum(r["operating_hours"] for r in subset),
                    ),
                )
            )
    observations = [
        (r["survival_hours"], r["failed"]) for r in rows if r["survival_hours"] > 0 or r["failed"]
    ]
    comparison = compare_drivers(rows)
    software_counts = defaultdict(int)
    for event in eps:
        if event["domain"] == "software":
            software_counts[event["entity_id"]] += 1
    domain_comparison = compare_drivers(
        [{**r, "interruptions": software_counts[r["entity_id"]]} for r in rows]
    )
    return dict(
        schema_version="1.0",
        description=data.description,
        summary=summary,
        cohorts=cohorts,
        driver_comparison=comparison,
        software_driver_comparison=domain_comparison,
        pareto=pareto_loss(entities, eps),
        survival=kaplan_meier(observations),
        weibull=weibull(observations) if fit_weibull else {"status": "not_requested"},
        patterns=classify_patterns(eps, rows, domain_comparison),
        entity_metrics=rows,
        episodes=eps,
        methodology="docs/reliability/MEASUREMENT.md",
        limitations=[
            "MTBI here is operating entity-hours / interruption episodes, an inverse rate estimator.",
            "GPU, node and job denominators are distinct; no unit is inferred from GPU-hours.",
            "Correlated failures make naive Poisson intervals optimistic.",
            "Survival is time to FIRST interruption, censored at first unknown coverage.",
            "The pooled Weibull fit may mix cohorts; review fit gap and homogeneous subcohorts.",
        ],
    )
