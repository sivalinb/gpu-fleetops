from concurrent.futures import ThreadPoolExecutor

import pytest

from fleetops.agent import Investigator
from fleetops.config import Settings
from fleetops.lab import Lab
from fleetops.models import Fault
from fleetops.store import ConflictError, Store


@pytest.mark.parametrize("fault,action,owner", [
    ("gpu_oom", "rollback", "ml-platform"),
    ("storage_latency", "restore_storage", "storage-platform"),
    ("node_down", "restore_node", "compute-platform"),
    ("telemetry_outage", "restore_telemetry", "observability-platform"),
    ("inventory_drift", "reconcile_inventory", "compute-platform"),
    ("alert_storm", "rollback", "ml-platform"),
])
def test_full_fault_investigation_approved_fix_and_report(lab, fault, action, owner):
    lab.inject(fault)
    lab.probe(40)
    active = lab.incidents(active_only=True)
    assert len(active) == 1
    diagnosis = Investigator(Settings()).investigate(lab, active[0]["id"])
    assert diagnosis["diagnosis"]["action"] == action
    assert not diagnosis["diagnosis"]["abstained"]
    assert lab.incidents()[0]["owner"] == owner
    assert len(diagnosis["tool_trace"]) == 5
    result = lab.fix(diagnosis["proposal"]["id"], approved=True, actor="test-operator")
    assert result["verified"]
    assert not lab.incidents(active_only=True)
    assert lab.state["fault"] == Fault.HEALTHY
    report = lab.postmortem(active[0]["id"])
    assert "recovery_verified" in report
    assert "actor: test-operator" in report
    assert "synthetic" in report


def test_insufficient_evidence_abstains(lab):
    lab.inject("unknown")
    lab.probe(40)
    result = Investigator(Settings()).investigate(lab, lab.incidents()[0]["id"])
    assert result["diagnosis"]["abstained"]
    assert result["proposal"] is None
    assert lab.state["fault"] == "unknown"


def test_alert_storm_deduplicates(lab):
    lab.inject("alert_storm")
    lab.probe(40)
    assert len(lab.incidents()) == 1
    assert lab.incidents()[0]["alert_count"] >= 26


def test_concurrent_duplicate_alerts_create_one_incident(lab):
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: lab.emit_alert("same-signal", "Test alert", []), range(20)))
    assert len(lab.incidents()) == 1
    assert lab.incidents()[0]["alert_count"] == 20


def test_maintenance_suppresses_paging_without_excluding_failures(lab):
    lab.maintenance(30)
    lab.inject("gpu_oom")
    lab.probe(40)
    assert not lab.incidents()
    assert lab.slo()["availability"]["bad"] == 40
    lab.maintenance(0)
    lab.probe(40)
    assert len(lab.incidents()) == 1


def test_escalation_and_acknowledgment(lab):
    incident = lab.emit_alert("signal", "Test incident", [])
    lab.advance(301)
    assert lab.incidents()[0]["escalated"]
    lab.acknowledge(incident["id"], "operator")
    assert lab.incidents()[0]["status"] == "acknowledged"
    with pytest.raises(ConflictError):
        lab.acknowledge(incident["id"], "operator")


def test_budget_is_not_reset_by_recovery(lab):
    lab.inject("gpu_oom")
    lab.probe(40)
    result = Investigator(Settings()).investigate(lab, lab.incidents()[0]["id"])
    lab.fix(result["proposal"]["id"], approved=True, actor="operator")
    lab.probe(80)
    assert lab.slo()["availability"]["bad"] == 40
    assert lab.slo()["availability"]["status"] == "breached"
    assert not lab.incidents(active_only=True)


def test_fresh_failure_reopens_after_verified_recovery(lab):
    lab.inject("gpu_oom")
    lab.probe(40)
    first = lab.incidents()[0]["id"]
    result = Investigator(Settings()).investigate(lab, first)
    lab.fix(result["proposal"]["id"], approved=True, actor="operator")
    lab.probe(80)
    assert not lab.incidents(active_only=True)
    lab.inject("node_down")
    lab.probe(40)
    assert len(lab.incidents(active_only=True)) == 1
    assert lab.incidents(active_only=True)[0]["id"] != first


def test_missing_approval_and_actor_rejected(lab):
    with pytest.raises(ValueError, match="approval"):
        lab.fix("anything", approved=False, actor="operator")
    with pytest.raises(ValueError, match="operator"):
        lab.fix("anything", approved=True, actor="\n")


def test_stale_plan_and_double_execution_rejected(lab):
    lab.inject("gpu_oom")
    lab.probe(40)
    result = Investigator(Settings()).investigate(lab, lab.incidents()[0]["id"])
    plan_id = result["proposal"]["id"]
    lab.probe(10)
    with pytest.raises(ConflictError, match="stale"):
        lab.fix(plan_id, approved=True, actor="operator")
    fresh = Investigator(Settings()).investigate(lab, lab.incidents()[0]["id"])
    lab.fix(fresh["proposal"]["id"], approved=True, actor="operator")
    with pytest.raises(ConflictError):
        lab.fix(fresh["proposal"]["id"], approved=True, actor="operator")


