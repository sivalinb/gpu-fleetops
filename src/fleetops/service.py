"""Session lifecycle and shared provider budget for the API and Gradio UI."""

import time
import uuid
from threading import RLock

from .agent import Investigator, Quota
from .config import Settings
from .lab import Lab
from .store import Store
from .telemetry import Telemetry


class FleetOps:
    def __init__(self, settings: Settings, *, provider=None):
        self.settings = settings
        self.store = Store(settings.database_url)
        self.telemetry = Telemetry(endpoint=settings.otlp_endpoint, log_path=settings.log_path)
        self.investigator = Investigator(settings, provider=provider, quota=Quota())
        self.labs: dict[str, tuple[Lab, float]] = {}
        self.lock = RLock()

    def session(self, namespace: str) -> Lab:
        try:
            uuid.UUID(namespace)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("Session identifier must be a UUID") from exc
        with self.lock:
            now = time.monotonic()
            for key, (_, touched) in list(self.labs.items()):
                if now - touched > self.settings.session_ttl_seconds:
                    self.labs.pop(key)
                    self.telemetry.forget_lab(key)
                    self.store.clear(key)
            if namespace not in self.labs:
                if len(self.labs) >= self.settings.max_sessions:
                    raise ValueError("Demo session capacity reached; try again after an idle session expires")
                self.labs[namespace] = (Lab(self.store, namespace, self.telemetry), now)
            lab = self.labs[namespace][0]
            self.labs[namespace] = (lab, now)
            return lab

    def new_session(self) -> str:
        namespace = str(uuid.uuid4())
        self.session(namespace)
        return namespace

    def investigate(self, namespace: str, incident_id: str | None = None) -> dict:
        lab = self.session(namespace)
        active = lab.incidents(active_only=True)
        if not active:
            raise ValueError("Run a failure drill and probes to create an active incident")
        return self.investigator.investigate(lab, incident_id or active[0]["id"])

    def close(self):
        self.telemetry.close()
        self.store.close()

    def reliability_replay(self, seed=2026, assets=1000, namespace=None):
        from .reliability.reporting import build_bundle
        if namespace is not None:
            self.session(namespace)
        started = time.monotonic()
        with self.telemetry.tracer.start_as_current_span("reliability.replay") as span:
            span.set_attribute("reliability.origin", "synthetic")
            span.set_attribute("reliability.assets", assets)
            result = build_bundle(seed, assets)
        self.telemetry.reliability_runs.labels("synthetic").inc()
        self.telemetry.reliability_seconds.observe(time.monotonic()-started)
        for field in ("interruptions", "operating_hours", "unknown_hours"):
            self.telemetry.reliability_last.labels(field).set(result["analysis"]["summary"][field])
        self.telemetry.log("reliability.replay.completed", origin="synthetic", assets=assets, seed=seed)
        if namespace is not None:
            self.store.put(namespace, "reliability", dict(id="latest", timestamp=time.time(), **result))
        return result
