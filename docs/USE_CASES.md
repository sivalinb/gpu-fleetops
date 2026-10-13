# Use cases and test map

| ID | Use case | Expected outcome | Automated evidence |
|---|---|---|---|
| UC01 | Discover a fleet | Stable identities, relationships, owners, provenance | `test_inventory.py` |
| UC02 | Reconcile conflicting discovery | Older/lower-priority records do not overwrite trusted state; conflicts visible | `test_inventory.py` |
| UC03 | Measure reliability | Correct availability/latency denominators and budgets | `test_slo.py` |
| UC04 | GPU memory failure | Owned incident, cited diagnosis, rollback, verified recovery | Parametrized lifecycle in `test_breakfix.py` |
| UC05 | Storage latency | Dependency ownership and recovery | Same lifecycle matrix |
| UC06 | Node unavailable | Compute ownership and recovery | Same lifecycle matrix |
| UC07 | Telemetry outage | Durable queue, independent signal, replay | Lifecycle and restart tests |
| UC08 | Queue capacity exhausted | Explicit drops; finite memory/storage queue | `test_outbox_is_bounded_and_reports_drops` |
| UC09 | Driver inventory drift | Compare desired/observed state and reconcile | Lifecycle matrix |
| UC10 | Alert storm | One active incident with grouped alert count | Concurrent dedup and alert storm tests |
| UC11 | Insufficient evidence | Abstention, no recovery proposal | Baseline and agent tests |
| UC12 | Maintenance | Suppressed paging, failures still counted | Maintenance test and API test |
| UC13 | Unacknowledged incident | Timed escalation record | Escalation/acknowledgment test |
| UC14 | Unapproved/stale/repeated fix | Rejection before an obsolete action executes | Recovery boundary tests |
| UC15 | Inappropriate fix | Failed verification; incident remains active | Wrong-fix test |
| UC16 | Real DCGM/Kubernetes input | Validated authenticated input, preserved source | Adapter and API integration tests |
| UC17 | Cross-session access | Foreign incidents and evidence unavailable | Namespace isolation tests |
| UC18 | Model/provider failure | No secret leakage; safe abstention | Scripted provider and HTTP contract tests |
| UC19 | Unsafe model action | Unknown tools, parameters, citations, and mismatched actions rejected | Agent negative matrix |
| UC20 | Restart and replay | State/outbox survive restart; replay remains idempotent | Persistence test |
| UC21 | Public Gradio demo | Components mount and callbacks complete the lifecycle | `test_ui.py`, HTTP smoke |
| UC22 | Deployment configuration | Local bindings, secrets, probes, dashboards, pipelines | `test_deployment.py`, container CI job |

Tests include boundary inputs and explicit assertions on user-visible outcomes. CI runs Python 3.12 and 3.13 and collects coverage and JUnit artifacts. Run status must be checked; the presence of a workflow is not proof it executed.
