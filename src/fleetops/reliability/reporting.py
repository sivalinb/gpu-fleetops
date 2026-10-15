"""Reproducible evidence bundles, executive briefs and technical reviews."""

import hashlib
import json
import platform
from pathlib import Path
from time import perf_counter

from .analysis import analyze
from .prediction import evaluate_prediction
from .readiness import assess, sample_evidence
from .simulation import controlled_experiment, simulate


def technical_report(bundle: dict) -> str:
    analysis = bundle["analysis"]
    s, experiment = analysis["summary"], bundle.get("experiment")
    lines = [
        "# GPU Fleet Reliability Intelligence",
        "",
        "Evidence origin: **synthetic controlled lab**.",
        "",
        "## Measurement",
        "",
        f"- Unit: {s['unit']}; observed entities: {s['entities']:,}",
        f"- Source records: {s['raw_records']:,}; interruption episodes: {s['interruptions']:,}; shared incidents: {s['unique_incidents']:,}",
        f"- Operating exposure: {s['operating_hours']:,.2f} {s['unit']}-hours",
        f"- Lost observed time: {s['lost_hours']:,.2f} {s['unit']}-hours",
        f"- Unknown coverage: {s['unknown_hours']:,.2f} {s['unit']}-hours",
        f"- Interruption intensity: {s['per_1000_hours']:.3f} / 1,000 operating hours"
        if s["per_1000_hours"] is not None
        else "- No operating exposure: rate and MTBI unavailable",
        "",
        "## Competing hypotheses",
        "",
    ]
    for p in analysis["patterns"]:
        lines += [
            f"- **{p['domain']} / {p['classification']}**: {p['explanation']}. Episodes: {p['episodes']}. Evidence: "
            + ", ".join(p["evidence_ids"][:3])
        ]
    lines += [
        "",
        "These classifications prioritize investigations. They do not establish causation.",
        "",
        "## Statistical review",
        "",
        "Matched driver comparisons condition on provider, rack, model, firmware/configuration, workload and age band. Unmatched strata are excluded.",
        f"Common strata: {analysis['driver_comparison']['matched_strata']}.",
        "",
        "Kaplan–Meier measures observed operating time to FIRST interruption. Unknown coverage right-censors a device at the start of its first gap. Maintenance pauses the exposure clock.",
        "",
        f"Weibull output: `{json.dumps(analysis['weibull'], sort_keys=True)}`",
        "",
        "Pooled cohorts may violate the Weibull assumptions. The KM gap is a descriptive diagnostic, not a goodness-of-fit test.",
    ]
    if experiment:
        reduction = experiment["relative_rate_reduction"]
        lines += [
            "",
            "## Controlled follow-up",
            "",
            experiment["method"],
            "",
            f"Concurrent canary/control rate ratio: {experiment['contemporaneous_canary_to_control']['ratio']}; approximate 95% CI: {experiment['contemporaneous_canary_to_control']['ci95']}.",
            f"Relative reduction: {100 * reduction:.1f}%."
            if reduction is not None
            else "Insufficient events to estimate a reduction.",
            f"Predeclared demonstration criteria passed: {experiment['acceptance']['passed']}.",
            "Acceptance requires ≥30% relative reduction and an approximate rate-ratio upper confidence bound below one. The synthetic generator creates the intervention effect.",
        ]
    if "prediction" in bundle:
        prediction = bundle["prediction"]
        lines += [
            "",
            "## Held-out prediction benchmark",
            "",
            prediction["preprocessing"],
            f"Split: `{json.dumps(prediction['split'])}`",
            "",
            "| Method | Precision | Recall | False alerts / 1,000 h | Median warning h |",
            "|---|---:|---:|---:|---:|",
        ]
        for name in ("rules", "logistic"):
            m = prediction[name]
            lines += [
                f"| {name} | {m['precision']} | {m['recall']} | {m['false_alerts_per_1000_operating_hours']:.2f} | {m['median_warning_hours']} |"
            ]
    lines += [
        "",
        "## Readiness and boundaries",
        "",
        "The authored readiness fixtures exercise pass, fail and insufficient-data decisions. No physical NVIDIA GPU or customer fleet was available for this recorded run.",
        "Live collection and the opt-in DCGM runner require supported operator-owned hardware. Unknown schemas, missing versions, skipped tests, short duration or insufficient coverage cannot pass.",
        "",
        "## Engineering priorities",
        "",
        "1. Reproduce the candidate-driver pattern on a supported isolated GPU or cluster.",
        "2. Inspect the affected rack's cooling and power records; keep this separate from the driver investigation.",
        "3. Run a controlled fabric-configuration comparison with equal workload and placement.",
        "4. Gather real failure labels before deploying predictive health decisions.",
        "",
        "## Limits",
        "",
        *["- " + s for s in analysis["limitations"]],
        "- Synthetic scale is logical record count, not physical fleet operation.",
        "- No independent operator or CSP review has been completed. Use REVIEW.md to record an actual review.",
        "",
    ]
    return "\n".join(lines)


