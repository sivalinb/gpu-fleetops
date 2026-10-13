"""Bounded recovery actions; these never run arbitrary shell commands."""

RUNBOOKS = {
    "gpu_oom": {"action": "rollback", "owner": "ml-platform", "steps": ["Compare the deployment and CUDA error timestamps.", "Restore the prior batch-size configuration.", "Run recovery probes and verify successful responses."]},
    "storage_latency": {"action": "restore_storage", "owner": "storage-platform", "steps": ["Inspect dependency trace durations.", "Remove the simulated artifact-store latency injection.", "Verify latency and availability with recovery probes."]},
    "node_down": {"action": "restore_node", "owner": "compute-platform", "steps": ["Check node readiness and service placement.", "Restore the simulated node; confirm workload readiness.", "Run recovery probes."]},
    "telemetry_outage": {"action": "restore_telemetry", "owner": "observability-platform", "steps": ["Confirm exporter failure and bounded queue growth.", "Restore export and atomically replay the persistent queue.", "Confirm queue drainage without duplicating evidence."]},
    "inventory_drift": {"action": "reconcile_inventory", "owner": "compute-platform", "steps": ["Compare desired and observed driver versions and discovery sources.", "Restore the demo inventory to its declared desired state.", "Reconcile and confirm there are no remaining driver conflicts."]},
    "unknown": {"action": "none", "owner": "ml-platform", "steps": ["Collect workload logs, node health, and deployment history.", "Escalate with the missing evidence; do not guess a recovery action."]},
}

ACTION_CAUSE = {book["action"]: cause for cause, book in RUNBOOKS.items() if book["action"] != "none"}
