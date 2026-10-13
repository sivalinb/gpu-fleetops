# Agentic investigation

## When AI adds value

Detection, SLO math, inventory reconciliation, incident deduplication, and recovery checks are deterministic. The model is used for the part that benefits from interpretation: choosing evidence to inspect and synthesizing a supported diagnosis across changes, workload signals, inventory, and runbooks.

The baseline runs the same read tools and applies explicit diagnostic rules. It is labeled **deterministic rules**, not AI. Live mode makes actual provider calls. It supports the Chat Completions function-tool protocol; choose a provider and model with that capability. Model/API compatibility is separate from a Codex subscription.

## Read tools

| Tool | Scope |
|---|---|
| `get_incident` | One active incident in the caller's session. |
| `query_evidence` | Recent evidence for that incident's service. |
| `get_inventory` | Service catalog, affected assets, owners, dependencies. |
| `get_slo` | That session's reliability report. |
| `get_runbooks` | A finite set of supported recovery policies. |

Tools accept no model-supplied session, incident, URL, file, or command parameters. No recovery tool is exposed. Logs and tool results are explicitly treated as untrusted data.

## Loop and validation

1. Send the incident ID, tool schemas, and output schema.
2. Execute model-selected read tools; return results with matching tool-call IDs.
3. Stop after at most six model responses and five tool calls per response.
4. Validate the final JSON through Pydantic.
5. Check that cited IDs were actually retrieved and support the declared diagnostic class.
6. Check that the action matches the supported cause and runbook.
7. Create an approval proposal or abstain.

A failure, malformed argument, fabricated citation, unsupported cause, inconsistent action, timeout, rate limit, or iteration limit returns a safe abstention. Error reports include exception categories instead of provider details or credentials. Confidence is an uncalibrated hypothesis estimate; the baseline uses a fixed heuristic score.

## Approval boundary

The model's result is not authority to execute a fix. An operator must approve a current plan. The runner checks the incident and configuration revisions, executes only an allowed simulation action, records the operator/action, and runs 20 verification probes. Failed verification leaves the incident active.

## Evaluation

`scripts/evaluate.py` runs seven known synthetic regression cases and records expected/actual actions, citation resolution, verified recoveries, deduplication, and timing. Those results are a **baseline regression evaluation**, not an LLM accuracy estimate.

`tests/test_agent.py` exercises the real model protocol with scripted providers and HTTP mock transports. It covers call/result correlation, provider errors, untrusted log instructions, quotas, unknown tools, arbitrary arguments, invalid JSON, fabricated citations, inconsistent actions, and the loop bound.

For a live model benchmark, create a separate held-out dataset with ambiguous and insufficient-evidence cases. Record the provider, model/version, prompt version, tools, token usage, evidence correctness, cause/action accuracy, abstention quality, operator time, and cost. Compare against the rules baseline and a documented manual procedure. Avoid tuning and reporting on the same cases.

## Provider configuration

Set `FLEETOPS_AI_MODE=live`, `FLEETOPS_AI_BASE_URL`, `FLEETOPS_AI_MODEL`, and `FLEETOPS_AI_API_KEY` on the server. The base URL must use HTTPS. The implementation does not guess a model ID or require a paid call to run the demo.

Live quotas are three investigations/session and sixty/server/hour. Resetting a lab does not reset the shared provider quota. Quotas are process-local; a distributed deployment needs shared accounting.

Protocol reference: [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling). The provider adapter uses the compatible Chat Completions shape rather than claiming compatibility with models that require another API.
