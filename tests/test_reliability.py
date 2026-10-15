import json
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fleetops.api import create_app
from fleetops.config import Settings
from fleetops.reliability.adapters import encode, normalize
from fleetops.reliability.analysis import analyze, compare_drivers, episodes
from fleetops.reliability.cli import main
from fleetops.reliability.contracts import Dataset, Entity, Event, Interval
from fleetops.reliability.prediction import evaluate_prediction, score
from fleetops.reliability.readiness import Check, assess, parse_dcgm, run_local, sample_evidence
from fleetops.reliability.reporting import evaluate_classification, save_bundle
from fleetops.reliability.simulation import controlled_experiment, simulate
from fleetops.reliability.statistics import kaplan_meier, rate, rate_ratio, weibull
from fleetops.reliability.views import render


def entity(**changes):
    return Entity(id="gpu-1", provider="provider", rack="rack", node="node", stop=10, **changes)


def event(**changes):
    values = dict(
        id="e1",
        entity_id="gpu-1",
        incident_key="i1",
        start=2,
        stop=3,
        domain="software",
        signal="LAB_INTERRUPT",
        interrupted=True,
        origin="synthetic",
    )
    return Event(**(values | changes))


def test_overlap_and_duplicate_logs_are_one_gpu_interruption():
    first = event(stop=5)
    second = event(id="e2", incident_key="i2", start=3, stop=6, domain="memory")
    result = analyze(Dataset(entities=[entity()], events=[first, first, second]))
    assert result["summary"]["interruptions"] == 1
    assert result["summary"]["unique_incidents"] == 2
    assert result["summary"]["operating_hours"] == 6
    assert sum(p["lost_hours"] for p in result["pareto"]) == 4
    assert result["episodes"][0]["domain"] == "unknown"


def test_maintenance_unknown_and_warning_do_not_become_healthy_exposure():
    gpu = entity(
        exclusions=[
            Interval(start=2, stop=4, state="maintenance"),
            Interval(start=6, stop=8, state="unknown"),
        ]
    )
    result = analyze(
        Dataset(
            entities=[gpu],
            events=[
                event(),
                event(id="e2", incident_key="i2", start=5, stop=7),
                event(id="warning", start=8, stop=9, interrupted=False),
            ],
        )
    )
    assert result["summary"]["interruptions"] == 1
    assert result["summary"]["operating_hours"] == 5
    assert result["summary"]["unknown_hours"] == 2
    assert result["entity_metrics"][0]["survival_hours"] == 3


def test_unknown_gap_censors_survival_before_later_failure():
    gpu = entity(exclusions=[Interval(start=4, stop=5, state="unknown")])
    result = analyze(Dataset(entities=[gpu], events=[event(start=7, stop=8)]))
    assert result["summary"]["interruptions"] == 1
    assert not result["entity_metrics"][0]["failed"]
    assert result["entity_metrics"][0]["survival_hours"] == 4


def test_disconnected_reused_incident_id_does_not_collapse_outages():
    assert (
        len(
            episodes(
                Dataset(entities=[entity()], events=[event(), event(id="e2", start=7, stop=8)])
            )
        )
        == 2
    )


@pytest.mark.parametrize("unit", ["gpu", "node", "job"])
def test_units_require_explicit_entity_exposure(unit):
    data = Dataset(entities=[entity(unit=unit)], events=[event()])
    assert analyze(data, unit)["summary"]["operating_hours"] == 9
    other = "node" if unit == "gpu" else "gpu"
    assert analyze(data, other)["summary"]["status"] == "no_data"


@pytest.mark.parametrize(
    "mutation", ["unknown_entity", "conflicting_id", "outside_window", "duplicate_entity"]
)
def test_invalid_relationships_fail_closed(mutation):
    values = dict(entities=[entity()], events=[event()])
    if mutation == "unknown_entity":
        values["events"] = [event(entity_id="absent")]
    elif mutation == "conflicting_id":
        values["events"].append(event(start=4, stop=5))
    elif mutation == "outside_window":
        values["events"] = [event(stop=11)]
    else:
        values["entities"].append(entity())
    with pytest.raises(ValidationError):
        Dataset(**values)


@pytest.mark.parametrize("provider", ["csp-aurora", "csp-borealis", "csp-cirrus"])
def test_provider_contract_units_round_trip(provider):
    source = event(start=2.75, stop=3.5)
    assert normalize(provider, encode(provider, source)) == source


def test_unknown_provider_and_impact_rejected():
    with pytest.raises(ValueError):
        normalize("real-provider", {})
    row = encode("csp-borealis", event())
    row["impact"] = "maybe"
    with pytest.raises(ValueError):
        normalize("csp-borealis", row)


def test_zero_failures_have_finite_upper_bound_and_no_infinite_mtbi():
    result = rate(0, 100)
    assert result["mtbi_hours"] is None
    assert result["rate_ci95"][1] == pytest.approx(36.8887945)
    assert result["mtbi_ci95"][1] is None
    assert rate(0, 0)["status"] == "no_data"
    with pytest.raises(ValueError):
        rate(2, float("nan"))


