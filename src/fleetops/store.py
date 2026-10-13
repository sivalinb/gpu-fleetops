"""SQL persistence with namespace isolation and optimistic concurrency checks.

Entity documents are versioned JSON; request observations have dedicated relational
columns for SLI queries. Both SQLite and PostgreSQL use the same SQLAlchemy schema.
"""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.pool import StaticPool


class ConflictError(ValueError):
    """A plan or update was based on an obsolete revision."""


class Store:
    def __init__(self, url: str = "sqlite:///:memory:") -> None:
        if url.startswith("sqlite:///") and ":memory:" not in url:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        options: dict[str, Any] = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                options["poolclass"] = StaticPool
        self.engine = create_engine(url, **options)
        self.lock = RLock()
        metadata = MetaData()
        self.entities = Table(
            "entities", metadata,
            Column("namespace", String(80), primary_key=True),
            Column("kind", String(40), primary_key=True),
            Column("id", String(120), primary_key=True),
            Column("revision", Integer, nullable=False),
            Column("timestamp", Float, nullable=False),
            Column("payload", JSON, nullable=False),
        )
        self.observations = Table(
            "observations", metadata,
            Column("namespace", String(80), primary_key=True),
            Column("id", String(80), primary_key=True),
            Column("service_id", String(80), nullable=False),
            Column("timestamp", Float, nullable=False),
            Column("status", Integer, nullable=False),
            Column("latency_ms", Float, nullable=False),
            Column("execution_ms", Float, nullable=False),
            Column("trace_id", String(80), nullable=False),
            Column("source", String(40), nullable=False),
        )
        Index("ix_observation_window", self.observations.c.namespace, self.observations.c.service_id, self.observations.c.timestamp)
        Index("ix_entity_time", self.entities.c.namespace, self.entities.c.kind, self.entities.c.timestamp)
        metadata.create_all(self.engine)

    def _key(self, namespace: str, kind: str, entity_id: str):
        return (
            (self.entities.c.namespace == namespace)
            & (self.entities.c.kind == kind)
            & (self.entities.c.id == entity_id)
        )

    def get(self, namespace: str, kind: str, entity_id: str) -> dict | None:
        with self.lock, self.engine.connect() as conn:
            row = conn.execute(select(self.entities).where(self._key(namespace, kind, entity_id))).mappings().first()
            return {**row["payload"], "_revision": row["revision"]} if row else None

    def list(self, namespace: str, kind: str, *, since: float = 0, limit: int = 2000) -> list[dict]:
        with self.lock, self.engine.connect() as conn:
            rows = conn.execute(
                select(self.entities)
                .where((self.entities.c.namespace == namespace) & (self.entities.c.kind == kind) & (self.entities.c.timestamp >= since))
                .order_by(self.entities.c.timestamp.desc(), self.entities.c.id)
                .limit(limit)
            ).mappings().all()
            return [{**row["payload"], "_revision": row["revision"]} for row in rows]

    def put(self, namespace: str, kind: str, payload: dict, *, expected_revision: int | None = None) -> dict:
        clean = {k: v for k, v in payload.items() if k != "_revision"}
        key = self._key(namespace, kind, clean["id"])
        with self.lock, self.engine.begin() as conn:
            old = conn.execute(select(self.entities.c.revision).where(key)).scalar_one_or_none()
            if expected_revision is not None and old != expected_revision:
                raise ConflictError("Record changed; refresh before continuing")
            revision = (old or 0) + 1
            values = {"revision": revision, "timestamp": clean.get("timestamp", clean.get("observed_at", 0)), "payload": clean}
            if old is None:
                conn.execute(insert(self.entities).values(namespace=namespace, kind=kind, id=clean["id"], **values))
            else:
                result = conn.execute(update(self.entities).where(key & (self.entities.c.revision == old)).values(**values))
                if result.rowcount != 1:
                    raise ConflictError("Concurrent update rejected")
        return {**clean, "_revision": revision}

    def add_observations(self, namespace: str, values: list[dict]) -> None:
        if values:
            with self.lock, self.engine.begin() as conn:
                conn.execute(insert(self.observations), [{"namespace": namespace, **v} for v in values])

    def requests(self, namespace: str, *, since: float = 0, until: float = float("inf"), service_id: str = "inference-api") -> list[dict]:
        with self.lock, self.engine.connect() as conn:
            rows = conn.execute(select(self.observations).where(
                (self.observations.c.namespace == namespace)
                & (self.observations.c.service_id == service_id)
                & (self.observations.c.timestamp >= since)
                & (self.observations.c.timestamp <= until)
            ).order_by(self.observations.c.timestamp)).mappings().all()
            return [dict(row) for row in rows]

    def delete(self, namespace: str, kind: str, entity_id: str) -> None:
        with self.lock, self.engine.begin() as conn:
            conn.execute(delete(self.entities).where(self._key(namespace, kind, entity_id)))

    def clear(self, namespace: str) -> None:
        with self.lock, self.engine.begin() as conn:
            conn.execute(delete(self.entities).where(self.entities.c.namespace == namespace))
            conn.execute(delete(self.observations).where(self.observations.c.namespace == namespace))

    def drain_outbox(self, namespace: str) -> int:
        """Move queued evidence and delete the queue in one database transaction."""
        with self.lock, self.engine.begin() as conn:
            condition = (self.entities.c.namespace == namespace) & (self.entities.c.kind == "outbox")
            queued = conn.execute(select(self.entities).where(condition)).mappings().all()
            for row in queued:
                key = self._key(namespace, "evidence", row["id"])
                if conn.execute(select(self.entities.c.id).where(key)).first() is None:
                    conn.execute(insert(self.entities).values(namespace=namespace, kind="evidence", id=row["id"], revision=1, timestamp=row["timestamp"], payload=row["payload"]))
            conn.execute(delete(self.entities).where(condition))
            return len(queued)

    def close(self) -> None:
        self.engine.dispose()
