# Break/fix runbooks

Actions change **simulation state**. They do not reset GPUs, drain real nodes, or execute arbitrary commands.

Inject → run 40 probes → inspect incident → investigate → inspect citations → approve → verify. Recovery runs 20 probes. Repeated plans and plans invalidated by further incident changes are rejected.

| Scenario | Evidence | Owner | Allowed action | Verification |
|---|---|---|---|---|
| GPU memory exhaustion | CUDA memory errors, batch-size change, trace IDs | ml-platform | Roll back simulated batch config | 20 successful timely responses |
| Storage latency | Slow artifact-store signal/spans, service dependency | storage-platform | Remove simulated dependency latency | Successful responses ≤ 300 ms |
| Node unavailable | Node readiness signal, catalog placement | compute-platform | Restore simulated node | Successful probes |
| Telemetry outage | Independent exporter-down signal, outbox growth | observability-platform | Restore delivery and replay | Empty queue and successful probes |
| Driver drift | Desired/observed versions and provenance | compute-platform | Reconcile simulated desired state | No driver drift; successful probes |
| Alert storm | Repeated errors, one incident, grouped count | ml-platform | Roll back configuration | One recovery, no active incident |
| Insufficient evidence | Failures without a diagnostic signal | ml-platform | None; collect further evidence | Abstention; incident stays active |

## Healthy service, breached SLO

Inspect historical failures. Recovery restores current service; it cannot erase reliability cost. Check the short burn window and continue monitoring the long window.

## Stale proposal

An alert update, acknowledgment, or configuration change can invalidate a plan. Investigate again and approve the current result.

## Verification failed

The incident stays `mitigating`. Check whether the action matched the evidence. Tests deliberately execute an inappropriate action to prove that executing a fix alone cannot close an incident.

## Queue overflow

New evidence is dropped after capacity. Inspect `fleetops_telemetry_dropped_total`, restore the backend, check replay counts, and document the missing interval. Durable storage does not provide infinite buffering.

## Real GPU hardware error

Associate the UUID with its catalog and owner. Consult NVIDIA's diagnostics for that error and the actual system. The baseline abstains for unsupported hardware signals. Simulation runbooks are not real hardware repairs.
