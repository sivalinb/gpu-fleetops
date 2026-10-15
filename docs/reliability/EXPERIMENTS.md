# Controlled experiments and evaluation

## Recorded fleet

Seed 2026 creates 1,000 logical GPUs observed for 168 scheduled hours. Providers and hardware identifiers are fictional. The three adapters genuinely execute different input schemas and unit conversion.

The generator plants a higher software-interruption intensity in candidate-driver devices in two providers; a shared cooling outage in one rack of the third; a fabric-configuration issue; and background memory interruptions. It also emits repeated records, warnings, maintenance interruptions and telemetry gaps.

The analyzer receives only the canonical dataset. The separate truth map is used afterward for evaluation. `classification-evaluation.json` runs seeds 2040–2049, four expected domain outcomes per seed. This checks generalization to other draws in the same generator family; it does not measure novel real-world root-cause accuracy.

## Controlled follow-up

Eligible candidate-driver GPUs in the two affected providers are assigned to canary or control before outcomes are generated. The layout and assignment remain fixed across periods. In the follow-up period only the canary receives the simulated driver mitigation. Concurrent controls retain the problem. Other failure modes remain present.

The acceptance policy is declared in code: at least 30% lower canary interruption rate, with an approximate 95% canary/control rate-ratio upper bound below one. Rates use actual measured operating exposure rather than nominal fleet size. Zero-event comparisons abstain instead of manufacturing a ratio.

The recorded synthetic intervention effect is created by the generator. It is a demonstration of experiment design and numerical implementation, not evidence that any real driver or firmware fix works.

## Break/fix exercises

| Exercise | Inspect | Expected behavior |
|---|---|---|
| Repeat one source event | Episode count and provenance | Idempotent ingestion |
| Reuse an incident key after recovery | Episode boundaries | Separate interruption |
| Overlap two outage causes | Exposure and unknown attribution | One entity outage; no double-counted lost time |
| Remove telemetry during a failure | Coverage and censoring | Unknown time excluded; survival censored |
| Shift workload mix between driver cohorts | Raw and matched comparisons | Compare only common strata |
| No failures observed | Rate bounds | No infinite MTBI assertion |
| Missing hardware test or new JSON schema | Readiness | Insufficient evidence |
| Mitigation reduces synthetic errors | Concurrent cohorts | Quantified effect and acceptance result |
| Prediction makes false alerts | Confusion matrix | Visible FP/FN and operating-hour denominator |

Run `pytest tests/test_reliability.py -q` for the executable edge cases. The original seven incident drills are in Operations and [RUNBOOKS](../RUNBOOKS.md).
