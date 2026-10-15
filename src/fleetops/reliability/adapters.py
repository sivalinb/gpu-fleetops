"""Three fictional CSP schemas, deliberately unrelated to native cloud APIs."""

from .contracts import Event


def normalize(provider: str, row: dict) -> Event:
    if provider == "csp-aurora":
        values = dict(
            id=row["event_id"],
            entity_id=row["gpu"],
            incident_key=row["episode"],
            start=row["start_hours"],
            stop=row["end_hours"],
            domain=row["domain"],
            signal=row["code"],
            interrupted=row["job_interrupted"],
            origin=row["origin"],
        )
    elif provider == "csp-borealis":
        values = dict(
            id=row["id"],
            entity_id=row["asset"],
            incident_key=row["correlation"],
            start=row["begin_seconds"] / 3600,
            stop=row["finish_seconds"] / 3600,
            domain=row["subsystem"],
            signal=row["signal"],
            interrupted=row["impact"] == "interruption",
            origin=row["provenance"],
        )
        if row["impact"] not in {"interruption", "warning"}:
            raise ValueError("Unknown impact classification")
    elif provider == "csp-cirrus":
        values = dict(
            id=row["key"],
            entity_id=row["target"]["id"],
            incident_key=row["incident"],
            start=row["window"][0],
            stop=row["window"][1],
            domain=row["type"],
            signal=row["reason"],
            interrupted=row["interrupted"],
            origin=row["origin"],
        )
    else:
        raise ValueError("Unsupported fictional provider")
    return Event.model_validate(values)


def encode(provider: str, event: Event) -> dict:
    e = event
    if provider == "csp-aurora":
        return dict(
            event_id=e.id,
            gpu=e.entity_id,
            episode=e.incident_key,
            start_hours=e.start,
            end_hours=e.stop,
            domain=e.domain,
            code=e.signal,
            job_interrupted=e.interrupted,
            origin=e.origin,
        )
    if provider == "csp-borealis":
        return dict(
            id=e.id,
            asset=e.entity_id,
            correlation=e.incident_key,
            begin_seconds=e.start * 3600,
            finish_seconds=e.stop * 3600,
            subsystem=e.domain,
            signal=e.signal,
            impact="interruption" if e.interrupted else "warning",
            provenance=e.origin,
        )
    if provider == "csp-cirrus":
        return dict(
            key=e.id,
            target={"id": e.entity_id},
            incident=e.incident_key,
            window=[e.start, e.stop],
            type=e.domain,
            reason=e.signal,
            interrupted=e.interrupted,
            origin=e.origin,
        )
    raise ValueError("Unsupported fictional provider")
