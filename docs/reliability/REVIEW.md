# Independent engineering review

Status: **not yet performed**. This file is a review protocol, not a fabricated endorsement.

Ask an infrastructure engineer to run the project from a clean checkout and record:

- Reviewer/date/environment and the actual commands used.
- Whether the interruption unit, exclusions and exposure are clear.
- Whether they can reproduce the driver, cooling and configuration investigations without the author.
- Whether uncertainty, missing telemetry and simulated inputs are understandable.
- Whether they can explain why the canary/control comparison is stronger than an unadjusted before/after claim.
- Whether the readiness policy distinguishes failed tests from absent evidence.
- Setup and diagnosis time; confusing steps; proposed documentation changes.
- Findings accepted, changes made, and rerun evidence.

A future CSP review should additionally agree on interruption definitions, shared incident IDs, repair/replacement handling, fleet age, censoring, workload mix, firmware transitions, data retention, launch acceptance criteria and responsibility for the next experiment.
