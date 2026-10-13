import json

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from fleetops.lab import Lab
from fleetops.telemetry import Telemetry


def test_structured_file_logs_and_real_trace_correlation(tmp_path, store):
    path = tmp_path / "telemetry.jsonl"
    meter = Telemetry(log_path=str(path))
    exporter = InMemorySpanExporter()
    meter.provider.add_span_processor(SimpleSpanProcessor(exporter))
    lab = Lab(store, "trace-test", meter, start_time=1700000000)
    lab.probe(2)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    logged = [record for record in records if record["event"] == "inference_completed"]
    spans = exporter.get_finished_spans()
    trace_ids = {f"{span.context.trace_id:032x}" for span in spans}
    assert len(logged) == 2
    assert all(record["trace_id"] in trace_ids for record in logged)
    assert all(record["source"] == "synthetic" for record in logged)
    meter.close()