def test_km_tied_failure_and_censor_hand_calculation():
    rows = kaplan_meier([(1, True), (1, False), (2, True), (3, False)])
    assert rows[1]["at_risk"] == 4
    assert rows[1]["survival"] == 0.75
    assert rows[2]["survival"] == 0.375
    assert all(0 <= r["lower"] <= r["survival"] <= r["upper"] <= 1 for r in rows)
    assert kaplan_meier([(1, True)])[-1]["survival"] == 0
    assert kaplan_meier([]) == []


def test_censored_weibull_recovers_known_parameters():
    rng = np.random.default_rng(42)
    raw = rng.weibull(2, 2500) * 100
    result = weibull([(min(float(t), 100), bool(t < 100)) for t in raw])
    assert result["shape"] == pytest.approx(2, rel=0.08)
    assert result["scale_hours"] == pytest.approx(100, rel=0.06)
    assert result["right_censored"] > 500
    assert weibull([(10, False)] * 20)["status"] == "insufficient_data"
    assert rate_ratio(0, 10, 1, 10)["status"] == "insufficient_events"


def test_matching_refuses_nonoverlapping_cohorts():
    rows = [
        dict(
            provider="a",
            rack="r",
            model="m",
            firmware="f",
            workload="train",
            age_band="new",
            driver="candidate",
            interruptions=3,
            operating_hours=100,
        )
    ]
    assert compare_drivers(rows)["status"] == "no_common_support"


def test_common_stratum_weights_remove_simpson_paradox():
    rows = []
    for workload, counts in [("easy", [(90, 9000), (2, 100)]), ("hard", [(10, 100), (1800, 9000)])]:
        for driver, (count, hours) in zip(("stable", "candidate"), counts, strict=True):
            rows.append(
                dict(
                    provider="a",
                    rack="r",
                    model="m",
                    firmware="f",
                    workload=workload,
                    age_band="new",
                    driver=driver,
                    interruptions=count,
                    operating_hours=hours,
                )
            )
    assert compare_drivers(rows)["standardized_ratio"] == pytest.approx(2)


def test_replay_identifies_patterns_without_reading_truth():
    data, _ = simulate()
    result = analyze(data)
    actual = {p["domain"]: p["classification"] for p in result["patterns"]}
    assert actual["software"] == "systemic_candidate"
    assert actual["thermal"] == "environmental_candidate"
    assert actual["interconnect"] == "configuration_candidate"
    assert sum(p["lost_hours"] for p in result["pareto"]) == pytest.approx(
        result["summary"]["lost_hours"]
    )
    assert data == simulate()[0]
    assert data != simulate(2027)[0]
    assert controlled_experiment()["acceptance"]["passed"]


def test_prediction_no_device_or_future_leakage_and_errors_visible():
    result = evaluate_prediction()
    assert result["split"]["device_overlap"] == 0
    assert result["split"]["test_days"][0] > result["split"]["validation_days"][1]
    for method in ("rules", "logistic"):
        metrics = result[method]
        assert sum(metrics[k] for k in ("tp", "fp", "fn", "tn")) == result["split"]["test"]
        assert metrics["fp"] > 0 and metrics["fn"] > 0
        assert 0.5 <= metrics["median_warning_hours"] <= 6
    empty = score(np.array([False]), np.array([0.0]), 0.5, [None])
    assert empty["precision"] is None and empty["roc_auc"] is None


@pytest.mark.parametrize(
    "case,status", [("pass", "pass"), ("fail", "fail"), ("incomplete", "insufficient_data")]
)
def test_readiness_evidence_and_missing_data(case, status):
    result = assess(sample_evidence(case))
    assert result["status"] == status
    assert not result["physical_gpu_validated"]


def test_unknown_schema_and_skips_cannot_pass():
    assert parse_dcgm({"new_schema": []}) == []
    evidence = sample_evidence().model_copy(
        update={"checks": [Check(name="memory", result="skip")]}
    )
    assert assess(evidence)["status"] == "insufficient_data"
    doc = {
        "DCGM GPU Diagnostic": {
            "test_categories": [
                {
                    "category": "Deployment",
                    "tests": [{"name": "NVML", "results": [{"status": "Pass"}]}],
                }
            ]
        }
    }
    assert Check(name="software", result="pass") in parse_dcgm(doc)
    assert parse_dcgm({"runtime_error": "failed"})[0].result == "fail"


def test_live_runner_explicit_intent_and_missing_tool(tmp_path):
    with pytest.raises(ValueError):
        run_local(tmp_path)
    with patch("fleetops.reliability.readiness.shutil.which", return_value=None):
        result = run_local(tmp_path, execute=True, idle_confirmed=True)
    assert result["status"] == "unavailable"
    assert (tmp_path / "live-attempt.json").exists()


