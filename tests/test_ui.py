import json
import re

import pytest
from fastapi.testclient import TestClient

from fleetops.api import create_app
from fleetops.config import Settings
from fleetops.ui import Presenter, diagnosis_markdown, percentage


@pytest.mark.ui
def test_gradio_frontend_bundles_load_without_static_asset_route_collision():
    app = create_app(Settings(database_url="sqlite:///:memory:"))
    app.state.service.telemetry.logger.disabled = True
    with TestClient(app) as client:
        document = client.get("/").text
        bundles = re.findall(r'(?:src|href)="(\./assets/[^"?]+\.(?:js|css))"', document)
        assert len(bundles) >= 2, "The actual frontend JS and CSS must be discovered"
        for path in bundles:
            response = client.get(path.removeprefix("."))
            assert response.status_code == 200, path
            assert len(response.content) > 100
        assert client.get("/fleetops-assets/architecture.svg").status_code == 200


@pytest.mark.ui
def test_gradio_mount_components_and_no_secret_exposure():
    app = create_app(Settings(database_url="sqlite:///:memory:", api_token="private-operator-token", ai_api_key="private-key"))
    app.state.service.telemetry.logger.disabled = True
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        config = client.get("/config").json()
        serialized = json.dumps(config)
        assert "private-operator-token" not in serialized
        assert "private-key" not in serialized
        assert "Fleet inventory" in serialized
        assert "Architecture" in serialized
        assert "I reviewed the evidence" in serialized
        assert config["enable_queue"]
        assert all(dep.get("api_visibility") == "private" for dep in config["dependencies"] if dep.get("api_name") != "lambda")


def test_presenter_end_to_end_updates_all_views(service):
    presenter = Presenter(service)
    namespace = service.new_session()
    assert len(presenter.initialize(namespace)) == 9
    assert len(presenter.inject(namespace, "gpu_oom")) == 9
    assert len(presenter.probe(namespace, 40)) == 9
    investigation = presenter.investigate(namespace)
    assert len(investigation) == 13
    proposal_id = investigation[3]
    assert proposal_id
    rejected = presenter.fix(namespace, proposal_id, False, "operator")
    assert "approval" in rejected[0]
    fixed = presenter.fix(namespace, proposal_id, True, "operator")
    assert "verified" in fixed[0]
    assert len(presenter.probe(namespace, 80)) == 9
    assert len(presenter.reset(namespace)) == 9


def test_presenter_empty_incident_and_conflicting_drill(service):
    presenter = Presenter(service)
    namespace = service.new_session()
    assert "active incident" in presenter.investigate(namespace)[0]
    presenter.inject(namespace, "node_down")
    presenter.probe(namespace, 40)
    assert "Finish or reset" in presenter.inject(namespace, "gpu_oom")[0]


def test_presenter_maintenance_and_buffer_recovery(service):
    presenter = Presenter(service)
    namespace = service.new_session()
    assert "Maintenance" in presenter.maintenance(namespace, True)[0]
    presenter.maintenance(namespace, False)
    presenter.inject(namespace, "telemetry_outage")
    presenter.probe(namespace, 40)
    report = presenter.investigate(namespace)
    assert "Replayed" in presenter.fix(namespace, report[3], True, "operator")[0]


def test_abstention_display_and_no_data_percentage(service):
    presenter = Presenter(service)
    namespace = service.new_session()
    presenter.inject(namespace, "unknown")
    presenter.probe(namespace, 40)
    result = service.investigate(namespace)
    assert "Abstained" in diagnosis_markdown(result)
    assert percentage(None) == "No data"


def test_ui_approval_is_reset_per_plan_and_used_plan_is_disabled(service):
    presenter = Presenter(service)
    namespace = service.new_session()
    presenter.inject(namespace, "gpu_oom")
    presenter.probe(namespace, 40)
    result = presenter.investigate_ui(namespace)
    assert len(result) == 15
    assert result[4] is False
    assert result[5]["interactive"]
    fixed = presenter.fix_ui(namespace, result[3], True, "operator")
    assert len(fixed) == 12
    assert fixed[0]["status"] == "executed"
    assert fixed[1] == ""
    assert not fixed[2]["interactive"]
    presenter.probe(namespace, 80)
    assert not service.session(namespace).incidents(active_only=True)
    reset = presenter.reset_ui(namespace)
    assert len(reset) == 16
    assert reset[2] == {} and reset[3] == "" and reset[4] is False


def test_ui_probe_budget_and_failed_fix_are_visible(service):
    presenter = Presenter(service)
    namespace = service.new_session()
    presenter.inject(namespace, "gpu_oom")
    presenter.probe(namespace, 40)
    lab = service.session(namespace)
    plan = lab.create_proposal(lab.incidents()[0]["id"], {"abstained": False, "action": "restore_storage", "hypotheses": []})
    assert "Verification failed" in presenter.fix(namespace, plan["id"], True, "operator")[0]
    lab._save_state(probe_count=2000)
    assert "probe budget" in presenter.probe(namespace, 40)[0]
