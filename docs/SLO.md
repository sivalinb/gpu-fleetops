# SLI and SLO policy

`inference-api` uses a **rolling 30-day request window**, evaluated against the simulation clock. All requests are eligible, including requests during maintenance. Seeded requests are synthetic baseline data. Future observations are excluded.

| Objective | Good event | Denominator | Target |
|---|---|---|---|
| Availability | HTTP status 200–399 | All eligible requests | 99.5% |
| Latency | Successful response with latency ≤ 300 ms | All eligible requests | 99% |

Failed responses are bad for both objectives, even when fast. CPU time is measured separately; reported service latency is synthetic. These are demonstration policies, not NVIDIA's internal objectives.

```text
SLI                  = good / total
Allowed bad events   = total × (1 − target)
Burn rate            = bad / allowed_bad
Budget remaining (%) = 100 × (1 − bad / allowed_bad)
```

No requests means **no data**. Overspent budget can be negative. The budget uses observed counts without assuming future traffic. Healthy traffic improves the ratio; failures remain until they age out.

Example: 1,000 requests at 99.5% allow five bad events. Ten failures produce burn rate 2 and remaining budget −100%.

## Paired-window paging

| Policy | Long window | Short window | Both burn rates must reach |
|---|---|---|---|
| Fast | 1 hour | 5 minutes | 14.4 |
| Slow | 6 hours | 30 minutes | 6 |

At least 20 long-window and 10 short-window requests are required. Both windows must burn, so old failures cannot keep a fast page firing after recent traffic recovers. Low-traffic real services need complementary synthetic-probe policies.

Maintenance suppresses incident creation and paging records. It does not alter SLO denominators or hide existing incidents.

New workload incident creation/updates additionally require an unhealthy request in the current probe batch. Historical budget consumption stays visible after recovery and cannot by itself reopen a resolved incident. A fresh unhealthy batch can create a new incident.

## App versus Prometheus

Gradio evaluates persisted session requests using accelerated simulation time. Prometheus evaluates aggregate counters using wall-clock scrape windows. Targets and denominators match, but charts differ during accelerated drills. Prometheus has fast-burn examples; the application also implements the slow pair.

Gradio includes seeded history. Prometheus request counters include executed probes since startup. Aggregate SLI gauges include each active lab's latest historical report. Production monitoring should use authoritative service counters and regular window evaluation.

`test_slo.py` covers no data, boundaries, failed-but-fast requests, budgets, rolling windows, future samples, minima, and paired burns. Break/fix tests verify maintenance accounting and preserved failures. Deployment tests check Prometheus denominators and success buckets.
