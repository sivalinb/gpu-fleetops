# Contributing

Use Python 3.12+. Install `requirements-dev.txt`, then install the project with `pip install --no-deps -e .`. Run Ruff and pytest before proposing a change.

Keep the simulation label visible. New faults need a use case, deterministic evidence, a runbook or intentional abstention, recovery verification, and tests for the failure boundary. New model tools must stay incident-scoped and read-only.

Do not commit credentials, real private telemetry, personal on-call contacts, runtime databases, or `.env` files. Keep test fixtures synthetic. Record the scope of every benchmark and evaluation.
