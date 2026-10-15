# Fleet reliability review — executive brief

**Scope: synthetic portfolio experiment; no customer or physical-GPU reliability claim.**

The replay covers 1,000 logical GPUs and 166,599 operating GPU-hours. It contains 636 interruption episodes and 655.0 lost GPU-hours.

The analysis prioritizes three separate investigations: a shared driver pattern, a local cooling incident, and a fabric-configuration cohort. A matched comparison reduces measured workload and placement differences; remaining uncertainty is explicit.

A randomized synthetic canary/control follow-up measured a 88.1% lower canary interruption rate.
This demonstrates the evaluation method. Real effectiveness requires a hardware trial and customer validation.

**Decision requested:** authorize an isolated reproduction and a limited canary after readiness checks; do not promote from replay results alone.

**Acceptance:** predefined interruption-rate reduction, enough observation exposure, no new hardware errors, and an agreed rollback criterion.
