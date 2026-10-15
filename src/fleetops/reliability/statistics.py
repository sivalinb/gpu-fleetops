"""Explicit estimands: interruption intensity, first-event survival, and censored MLE."""

import math
import warnings

import numpy as np
from scipy.stats import CensoredData, chi2, weibull_min


def rate(count: int, exposure: float) -> dict:
    if count < 0 or not math.isfinite(exposure) or exposure < 0:
        raise ValueError("Count and exposure must be nonnegative and finite")
    if exposure == 0:
        return dict(
            status="no_data",
            interruptions=count,
            operating_hours=0,
            per_1000_hours=None,
            rate_ci95=None,
            mtbi_hours=None,
            mtbi_ci95=None,
        )
    low = float(chi2.ppf(0.025, 2 * count) / 2 / exposure) if count else 0.0
    high = float(chi2.ppf(0.975, 2 * (count + 1)) / 2 / exposure)
    return dict(
        status="observed" if count else "zero_observed_interruptions",
        interruptions=count,
        operating_hours=round(exposure, 6),
        per_1000_hours=1000 * count / exposure,
        rate_ci95=[1000 * low, 1000 * high],
        mtbi_hours=exposure / count if count else None,
        mtbi_ci95=[1 / high, 1 / low if low else None],
        assumption="Poisson independent episodes, constant intensity; correlated rack failures violate this assumption",
    )


def kaplan_meier(observations: list[tuple[float, bool]]) -> list[dict]:
    """Failures occur before censoring at a tied time. Times are observed at-risk hours."""
    if not observations:
        return []
    if any(t < 0 or not math.isfinite(t) for t, _ in observations):
        raise ValueError("Survival times must be finite and nonnegative")
    n = len(observations)
    survival, greenwood = 1.0, 0.0
    rows = [dict(hours=0.0, survival=1.0, lower=1.0, upper=1.0, at_risk=n, failures=0, censored=0)]
    grouped = {}
    for time, failed in observations:
        bucket = grouped.setdefault(time, [0, 0])
        bucket[0 if failed else 1] += 1
    for time, (d, c) in sorted(grouped.items()):
        survival *= 1 - d / n
        if d and n > d:
            greenwood += d / (n * (n - d))
        if 0 < survival < 1:
            spread = 1.96 * math.sqrt(greenwood) / abs(math.log(survival))
            loglog = math.log(-math.log(survival))
            lower = math.exp(-math.exp(min(700, loglog + spread)))
            upper = math.exp(-math.exp(max(-700, loglog - spread)))
        else:
            lower = upper = survival
        rows.append(
            dict(
                hours=float(time),
                survival=survival,
                lower=lower,
                upper=upper,
                at_risk=n,
                failures=d,
                censored=c,
            )
        )
        n -= d + c
    return rows


def weibull(observations: list[tuple[float, bool]]) -> dict:
    failed = [t for t, f in observations if f and t > 0]
    censored = [t for t, f in observations if not f and t > 0]
    if len(failed) < 8 or len(set(failed)) < 4 or any(t <= 0 for t, _ in observations):
        return dict(
            status="insufficient_data",
            failures=len(failed),
            reason="Need ≥8 positive failures and ≥4 distinct failure times",
        )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        shape, _, scale = weibull_min.fit(CensoredData(uncensored=failed, right=censored), floc=0)
    if not np.isfinite([shape, scale]).all() or shape <= 0 or scale <= 0:
        return dict(status="fit_failed")
    km = kaplan_meier(observations)
    residual = max(
        abs(row["survival"] - float(weibull_min.sf(row["hours"], shape, scale=scale)))
        for row in km
        if row["at_risk"] >= max(5, len(observations) // 10)
    )
    return dict(
        status="descriptive_fit",
        shape=float(shape),
        scale_hours=float(scale),
        failures=len(failed),
        right_censored=len(censored),
        km_max_abs_gap=residual,
        review_required=bool(caught) or residual > 0.12,
        interpretation="First-interruption fit, not recurrent MTBI; inspect cohort homogeneity and censoring assumptions",
    )


def rate_ratio(a_count: int, a_hours: float, b_count: int, b_hours: float) -> dict:
    if min(a_count, b_count) <= 0 or min(a_hours, b_hours) <= 0:
        return dict(ratio=None, ci95=None, status="insufficient_events")
    ratio = (a_count / a_hours) / (b_count / b_hours)
    spread = 1.96 * math.sqrt(1 / a_count + 1 / b_count)
    return dict(
        ratio=ratio,
        ci95=[ratio * math.exp(-spread), ratio * math.exp(spread)],
        status="approximate",
        assumption="Independent Poisson counts; exploratory, no multiple-comparison correction",
    )
