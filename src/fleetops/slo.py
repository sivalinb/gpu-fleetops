"""Request-based SLOs, budgets, and paired-window burn-rate detection."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Objective:
    name: str
    target: float
    latency_ms: float | None = None

    def __post_init__(self):
        if not 0 < self.target < 1:
            raise ValueError("SLO target must be between zero and one")
        if self.latency_ms is not None and (not isfinite(self.latency_ms) or self.latency_ms <= 0):
            raise ValueError("Latency threshold must be finite and positive")


AVAILABILITY = Objective("availability", 0.995)
LATENCY = Objective("latency", 0.99, 300.0)
OBJECTIVES = (AVAILABILITY, LATENCY)
WINDOW_SECONDS = 30 * 24 * 3600


def is_good(row: dict, objective: Objective) -> bool:
    success = 200 <= row["status"] < 400
    return success and (objective.latency_ms is None or row["latency_ms"] <= objective.latency_ms)


def evaluate(rows: list[dict], objective: Objective) -> dict:
    total = len(rows)
    bad = sum(not is_good(row, objective) for row in rows)
    allowed = total * (1 - objective.target)
    return {
        "name": objective.name, "target": objective.target,
        "total": total, "good": total - bad, "bad": bad,
        "sli": (total - bad) / total if total else None,
        "allowed_bad": allowed,
        "remaining_budget_percent": 100 * (1 - bad / allowed) if total else None,
        "burn_rate": bad / allowed if total else None,
        "status": "no_data" if not total else "meeting" if bad <= allowed else "breached",
    }


def window(rows: list[dict], now: float, seconds: int) -> list[dict]:
    return [row for row in rows if now - seconds <= row["timestamp"] <= now]


def report(rows: list[dict], now: float) -> dict:
    return {obj.name: evaluate(window(rows, now, WINDOW_SECONDS), obj) for obj in OBJECTIVES}


def burn_alert(rows: list[dict], now: float, objective: Objective) -> dict:
    """A 30-day objective: fast page (1h + 5m), slow page (6h + 30m).

    A minimum sample count prevents a single demo request causing a page. Low
    traffic needs a complementary synthetic-probe policy in a real deployment.
    """
    measured = {}
    for name, long_s, short_s, threshold in [("fast", 3600, 300, 14.4), ("slow", 21600, 1800, 6.0)]:
        long = evaluate(window(rows, now, long_s), objective)
        short = evaluate(window(rows, now, short_s), objective)
        eligible = long["total"] >= 20 and short["total"] >= 10
        firing = eligible and long["burn_rate"] >= threshold and short["burn_rate"] >= threshold
        measured[name] = {"firing": firing, "threshold": threshold, "long": long, "short": short}
    return {"firing": any(pair["firing"] for pair in measured.values()), "windows": measured}
