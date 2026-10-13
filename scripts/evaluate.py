"""Reproducible scenario evaluation; reports baseline results without LLM claims."""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from fleetops.agent import Investigator
from fleetops.config import Settings
from fleetops.lab import Lab
from fleetops.models import SCENARIOS
from fleetops.runbooks import RUNBOOKS
from fleetops.store import Store
from fleetops.telemetry import Telemetry


def evaluate() -> dict:
    store, telemetry = Store(), Telemetry()
    telemetry.logger.disabled = True
    investigator = Investigator(Settings())
    results = []
    for index, fault in enumerate(SCENARIOS):
        lab = Lab(store, "eval-" + fault.value, telemetry, start_time=1700000000 + index * 10000)
        start = time.perf_counter()
        lab.inject(fault)
        lab.probe(40)
        incident = lab.incidents()[0]
        report = investigator.investigate(lab, incident["id"])
        diagnosis = report["diagnosis"]
        cause = "gpu_oom" if fault.value == "alert_storm" else fault.value
        expected = RUNBOOKS[cause]["action"]
        cited = [eid for hypothesis in diagnosis["hypotheses"] for eid in hypothesis["evidence_ids"]]
        recovery = lab.fix(report["proposal"]["id"], approved=True, actor="evaluation-operator") if report["proposal"] else None
        results.append({
            "scenario": fault.value, "expected_action": expected, "actual_action": diagnosis["action"],
            "correct_action": diagnosis["action"] == expected, "abstained": diagnosis["abstained"],
            "citation_ids_resolve": all(store.get(lab.namespace, "evidence", eid) is not None for eid in cited),
            "verified_recovery": recovery["verified"] if recovery else None,
            "grouped_alert_count": lab.incidents()[0]["alert_count"],
            "wall_seconds": round(time.perf_counter() - start, 4),
            "detection_simulation_seconds": incident["detected_at"] - (1700000000 + index * 10000),
        })
    telemetry.close()
    store.close()
    return {"generated_at": datetime.now(UTC).isoformat(), "mode": "deterministic rules baseline",
            "scope": "Seven synthetic, known scenarios. These are regression evaluations, not a held-out LLM accuracy benchmark or real GPU performance claim.",
            "scenario_count": len(results), "correct_actions": sum(result["correct_action"] for result in results),
            "verified_recoveries": sum(result["verified_recovery"] is True for result in results), "results": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/evaluation.json")
    args = parser.parse_args()
    result = evaluate()
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{result['correct_actions']}/{result['scenario_count']} expected baseline actions; {result['verified_recoveries']} verified recoveries. Report: {destination}")
    if result["correct_actions"] != result["scenario_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