def test_exports_figures_and_cli_calculate_outputs(tmp_path, monkeypatch, capsys):
    bundle = save_bundle(tmp_path, assets=100)
    assert "Unknown coverage" in (tmp_path / "TECHNICAL_REVIEW.md").read_text()
    assert "synthetic" in (tmp_path / "EXECUTIVE_BRIEF.md").read_text()
    assert (
        json.loads((tmp_path / "bundle.json").read_text())["analysis"]["summary"]["entities"] == 100
    )
    assert len(render(bundle)) == 9
    assert evaluate_classification(range(2040, 2042))["total"] == 8
    data, _ = simulate(2026, 60)
    source = tmp_path / "input.json"
    source.write_text(data.model_dump_json())
    output = tmp_path / "analysis.json"
    monkeypatch.setattr(
        "sys.argv", ["reliability", "analyze", str(source), "--output", str(output)]
    )
    main()
    assert json.loads(output.read_text())["summary"]["entities"] == 60
    capsys.readouterr()


@pytest.mark.integration
def test_authenticated_api_persists_isolated_reports_and_metrics():
    app = create_app(
        Settings(database_url="sqlite:///:memory:", api_token="test-token"), mount_ui=False
    )
    app.state.service.telemetry.logger.disabled = True
    auth = {"Authorization": "Bearer test-token"}
    with TestClient(app) as client:
        assert client.post("/api/v1/reliability/replay", json={}).status_code in (401, 422)
        one = client.post("/api/v1/sessions", headers=auth).json()["session_id"]
        two = client.post("/api/v1/sessions", headers=auth).json()["session_id"]
        headers = auth | {"X-FleetOps-Session": one}
        response = client.post("/api/v1/reliability/replay", headers=headers, json={"assets": 100})
        assert response.status_code == 200
        assert response.json()["analysis"]["summary"]["entities"] == 100
        assert client.get("/api/v1/reliability/latest", headers=headers).status_code == 200
        assert (
            client.get(
                "/api/v1/reliability/latest", headers=auth | {"X-FleetOps-Session": two}
            ).status_code
            == 404
        )
        assert (
            "Controlled follow-up" in client.get("/api/v1/reliability/review", headers=headers).text
        )
        assert (
            client.post(
                "/api/v1/reliability/replay", headers=headers, json={"assets": 10000}
            ).status_code
            == 422
        )
        result = client.post(
            "/api/v1/reliability/readiness",
            headers=headers,
            json=sample_evidence("incomplete").model_dump(),
        )
        assert result.json()["status"] == "insufficient_data"
        assert "fleetops_reliability_runs_total" in client.get("/metrics").text


def test_live_runner_retains_raw_evidence_and_requires_identity(tmp_path):
    from subprocess import CompletedProcess

    raw = json.dumps(
        {
            "DCGM GPU Diagnostic": {
                "test_categories": [
                    {
                        "category": "tests",
                        "tests": [
                            {"name": name, "results": [{"status": "Pass"}]}
                            for name in ["software", "memory", "targeted_stress"]
                        ],
                    }
                ]
            }
        }
    )
    responses = [
        CompletedProcess([], 0, raw, ""),
        CompletedProcess([], 0, "GPU-UUID, driver-1\n", ""),
        CompletedProcess([], 0, "DCGM version fixture", ""),
    ]
    with (
        patch("fleetops.reliability.readiness.shutil.which", return_value="/fixture/dcgmi"),
        patch("fleetops.reliability.readiness.subprocess.run", side_effect=responses) as runner,
        patch("fleetops.reliability.readiness.monotonic", side_effect=[0, 180]),
    ):
        report = run_local(tmp_path, execute=True, idle_confirmed=True)
    assert report["status"] == "pass" and report["physical_gpu_validated"]
    assert (tmp_path / "dcgm-stdout.json").read_text() == raw
    assert report["evidence"]["raw_sha256"]
    assert runner.call_args_list[0].args[0] == [
        "/fixture/dcgmi",
        "diag",
        "--run",
        "3",
        "--entity-id",
        "gpu:0",
        "--json",
    ]
    assert runner.call_args_list[0].kwargs.get("shell", False) is False
    incomplete = sample_evidence().model_copy(update={"origin": "live", "driver_version": ""})
    assert assess(incomplete)["status"] == "insufficient_data"


def test_live_timeout_and_unknown_output_cannot_be_certified(tmp_path):
    from subprocess import TimeoutExpired

    with (
        patch("fleetops.reliability.readiness.shutil.which", return_value="/fixture/dcgmi"),
        patch(
            "fleetops.reliability.readiness.subprocess.run", side_effect=TimeoutExpired("dcgmi", 1)
        ),
        patch("fleetops.reliability.readiness.monotonic", side_effect=[0, 1]),
    ):
        report = run_local(tmp_path, execute=True, idle_confirmed=True)
    assert report["status"] == "fail"
    assert not report["physical_gpu_validated"]
    assert "timed out" in (tmp_path / "dcgm-stderr.txt").read_text()
