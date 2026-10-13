"""Prometheus metrics, structured JSON logs, and optional OTLP traces."""

import json
import logging
import sys
import uuid
from pathlib import Path
from threading import RLock

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"timestamp": record.created, "level": record.levelname,
                           "service": "gpu-fleetops", "event": record.getMessage(),
                           **getattr(record, "fields", {})})


class Telemetry:
    def __init__(self, *, endpoint: str = "", log_path: str = ""):
        self.registry = CollectorRegistry()
        self._lab_stats = {}
        self._stats_lock = RLock()
        self.requests = Counter("fleetops_inference_requests_total", "Workload requests (synthetic demo unless adapter source is real)", ["service", "outcome"], registry=self.registry)
        self.latency = Histogram("fleetops_inference_latency_seconds", "Reported service latency", ["service", "outcome"], buckets=(.05, .1, .2, .3, .5, 1, 2), registry=self.registry)
        self.api_requests = Counter("fleetops_http_requests_total", "API requests", ["route", "status"], registry=self.registry)
        self.incidents = Counter("fleetops_incidents_created_total", "Unique incidents created", registry=self.registry)
        self.dedup = Counter("fleetops_alerts_deduplicated_total", "Duplicate alerts grouped", registry=self.registry)
        self.sli = Gauge("fleetops_sli_ratio", "Current request-based SLI", ["service", "objective"], registry=self.registry)
        self.burn = Gauge("fleetops_slo_burn_rate", "Observed-window error-budget consumption rate", ["service", "objective"], registry=self.registry)
        self.outbox = Gauge("fleetops_telemetry_queue_size", "Queued evidence records across active sessions", registry=self.registry)
        self.dropped = Counter("fleetops_telemetry_dropped_total", "Records dropped because the outbox is full", registry=self.registry)
        self.agent_calls = Counter("fleetops_agent_calls_total", "Investigator invocations", ["mode", "outcome"], registry=self.registry)
        self.fixes = Counter("fleetops_recovery_actions_total", "Approved runbook executions", ["action", "outcome"], registry=self.registry)
        self.gpu = Gauge("fleetops_gpu_observation", "Operator-ingested DCGM fields; units depend on the field", ["gpu_id", "field"], registry=self.registry)
        self.provider = TracerProvider(resource=Resource.create({"service.name": "gpu-fleetops", "deployment.environment.name": "portfolio-lab"}))
        if endpoint:
            self.provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces", timeout=5)))
        self.tracer = self.provider.get_tracer("fleetops", "1.0.0")
        self.logger = logging.getLogger("fleetops." + uuid.uuid4().hex)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)
        if log_path:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path)
            file_handler.setFormatter(JSONFormatter())
            self.logger.addHandler(file_handler)

    def log(self, event: str, **fields):
        self.logger.info(event, extra={"fields": fields})

    def exposition(self) -> bytes:
        return generate_latest(self.registry)

    def update_lab(self, namespace: str, slo: dict, queue_size: int):
        with self._stats_lock:
            self._lab_stats[namespace] = (slo, queue_size)
            for objective in ("availability", "latency"):
                total = sum(values[0][objective]["total"] for values in self._lab_stats.values())
                bad = sum(values[0][objective]["bad"] for values in self._lab_stats.values())
                allowed = sum(values[0][objective]["allowed_bad"] for values in self._lab_stats.values())
                self.sli.labels("inference-api", objective).set((total - bad) / total if total else 0)
                self.burn.labels("inference-api", objective).set(bad / allowed if allowed else 0)
            self.outbox.set(sum(values[1] for values in self._lab_stats.values()))

    def forget_lab(self, namespace: str):
        with self._stats_lock:
            self._lab_stats.pop(namespace, None)

    def close(self):
        self.provider.shutdown()
        for handler in list(self.logger.handlers):
            handler.close()
            self.logger.removeHandler(handler)
