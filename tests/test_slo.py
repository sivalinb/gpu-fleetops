import pytest

from fleetops.slo import AVAILABILITY, LATENCY, Objective, burn_alert, evaluate, report, window


def row(status=200, latency=100, timestamp=1000):
    return {"status": status, "latency_ms": latency, "timestamp": timestamp}


@pytest.mark.parametrize("objective", [AVAILABILITY, LATENCY])
def test_no_traffic_is_no_data(objective):
    result = evaluate([], objective)
    assert result["sli"] is None
    assert result["burn_rate"] is None
    assert result["remaining_budget_percent"] is None
    assert result["status"] == "no_data"


def test_success_and_failure_denominator():
    result = evaluate([row(), row(503), row()], AVAILABILITY)
    assert result["sli"] == pytest.approx(2 / 3)
    assert result["bad"] == 1
    assert result["status"] == "breached"


def test_latency_counts_failed_requests_even_if_fast():
    result = evaluate([row(latency=300), row(latency=301), row(503, 1)], LATENCY)
    assert result["good"] == 1
    assert result["total"] == 3


def test_budget_can_be_negative_after_overspend():
    result = evaluate([row(503)] * 100, AVAILABILITY)
    assert result["allowed_bad"] == pytest.approx(.5)
    assert result["remaining_budget_percent"] < 0
    assert result["burn_rate"] == pytest.approx(200)


def test_exact_target_meets_objective():
    result = evaluate([row()] * 199 + [row(503)], AVAILABILITY)
    assert result["sli"] == .995
    assert result["status"] == "meeting"


@pytest.mark.parametrize("target", [0, 1, -.1, 2, float("nan")])
def test_invalid_target_rejected(target):
    with pytest.raises(ValueError):
        Objective("bad", target)


@pytest.mark.parametrize("latency", [0, -1, float("nan"), float("inf")])
def test_invalid_latency_rejected(latency):
    with pytest.raises(ValueError):
        Objective("bad", .99, latency)


def test_window_excludes_future_and_expired_samples():
    rows = [row(timestamp=0), row(timestamp=100), row(timestamp=200), row(timestamp=201)]
    assert [r["timestamp"] for r in window(rows, 200, 100)] == [100, 200]


def test_rolling_30_day_window():
    now = 3000000
    result = report([row(503, timestamp=now - 31 * 86400), row(timestamp=now)], now)
    assert result["availability"]["sli"] == 1


def test_fast_burn_requires_both_windows_and_samples():
    result = burn_alert([row(503, timestamp=1000)] * 25, 1000, AVAILABILITY)
    assert result["windows"]["fast"]["firing"]
    assert result["firing"]
    assert not burn_alert([row(503)] * 5, 1000, AVAILABILITY)["firing"]


def test_old_failures_do_not_keep_fast_page_firing():
    rows = [row(503, timestamp=600)] * 40 + [row(timestamp=1000)] * 50
    result = burn_alert(rows, 1000, AVAILABILITY)
    assert not result["windows"]["fast"]["firing"]


def test_slow_burn_pair_fires_without_fast_pair():
    rows = [row(503, timestamp=600)] * 40 + [row(timestamp=1000)] * 50
    assert burn_alert(rows, 1000, AVAILABILITY)["windows"]["slow"]["firing"]
