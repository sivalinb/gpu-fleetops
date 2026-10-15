# Portfolio and interview narrative

## The problem

GPU fleets produce many errors, but a reliability decision requires more than a count. Teams must agree on the interruption unit, observed operating exposure, duplicate-event policy and missing-data rules before comparing customers or evaluating a fix.

## What I built

I extended GPU FleetOps with three provider-format adapters, a shared measurement contract, censored reliability statistics, matched driver cohorts, failure-pattern hypotheses, a randomized canary experiment, a held-out predictive-health benchmark, and versioned readiness reports. The UI, API and reports share the same calculation code.

## Connection to my background

The project extends fleet observability, inventory and release-validation work from Apple PCC, and rack-scale architecture/customer escalation experience from Oracle Exalogic, into a reproducible GPU reliability methodology. The independent project uses fictional fleet data and does not claim to reproduce either employer's internal systems.

## Five-minute demonstration

1. Explain the measurement contract and the exposure-clock diagram.
2. Compare the candidate driver across providers and inspect common matching strata.
3. Separate a shared driver pattern from a local cooling incident and configuration cohort.
4. Read the randomized follow-up result, interval and acceptance criteria.
5. Show prediction false alerts, a readiness result with insufficient evidence, and the technical/executive reports.

## Evidence language

Say: “I implemented and evaluated a reproducible synthetic fleet reliability lab, with source-explicit integrations and a local supported-GPU validation path.”

Claim physical GPU or CSP validation only after those runs exist. Report logical replay scale, synthetic model performance and historical v1.0 verification with their scope. This project supports a principal-engineering discussion about methodology, customer interfaces and prioritization; direct NVIDIA firmware, multi-NUMA and real multi-CSP reliability ownership still require separate experience.
