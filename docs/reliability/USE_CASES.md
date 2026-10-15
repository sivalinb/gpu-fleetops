# Use cases and executable evidence

| Use case | Implementation / check |
|---|---|
| Different provider schemas and seconds/hours | Adapter round-trip tests |
| Repeated or conflicting source IDs | Identity validation and deduplication tests |
| Same key across separate outages | Disconnected-episode test |
| Multiple causes during the same outage | Overlap, lost-time and unknown-domain test |
| GPU versus node/job measurement | Explicit-unit tests |
| Maintenance and missing telemetry | Exposure and survival-censor tests |
| Healthy device never fails | Censoring and zero-event bounds |
| Known survival curve with tied events | Hand-calculated KM test |
| Known censored lifetime distribution | Weibull parameter-recovery test |
| Unequal workload mix | Common-stratum/Simpson-paradox test |
| No comparable cohort | No-common-support test |
| Systemic versus rack versus configuration pattern | Seeded replay and multi-seed evaluation |
| Evaluate a driver mitigation | Randomized concurrent canary/control trial |
| Predict future interruption | Held-out provider/device/time benchmark |
| No physical GPU available | Missing-tool runner result |
| Unknown diagnostic release shape | Insufficient-data assessment |
| Authenticated analysis and retained reports | API and session-isolation integration test |
| Observe analyzer operation | Prometheus, structured log and trace |
| Review findings with engineers and executives | Generated technical review and executive brief |
| Existing break/fix incident operations | Original seven scenarios, SLO and agent suites |

The verification page separates executed tests from future physical-hardware and independent-operator work.
