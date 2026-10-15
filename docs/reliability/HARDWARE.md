# Hardware readiness and live validation

## What is implemented

The lab policy requires software, memory and targeted-stress checks, at least 120 seconds of observation, at least 95% required diagnostic-result coverage, and recorded hardware/driver/DCGM identity. These are illustrative lab criteria, not NVIDIA certification standards. Authored fixtures demonstrate pass, fail and insufficient-data states.

A failed check produces `fail`. Missing/skipped/unknown tests, versions, duration or coverage produce `insufficient_data`. A passing synthetic fixture always has `physical_gpu_validated: false`.

## Run on a supported idle GPU

Install the appropriate NVIDIA driver/DCGM for the host using the official documentation. Check supported tests and prerequisites for your installed release. Use an idle operator-owned GPU with permission for active diagnostics; diagnostics consume compute, memory, PCIe, power and cooling capacity.

```bash
fleetops-reliability diagnose --execute --idle-confirmed --gpu 0 --output reports/live-readiness
```

The runner uses a fixed argument list, no shell and no remote command. It invokes `dcgmi diag --run 3 --entity-id gpu:0 --json`, with a timeout. It stores raw stdout/stderr, hashes the stdout, records measured wall duration, and queries GPU UUID/driver and DCGM version. Missing `dcgmi` records `unavailable` without claiming a test ran.

The result adapter supports the documented legacy `DCGM GPU Diagnostic` / `test_categories` fixture contract. Other release schemas remain insufficient evidence until a verified adapter is added. Software/deployment subtests are aggregated; partial, skipped and unknown outputs cannot pass. A process failure is not automatically classified as a hardware defect.

The timeout stops the local process; verify device state before resuming workloads. Skipped or unsupported interconnect tests do not establish NVLink, InfiniBand or rack-scale health. Add multi-GPU/NCCL validation only on actual supported hardware with an explicit test policy.

## Bring your evidence

Use `fleetops-reliability readiness evidence.json --output readiness-report.json` to evaluate a canonical evidence envelope. See the sample files under `examples/reliability/`. The operator remains responsible for the truth of imported provenance and coverage metadata.

For telemetry, use the existing `scripts/ingest_dcgm.py` path and validate the exporter's actual fields. An Xid gauge contains a code, not a cumulative interruption count. Hardware warnings require workload-impact evidence and source-specific interpretation before becoming interruption records.

References: [NVIDIA diagnostics](https://docs.nvidia.com/datacenter/dcgm/latest/learn/modules/dcgm-diagnostics.html), [DCGM Exporter metric semantics](https://docs.nvidia.com/datacenter/dcgm/latest/reference/dcgm-exporter-metrics.html), [Xid catalog](https://docs.nvidia.com/deploy/xid-errors/analyzing-xid-catalog.html).
