# Portfolio and interview guide

## The problem

A hardware signal without service context cannot tell an on-call engineer what is affected or who should respond. A service alert without inventory and change history cannot explain the infrastructure behind a failure. GPU FleetOps joins that context and leaves an auditable path from signal to verified recovery.

## What to show

1. A five-minute Gradio drill: GPU memory error → incident → evidence → proposal → approval → verification.
2. A telemetry outage: queue persistence, independent detection, and replay.
3. An ambiguous failure: abstention rather than an unsupported fix.
4. The architecture: why inventory, telemetry, and incident workflows share identities.
5. The tests and reports: measured results with their scope, including negative cases.

## Alignment with the target role

| Role responsibility | Project evidence |
|---|---|
| Common telemetry across infrastructure | Shared observation contracts, JSON logs, trace IDs, OpenTelemetry, real DCGM/Kubernetes adapters. |
| Dashboards and troubleshooting | Gradio views, Grafana provisioning, SLO policy, correlated evidence. |
| Incident and maintenance automation | Deduplication, routing, acknowledgment, escalation records, maintenance, reports. |
| Hardware/software catalog and ownership | Stable asset IDs, service relationships, provenance, source precedence, stale/drift flags. |
| AI-assisted operations | Bounded read-only tool loop, evidence/action validation, provider contract tests, abstention. |
| Production engineering principles | Persistence, finite queues, restart behavior, approval boundaries, verification, deployment profiles and CI. |

This demonstrates technical responsibilities associated with NVIDIA requisition JR2024816. It does not replace the role's senior experience and cross-functional leadership requirements.

## Explain the tradeoffs

- Why request-based SLOs count failed-but-fast responses as bad latency.
- Why maintenance suppresses paging but preserves reliability accounting.
- Why service recovery cannot reset the budget.
- Why AI interprets evidence while policy and execution remain deterministic.
- Why the outbox is bounded, and how dropped data becomes visible.
- Why one process is the current consistency boundary.
- How to extend ownership and escalation to real organizations and approved paging integrations.

## Add evidence from real use

Ask another engineer to set up the project and handle a drill using the runbook. Measure their investigation time, record the points of confusion, and make a documented improvement. Add a real GPU integration session if hardware becomes available. Run a held-out live-agent evaluation when a model provider is configured.

These are valuable follow-ups because a runnable application and automated tests do not establish adoption, independent usability, or production ownership.

## Honest résumé wording

> Built a GPU infrastructure operations reference platform connecting inventory, telemetry, request-based SLOs, and incident workflows; implemented evidence-grounded AI investigation, approved recovery, failure drills, and automated validation.

Add numerical test/coverage or measured benchmark results only after checking the current verification report. Say **simulated fleet** or **logical inventory records** when describing the demo scale. Avoid claiming physical GPU deployment, live-model accuracy, production availability, or team adoption without that evidence.