def executive_report(bundle: dict) -> str:
    s, e = bundle["analysis"]["summary"], bundle["experiment"]
    reduction = e["relative_rate_reduction"]
    return "\n".join(
        [
            "# Fleet reliability review — executive brief",
            "",
            "**Scope: synthetic portfolio experiment; no customer or physical-GPU reliability claim.**",
            "",
            f"The replay covers {s['entities']:,} logical GPUs and {s['operating_hours']:,.0f} operating GPU-hours. It contains {s['interruptions']} interruption episodes and {s['lost_hours']:,.1f} lost GPU-hours.",
            "",
            "The analysis prioritizes three separate investigations: a shared driver pattern, a local cooling incident, and a fabric-configuration cohort. A matched comparison reduces measured workload and placement differences; remaining uncertainty is explicit.",
            "",
            f"A randomized synthetic canary/control follow-up measured a {100 * reduction:.1f}% lower canary interruption rate."
            if reduction is not None
            else "The follow-up has insufficient events to estimate improvement.",
            "This demonstrates the evaluation method. Real effectiveness requires a hardware trial and customer validation.",
            "",
            "**Decision requested:** authorize an isolated reproduction and a limited canary after readiness checks; do not promote from replay results alone.",
            "",
            "**Acceptance:** predefined interruption-rate reduction, enough observation exposure, no new hardware errors, and an agreed rollback criterion.",
            "",
        ]
    )


def build_bundle(seed: int = 2026, assets: int = 1000) -> dict:
    started = perf_counter()
    data, truth = simulate(seed, assets)
    analysis = analyze(data)
    bundle = dict(
        analysis=analysis,
        experiment=controlled_experiment(seed, assets),
        prediction=evaluate_prediction(seed),
        readiness={case: assess(sample_evidence(case)) for case in ("pass", "fail", "incomplete")},
        ground_truth=truth,
        unit_summaries={
            unit: analyze(data, unit, fit_weibull=False)["summary"] for unit in ("node", "job")
        },
    )
    bundle["execution"] = dict(
        elapsed_seconds=perf_counter() - started,
        python=platform.python_version(),
        platform=platform.platform(),
        dataset_sha256=hashlib.sha256(data.model_dump_json().encode()).hexdigest(),
    )
    return bundle


def evaluate_classification(seeds=range(2040, 2050), assets=1000) -> dict:
    cases = []
    for seed in seeds:
        data, truth = simulate(seed, assets)
        analysis = analyze(data, fit_weibull=False)
        actual = {p["domain"]: p["classification"] for p in analysis["patterns"]}
        for domain, expected in truth["expected_patterns"].items():
            cases.append(
                dict(
                    seed=seed,
                    domain=domain,
                    expected=expected,
                    actual=actual.get(domain, "insufficient_evidence"),
                    passed=actual.get(domain) == expected,
                )
            )
    passed = sum(c["passed"] for c in cases)
    return dict(
        origin="synthetic",
        seeds=list(seeds),
        assets=assets,
        cases=cases,
        passed=passed,
        total=len(cases),
        accuracy=passed / len(cases) if cases else None,
        limits="Frozen generator-family holdout seeds; no real-customer, novel-failure or causal-classification accuracy claim",
    )


def save_bundle(directory: Path, seed=2026, assets=1000) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    bundle = build_bundle(seed, assets)
    # Detailed rows are inspectable in the complete bundle; the summary is convenient for review.
    (directory / "bundle.json").write_text(json.dumps(bundle, indent=2, allow_nan=False) + "\n")
    evaluation = evaluate_classification()
    (directory / "classification-evaluation.json").write_text(
        json.dumps(evaluation, indent=2, allow_nan=False) + "\n"
    )
    (directory / "TECHNICAL_REVIEW.md").write_text(technical_report(bundle))
    (directory / "EXECUTIVE_BRIEF.md").write_text(executive_report(bundle))
    return bundle
