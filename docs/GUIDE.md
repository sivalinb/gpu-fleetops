# A simple guide

GPU FleetOps is a practice environment for operating GPU infrastructure. It connects **the hardware, the service, its health, the person responsible, and the response to a failure**.

The fleet and GPU failures are simulated so anyone can try it. The application, database, workload probes, investigation tools, and response workflow execute.

## A normal day

Open fleet inventory to see assets and owners. Open telemetry to see service health. Availability measures successful responses. The latency objective measures successful responses within a declared limit. The dashboard shows whether the service has consumed more errors than its objective allows.

## When something breaks

1. A signal crosses the alert policy.
2. Related alerts become one incident.
3. The catalog supplies ownership and dependencies.
4. The investigator reads evidence and proposes a supported hypothesis.
5. The operator reviews and approves a recovery plan.
6. The app applies the simulation runbook and runs verification probes.
7. The incident closes only after those checks pass.

If evidence cannot support a diagnosis, the investigator identifies what is missing and proposes no action.

| Tab | Purpose |
|---|---|
| Operations | Inject failures, run probes, see incidents. |
| Investigation & recovery | Inspect citations and tool actions; approve recovery. |
| Fleet inventory | Find assets, owners, environments, sources, and drift. |
| Telemetry & SLOs | Inspect evidence and reliability calculations. |
| Architecture | Follow the illustrated system flow. |
| Incident report | Read the timeline and prevention task. |

## Five-minute demonstration

Start with GPU memory exhaustion. Show the change, workload failures, and SLO impact. Investigate and point to a specific evidence ID. Explain why the model cannot execute the fix. Approve recovery, then show healthy service with the incident still reflected in the budget.

Reset and demonstrate a telemetry backend outage. Probes continue; evidence queues durably. Investigation uses an independent control-plane signal. Recovery drains the queue and checks the result.

Finally, demonstrate insufficient evidence. The investigator abstains.

The simulation clock advances six seconds per probe. Seeded healthy requests span two hours. These timestamps make rolling windows visible quickly; they are not wall-clock performance measurements.
