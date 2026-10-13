import pytest

from fleetops.models import AssetSnapshot


def snapshot(lab, **changes):
    base = {"id": "discovered-node", "name": "real-node", "kind": "node", "environment": "cloud",
            "owner": "compute-platform", "observed_at": lab.now, "source": "kubernetes", "simulated": False}
    return AssetSnapshot(**{**base, **changes})


def test_three_environments_and_dependencies(lab):
    assets = lab.inventory.all(lab.now)
    assert {a["environment"] for a in assets} == {"on-prem", "cloud", "partner"}
    assert len(assets) == 10
    catalog = lab.inventory.for_service("inference-api", lab.now)
    assert catalog["service"]["owner"] == "ml-platform"
    assert catalog["dependencies"] == ["artifact-store"]


def test_discovery_keeps_stable_id_and_increases_revision(lab):
    first = lab.inventory.reconcile(snapshot(lab), lab.now)
    second = lab.inventory.reconcile(snapshot(lab, observed_at=lab.now + 1), lab.now)
    assert first["status"] == "created"
    assert second["status"] == "updated"
    assert second["asset"]["_revision"] == 2


def test_old_snapshot_does_not_overwrite(lab):
    lab.inventory.reconcile(snapshot(lab), lab.now)
    result = lab.inventory.reconcile(snapshot(lab, observed_at=lab.now - 10, owner="wrong-team"), lab.now)
    assert result["status"] == "stale"
    assert result["asset"]["owner"] == "compute-platform"


def test_lower_priority_source_does_not_overwrite(lab):
    lab.inventory.reconcile(snapshot(lab, source="manual"), lab.now)
    result = lab.inventory.reconcile(snapshot(lab, source="seed", observed_at=lab.now + 1), lab.now)
    assert result["status"] == "rejected_priority"


def test_equal_time_conflicting_owner_is_flagged(lab):
    lab.inventory.reconcile(snapshot(lab), lab.now)
    result = lab.inventory.reconcile(snapshot(lab, owner="other-team"), lab.now)
    assert result["status"] == "conflict"
    assert len(lab.store.list(lab.namespace, "conflict")) == 1


def test_newer_conflict_records_provenance(lab):
    lab.inventory.reconcile(snapshot(lab), lab.now)
    result = lab.inventory.reconcile(snapshot(lab, observed_at=lab.now + 1, owner="other-team"), lab.now)
    assert result["asset"]["owner"] == "other-team"
    conflict = lab.store.list(lab.namespace, "conflict")[0]
    assert conflict["previous_owner"] == "compute-platform"


def test_blank_discovery_owner_preserves_existing_owner(lab):
    lab.inventory.reconcile(snapshot(lab), lab.now)
    result = lab.inventory.reconcile(snapshot(lab, observed_at=lab.now + 1, owner=""), lab.now)
    assert result["asset"]["owner"] == "compute-platform"


@pytest.mark.parametrize("changes", [{"parent_id": "missing"}, {"service_ids": ["missing"]}, {"observed_at": 1800000000}])
def test_invalid_references_and_future_timestamp(lab, changes):
    with pytest.raises(ValueError):
        lab.inventory.reconcile(snapshot(lab, **changes), lab.now)


def test_stale_and_unowned_flags(lab):
    lab.inventory.reconcile(snapshot(lab, owner="", observed_at=lab.now - 90000), lab.now)
    asset = next(a for a in lab.inventory.all(lab.now) if a["id"] == "discovered-node")
    assert asset["stale"] and asset["ownership_gap"]


def test_unknown_service_rejected(lab):
    with pytest.raises(ValueError):
        lab.inventory.for_service("missing", lab.now)


def test_namespace_isolation(store, telemetry, lab):
    from fleetops.lab import Lab
    other = Lab(store, "other-lab", telemetry)
    lab.inventory.reconcile(snapshot(lab), lab.now)
    assert all(a["id"] != "discovered-node" for a in other.inventory.all(other.now))
