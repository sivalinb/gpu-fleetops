"""Measure catalog reconciliation and probe throughput on the current machine."""

import argparse
import json
import platform
import time
from pathlib import Path

from fleetops.lab import Lab
from fleetops.models import AssetSnapshot
from fleetops.store import Store
from fleetops.telemetry import Telemetry


def benchmark(count=1000):
    store, telemetry = Store(), Telemetry()
    telemetry.logger.disabled = True
    lab = Lab(store, "benchmark", telemetry)
    started = time.perf_counter()
    for index in range(count):
        lab.inventory.reconcile(AssetSnapshot(id=f"GPU-LOAD-{index:06d}", name=f"Logical GPU {index}", kind="gpu",
                                             environment="cloud", owner="compute-platform", observed_at=lab.now,
                                             parent_id="node-cloud-01", service_ids=["inference-api"]), lab.now)
    catalog_seconds = time.perf_counter() - started
    started = time.perf_counter()
    lab.probe(500)
    probe_seconds = time.perf_counter() - started
    result = {"platform": platform.platform(), "python": platform.python_version(), "logical_gpu_records": count,
              "catalog_seconds": round(catalog_seconds, 4), "catalog_records_per_second": round(count / catalog_seconds, 2),
              "probes": 500, "probe_seconds": round(probe_seconds, 4), "probes_per_second": round(500 / probe_seconds, 2),
              "scope": "Single-process synthetic catalog and workload on this machine. Includes synchronous persistence and evidence creation. Does not measure physical GPU or distributed fleet performance."}
    telemetry.close()
    store.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=int, default=1000)
    parser.add_argument("--output", default="reports/benchmark.json")
    args = parser.parse_args()
    if not 1 <= args.assets <= 5000:
        parser.error("assets must be between 1 and 5000")
    result = benchmark(args.assets)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Catalog: {result['catalog_records_per_second']} records/s. Probes: {result['probes_per_second']} requests/s. {destination}")


if __name__ == "__main__":
    main()
