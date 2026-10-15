# GPU Fleet Reliability Intelligence

Evidence origin: **synthetic controlled lab**.

## Measurement

- Unit: gpu; observed entities: 1,000
- Source records: 2,301; interruption episodes: 636; shared incidents: 555
- Operating exposure: 166,598.97 gpu-hours
- Lost observed time: 655.03 gpu-hours
- Unknown coverage: 568.00 gpu-hours
- Interruption intensity: 3.818 / 1,000 operating hours

## Competing hypotheses

- **software / systemic_candidate**: Candidate driver has higher matched software-interruption rates in ≥2 providers; reproduce on hardware. Episodes: 420. Evidence: software-100-0, software-102-0, software-102-1
- **thermal / environmental_candidate**: Observed interruptions concentrate in one rack; compare cooling, power and placement. Episodes: 83. Evidence: shared-cooling-episode
- **interconnect / configuration_candidate**: Episodes concentrate in one firmware/configuration cohort; validate a matched configuration experiment. Episodes: 72. Evidence: interconnect-120-0, interconnect-132-0, interconnect-163-0
- **memory / unresolved**: Observed pattern does not distinguish the competing causes. Episodes: 60. Evidence: memory-103-0, memory-115-0, memory-154-0
- **unknown / insufficient_evidence**: Fewer than five interruption episodes. Episodes: 1. Evidence: shared-cooling-episode

These classifications prioritize investigations. They do not establish causation.

## Statistical review

Matched driver comparisons condition on provider, rack, model, firmware/configuration, workload and age band. Unmatched strata are excluded.
Common strata: 80.

Kaplan–Meier measures observed operating time to FIRST interruption. Unknown coverage right-censors a device at the start of its first gap. Maintenance pauses the exposure clock.

Weibull output: `{"failures": 399, "interpretation": "First-interruption fit, not recurrent MTBI; inspect cohort homogeneity and censoring assumptions", "km_max_abs_gap": 0.0536854853123202, "review_required": false, "right_censored": 601, "scale_hours": 307.54121342275346, "shape": 1.0051848189065833, "status": "descriptive_fit"}`

Pooled cohorts may violate the Weibull assumptions. The KM gap is a descriptive diagnostic, not a goodness-of-fit test.

## Controlled follow-up

Randomized assignment fixed before outcomes; compare concurrent eligible canary/control cohorts

Concurrent canary/control rate ratio: 0.11859233543378982; approximate 95% CI: [0.07961746960545149, 0.17664643316769682].
Relative reduction: 88.1%.
Predeclared demonstration criteria passed: True.
Acceptance requires ≥30% relative reduction and an approximate rate-ratio upper confidence bound below one. The synthetic generator creates the intervention effect.

## Held-out prediction benchmark

Mean/scale fit on training only; threshold maximizes validation F1; test untouched
Split: `{"train": 1120, "validation": 480, "test": 400, "train_days": [0, 6], "validation_days": [7, 9], "test_days": [14, 18], "held_out_provider": "csp-cirrus", "device_overlap": 0}`

| Method | Precision | Recall | False alerts / 1,000 h | Median warning h |
|---|---:|---:|---:|---:|
| rules | 0.2857142857142857 | 0.4444444444444444 | 16.67 | 4.053891285713997 |
| logistic | 0.43478260869565216 | 0.5555555555555556 | 10.83 | 3.7434454261712724 |

## Readiness and boundaries

The authored readiness fixtures exercise pass, fail and insufficient-data decisions. No physical NVIDIA GPU or customer fleet was available for this recorded run.
Live collection and the opt-in DCGM runner require supported operator-owned hardware. Unknown schemas, missing versions, skipped tests, short duration or insufficient coverage cannot pass.

## Engineering priorities

1. Reproduce the candidate-driver pattern on a supported isolated GPU or cluster.
2. Inspect the affected rack's cooling and power records; keep this separate from the driver investigation.
3. Run a controlled fabric-configuration comparison with equal workload and placement.
4. Gather real failure labels before deploying predictive health decisions.

## Limits

- MTBI here is operating entity-hours / interruption episodes, an inverse rate estimator.
- GPU, node and job denominators are distinct; no unit is inferred from GPU-hours.
- Correlated failures make naive Poisson intervals optimistic.
- Survival is time to FIRST interruption, censored at first unknown coverage.
- The pooled Weibull fit may mix cohorts; review fit gap and homogeneous subcohorts.
- Synthetic scale is logical record count, not physical fleet operation.
- No independent operator or CSP review has been completed. Use REVIEW.md to record an actual review.