def test_wrong_fix_does_not_falsely_resolve(lab):
    lab.inject("gpu_oom")
    lab.probe(40)
    incident = lab.incidents()[0]
    plan = lab.create_proposal(incident["id"], {"abstained": False, "action": "restore_storage", "hypotheses": []})
    result = lab.fix(plan["id"], approved=True, actor="operator")
    assert not result["verified"]
    assert lab.incidents()[0]["status"] == "mitigating"


def test_outbox_survives_restart_and_replays_once(tmp_path, telemetry):
    url = "sqlite:///" + str(tmp_path / "fleet.db")
    database = Store(url)
    lab = Lab(database, "persistent", telemetry)
    lab.inject("telemetry_outage")
    lab.probe(12)
    assert len(database.list("persistent", "outbox")) == 24
    database.close()
    database = Store(url)
    lab = Lab(database, "persistent", telemetry)
    assert lab.state["fault"] == "telemetry_outage"
    assert len(database.list("persistent", "outbox")) == 24
    assert database.drain_outbox("persistent") == 24
    assert database.drain_outbox("persistent") == 0
    database.close()


def test_outbox_is_bounded_and_reports_drops(lab, monkeypatch):
    import fleetops.lab as module
    monkeypatch.setattr(module, "QUEUE_LIMIT", 4)
    lab.inject("telemetry_outage")
    lab.probe(5)
    assert len(lab.store.list(lab.namespace, "outbox")) == 4
    assert b"fleetops_telemetry_dropped_total 6.0" in lab.telemetry.exposition()


def test_probe_budget_prevents_unbounded_demo_growth(lab):
    lab._save_state(probe_count=2000)
    with pytest.raises(ValueError, match="probe budget"):
        lab.probe(1)


def test_recovery_requires_remaining_verification_budget(lab):
    lab.inject("gpu_oom")
    lab.probe(40)
    report = Investigator(Settings()).investigate(lab, lab.incidents()[0]["id"])
    lab._save_state(probe_count=1990)
    with pytest.raises(ValueError, match="20 remaining"):
        lab.fix(report["proposal"]["id"], approved=True, actor="operator")
    assert lab.store.get(lab.namespace, "proposal", report["proposal"]["id"])["status"] == "awaiting_approval"


def test_unlisted_action_is_rejected_before_execution(lab):
    lab.inject("gpu_oom")
    lab.probe(40)
    plan = lab.create_proposal(lab.incidents()[0]["id"], {"abstained": False, "action": "execute_shell", "hypotheses": []})
    with pytest.raises(ValueError, match="allowlist"):
        lab.fix(plan["id"], approved=True, actor="operator")


def test_closed_incident_cannot_receive_a_new_proposal(lab):
    lab.inject("gpu_oom")
    lab.probe(40)
    report = Investigator(Settings()).investigate(lab, lab.incidents()[0]["id"])
    lab.fix(report["proposal"]["id"], approved=True, actor="operator")
    with pytest.raises(ConflictError):
        lab.create_proposal(report["incident_id"], report["diagnosis"])


@pytest.mark.parametrize("count", [0, -1, 501, True, 1.5])
def test_bad_probe_count(lab, count):
    with pytest.raises(ValueError):
        lab.probe(count)


def test_reset_clears_only_this_session(lab, store, telemetry):
    other = Lab(store, "other", telemetry)
    other.emit_alert("other", "Another incident", [])
    lab.inject("gpu_oom")
    lab.probe(40)
    lab.reset()
    assert not lab.incidents()
    assert lab.slo()["availability"]["sli"] == 1
    assert len(other.incidents()) == 1


@pytest.mark.parametrize("operation", ["healthy", "duplicate", "missing_report", "missing_ack", "missing_plan", "unknown_service", "foreign_evidence", "bad_maintenance", "bad_clock", "bad_text"])
def test_rejected_operations(lab, operation):
    with pytest.raises(ValueError):
        if operation == "healthy":
            lab.inject("healthy")
        elif operation == "duplicate":
            lab.emit_alert("x", "x", [])
            lab.inject("gpu_oom")
        elif operation == "missing_report":
            lab.postmortem("missing")
        elif operation == "missing_ack":
            lab.acknowledge("missing", "operator")
        elif operation == "missing_plan":
            lab.fix("missing", approved=True, actor="operator")
        elif operation == "unknown_service":
            lab.emit_alert("x", "x", [], service_id="missing")
        elif operation == "foreign_evidence":
            lab.emit_alert("x", "x", ["missing"])
        elif operation == "bad_maintenance":
            lab.maintenance(121)
        elif operation == "bad_clock":
            lab.advance(-1)
        elif operation == "bad_text":
            lab.probe(1, "")
