import pytest

from fleetops.config import Settings
from fleetops.store import ConflictError, Store


def test_compare_and_swap_rejects_stale_update(store):
    record = store.put("a", "kind", {"id": "one", "timestamp": 1, "value": 1})
    store.put("a", "kind", {**record, "value": 2}, expected_revision=record["_revision"])
    with pytest.raises(ConflictError):
        store.put("a", "kind", {**record, "value": 3}, expected_revision=record["_revision"])


def test_list_time_filter_and_delete(store):
    store.put("a", "kind", {"id": "one", "timestamp": 1})
    store.put("a", "kind", {"id": "two", "timestamp": 10})
    assert len(store.list("a", "kind", since=5)) == 1
    store.delete("a", "kind", "two")
    assert store.get("a", "kind", "two") is None


def test_file_database_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "fleet.db"
    database = Store("sqlite:///" + str(path))
    assert path.exists()
    database.close()


def test_settings_load_environment_and_hide_secrets(monkeypatch):
    monkeypatch.setenv("FLEETOPS_API_TOKEN", "private-token")
    monkeypatch.setenv("FLEETOPS_AI_API_KEY", "private-model-key")
    settings = Settings.from_env()
    assert settings.api_token == "private-token"
    assert "private-token" not in repr(settings)
    assert "private-model-key" not in repr(settings)


@pytest.mark.parametrize("changes", [{"ai_mode": "invalid"}, {"ai_max_steps": 0}, {"ai_max_steps": 13}, {"ai_timeout": 0}, {"max_sessions": 0}, {"session_ttl_seconds": 0}, {"ai_mode": "live"}, {"ai_mode": "live", "ai_api_key": "test", "ai_model": "test", "ai_base_url": "http://insecure"}])
def test_invalid_server_configuration(changes):
    with pytest.raises(ValueError):
        Settings(**changes)


def test_session_capacity_and_expiry(monkeypatch):
    from fleetops.service import FleetOps
    service = FleetOps(Settings(database_url="sqlite:///:memory:", max_sessions=1, session_ttl_seconds=1))
    service.telemetry.logger.disabled = True
    first = service.new_session()
    with pytest.raises(ValueError, match="capacity"):
        service.new_session()
    touched = service.labs[first][1]
    monkeypatch.setattr("fleetops.service.time.monotonic", lambda: touched + 2)
    second = service.new_session()
    assert second != first
    assert first not in service.labs
    assert not service.store.get(first, "state", "lab")
    service.close()


def test_service_requires_active_incident(service):
    session = service.new_session()
    with pytest.raises(ValueError, match="active incident"):
        service.investigate(session)


@pytest.mark.parametrize("namespace", ["wrong", None, "../file"])
def test_invalid_session_identifiers(service, namespace):
    with pytest.raises(ValueError):
        service.session(namespace)
