"""Gradio operator experience and small, testable presentation callbacks."""

import html
from datetime import UTC, datetime
from pathlib import Path

import gradio as gr
import plotly.graph_objects as go

from .models import SCENARIOS, Fault

CSS = """
.gradio-container { max-width: 1320px !important; font-family: Inter, ui-sans-serif, system-ui, sans-serif !important; }
.fleet-hero { padding: 28px 32px; border: 1px solid #25404b; border-radius: 18px; background: linear-gradient(110deg,#0b1726,#113335); color: #effaf7; margin-bottom: 12px; }
.fleet-hero .eyebrow { color: #89e5bd; font: 600 12px ui-monospace,monospace; letter-spacing: 2px; }
.fleet-hero h1 { font-size: 38px; letter-spacing:-1px; margin: 10px 0; color:#fff; }
.fleet-hero p { max-width:800px; color:#b9cfd0; line-height:1.65; font-size:15px; margin:6px 0; }
.fleet-badges { display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }
.fleet-badges span { padding:6px 10px; border:1px solid #365b5b; border-radius:30px; color:#b8f5d8; font-size:11px; }
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:12px 0 20px; }
.kpi { padding:18px 20px; border:1px solid #dce8e3; border-radius:14px; background:#f5faf8; }
.kpi .label { font-size:11px; color:#53736c; text-transform:uppercase; letter-spacing:1px; }
.kpi strong { display:block; margin:8px 0; font-size:30px; color:#102e29; letter-spacing:-1px; }
.kpi small { color:#53736c; font-size:11px; }
.kpi.bad { background:#fff4ed; border-color:#f6cbb7; }
.kpi.bad strong { color:#a44123; }
.step-strip { display:flex; flex-wrap:wrap; gap:8px; padding:12px 0; }
.step-strip span { color:#316e5e; font-size:12px; padding:6px 10px; background:#eaf5f0; border-radius:6px; }
.architecture img, .architecture svg { width:100%; height:auto; border-radius:16px; }
@media (max-width:760px) { .kpis { grid-template-columns:repeat(2,1fr); } .fleet-hero {padding:22px;} .fleet-hero h1 {font-size:30px;} }
"""

HERO = """
<div class="fleet-hero">
  <div class="eyebrow">GPU FLEETOPS / RELIABILITY INTELLIGENCE</div>
  <h1>Understand failures. Measure the improvement.</h1>
  <p>Compare GPU fleets, quantify interruption risk, and evaluate a controlled mitigation.
  Follow every conclusion back to its evidence, exposure and uncertainty.</p>
  <div class="fleet-badges"><span>Three fictional CSPs</span><span>Explicit MTBI methodology</span><span>Controlled experiments</span><span>Evidence you can inspect</span></div>
</div>
"""


def percentage(value):
    return "No data" if value is None else f"{100 * value:.2f}%"


def kpis(summary: dict) -> str:
    availability, latency = summary["slo"]["availability"], summary["slo"]["latency"]
    open_count = sum(row["status"] != "resolved" for row in summary["incidents"])
    cards = [
        ("Availability", percentage(availability["sli"]), "SLO ≥ 99.5% · rolling 30 days", availability["status"] == "breached"),
        ("Good latency", percentage(latency["sli"]), "99% successful requests ≤ 300 ms", latency["status"] == "breached"),
        ("Active incidents", str(open_count), "Owner, evidence, and an auditable timeline", open_count > 0),
        ("Telemetry queue", str(summary["queue_size"]), "Durable buffer · capacity 1,000 records", summary["queue_size"] > 0),
    ]
    return '<div class="kpis">' + "".join(
        f'<div class="kpi{" bad" if bad else ""}"><div class="label">{label}</div><strong>{value}</strong><small>{note}</small></div>'
        for label, value, note, bad in cards) + "</div>"


def latency_chart(rows: list[dict]) -> go.Figure:
    selected = rows[-180:]
    x = [datetime.fromtimestamp(row["timestamp"], UTC).isoformat() for row in selected]
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=x, y=[row["latency_ms"] for row in selected], mode="lines", name="Reported latency",
                               line={"color": "#168266", "width": 2}, fill="tozeroy", fillcolor="rgba(22,130,102,.08)"))
    failures = [row for row in selected if row["status"] >= 400]
    figure.add_trace(go.Scatter(x=[datetime.fromtimestamp(row["timestamp"], UTC).isoformat() for row in failures],
                               y=[row["latency_ms"] for row in failures], mode="markers", name="Failed request",
                               marker={"color": "#e37646", "size": 6}))
    figure.add_hline(y=300, line_dash="dash", line_color="#d79532", annotation_text="300 ms objective")
    figure.update_layout(height=310, margin={"l": 50, "r": 20, "t": 20, "b": 35}, template="plotly_white",
                         paper_bgcolor="#ffffff", plot_bgcolor="#f8fbfa", legend={"orientation": "h", "y": 1.15},
                         yaxis_title="Synthetic service latency (ms)", xaxis_title="Simulation clock (UTC)", font={"family": "Inter, sans-serif"})
    return figure


def diagnosis_markdown(report: dict) -> str:
    diagnosis = report["diagnosis"]
    mode = "Live tool-calling model" if report["mode"] == "live" else "Rules baseline — no LLM call"
    lines = [f"**{mode}**", "", diagnosis["summary"], ""]
    if diagnosis["abstained"]:
        lines.extend(["**Abstained. No recovery action was proposed.**", "", *["- " + reason for reason in diagnosis["missing_evidence"]]])
    else:
        for hypothesis in diagnosis["hypotheses"]:
            lines.extend([f"**Hypothesis:** {hypothesis['cause'].replace('_', ' ')}", "", hypothesis["explanation"], "",
                          "Evidence: " + ", ".join(f"`{eid}`" for eid in hypothesis["evidence_ids"]), ""])
        lines.extend(["**Proposed action:** `" + diagnosis["action"] + "`", "", "Review the evidence and approve below. Recovery runs 20 verification probes."])
    return "\n".join(lines)


class Presenter:
    def __init__(self, service):
        self.service = service

    def views(self, namespace):
        lab = self.service.session(namespace)
        summary = lab.summary()
        incidents = [[row["id"], row["status"], row["owner"], row["title"], row["alert_count"], "Yes" if row["escalated"] else "No"] for row in summary["incidents"]]
        inventory = [[row["name"], row["kind"], row["environment"], row["owner"] or "Unassigned", row["source"],
                      row["driver_version"] or "—", "Drift" if row["drift"] else "Stale" if row["stale"] else "Current",
                      "Synthetic" if row["simulated"] else "Discovered"] for row in summary["inventory"]]
        evidence = [[row["id"], row["kind"], row.get("code", row.get("name", "—")), row["message"], row["source"]]
                    for row in lab.store.list(namespace, "evidence", limit=60)]
        postmortem = lab.postmortem(summary["incidents"][0]["id"]) if summary["incidents"] else "Run a drill to generate an incident report."
        state = f"**Current drill:** `{html.escape(summary['fault'])}` · **Maintenance:** {'active' if summary['maintenance_active'] else 'inactive'} · **Clock:** {datetime.fromtimestamp(lab.now, UTC).strftime('%H:%M:%S UTC')}"
        return [kpis(summary), latency_chart(lab.requests()), incidents, inventory, evidence, summary["slo"], postmortem, state]

    def initialize(self, namespace):
        return ["Ready. Inject a fault, run probes, then investigate.", *self.views(namespace)]

    def start(self):
        namespace = self.service.new_session()
        return [namespace, *self.initialize(namespace)]

    def inject(self, namespace, scenario):
        try:
            result = self.service.session(namespace).inject(scenario)
            message = result["description"] + " Run probes to observe the impact."
        except ValueError as exc:
            message = str(exc)
        return [message, *self.views(namespace)]

    def probe(self, namespace, count):
        try:
            result = self.service.session(namespace).probe(int(count))
            message = f"Completed {result['probes']} probes; {result['successful']} succeeded. SLO history includes all requests."
        except ValueError as exc:
            message = str(exc)
        return [message, *self.views(namespace)]

    def investigate(self, namespace):
        try:
            report = self.service.investigate(namespace)
            proposal_id = report["proposal"]["id"] if report["proposal"] else ""
            trace = [[entry["step"], entry["tool"], entry["status"]] for entry in report["tool_trace"]]
            return [diagnosis_markdown(report), trace, report["proposal"] or {}, proposal_id,
                    "Investigation complete. Inspect its citations in the Telemetry tab.", *self.views(namespace)]
        except ValueError as exc:
            return [str(exc), [], {}, "", str(exc), *self.views(namespace)]

    def fix(self, namespace, proposal_id, approved, actor):
        try:
            result = self.service.session(namespace).fix(proposal_id, approved=approved, actor=actor)
            message = "Recovery verified with 20 probes. Historical error-budget usage remains." if result["verified"] else "Verification failed; the incident remains active."
            if result["replayed"]:
                message += f" Replayed {result['replayed']} buffered records."
        except ValueError as exc:
            message = str(exc)
        return [message, *self.views(namespace)]

    def investigate_ui(self, namespace):
        result = self.investigate(namespace)
        # Approval belongs to the newly proposed plan, never a previous plan.
        return [*result[:4], False, gr.update(interactive=bool(result[3])), *result[4:]]

    def fix_ui(self, namespace, proposal_id, approved, actor):
        result = self.fix(namespace, proposal_id, approved, actor)
        plan = self.service.store.get(namespace, "proposal", proposal_id) or {}
        waiting = plan.get("status") == "awaiting_approval"
        return [plan, proposal_id if waiting else "", gr.update(interactive=waiting), *result]

    def reset_ui(self, namespace):
        result = self.reset(namespace)
        return ["Run **Investigate incident** in Operations to see a report.", [], {}, "", False,
                gr.update(interactive=False), False, *result]

    def maintenance(self, namespace, enabled):
        self.service.session(namespace).maintenance(30 if enabled else 0)
        return ["Maintenance updated. Paging is suppressed during the window; failed requests still count toward SLOs.", *self.views(namespace)]

    def reset(self, namespace):
        self.service.session(namespace).reset()
        return ["Your lab was reset to a healthy synthetic baseline.", *self.views(namespace)]


def build_demo(service):
    presenter = Presenter(service)
    with gr.Blocks(title="GPU FleetOps · Reliability Lab", analytics_enabled=False) as demo:
        namespace = gr.State(value=None, time_to_live=service.settings.session_ttl_seconds)
        proposal_id = gr.State("")
        gr.HTML(HERO)
        cards = gr.HTML()
        status = gr.Markdown("Preparing your isolated lab…")
        state = gr.Markdown()
        with gr.Tabs():
            with gr.Tab("Reliability intelligence"):
                from .reliability.views import mount
                replay, replay_seed, replay_assets, replay_outputs = mount(service)
            with gr.Tab("Operations"):
                gr.HTML('<div class="step-strip"><span>01 · Inject</span><span>02 · Observe</span><span>03 · Investigate</span><span>04 · Approve</span><span>05 · Verify</span></div>')
                with gr.Row():
                    with gr.Column(scale=1):
                        scenario = gr.Dropdown(choices=[(label, fault.value) for fault, (label, _) in SCENARIOS.items()], value=Fault.GPU_OOM.value, label="Failure scenario")
                        inject = gr.Button("1. Inject fault", variant="secondary")
                        count = gr.Slider(minimum=10, maximum=100, step=10, value=40, label="Probes per run")
                        probes = gr.Button("2. Run probes", variant="primary")
                        investigate = gr.Button("3. Investigate incident", variant="secondary")
                        with gr.Accordion("Maintenance and reset", open=False):
                            maintenance = gr.Checkbox(label="Enable a 30-minute maintenance window", value=False)
                            reset = gr.Button("Reset my lab", variant="secondary")
                    with gr.Column(scale=3):
                        chart = gr.Plot(label="Service latency and failures")
                incidents = gr.Dataframe(headers=["Incident", "Status", "Owner", "Summary", "Grouped alerts", "Escalated"], interactive=False, wrap=True, label="Incident queue")
            with gr.Tab("Investigation & recovery"):
                gr.Markdown("The investigator reads evidence and proposes an allowed runbook action. Recovery is a separate operator step.")
                analysis = gr.Markdown("Run **Investigate incident** in Operations to see a report.")
                with gr.Row():
                    tool_trace = gr.Dataframe(headers=["Step", "Tool", "Result"], interactive=False, label="Tool execution trace")
                    proposal = gr.JSON(label="Recovery proposal")
                with gr.Row():
                    actor = gr.Textbox(value="demo-operator", label="Operator name")
                    approval = gr.Checkbox(value=False, label="I reviewed the evidence and approve this recovery")
                fix = gr.Button("4. Apply approved fix and verify", variant="primary", interactive=False)
                recovery = gr.Button("5. Run 80 healthy probes to watch burn rate recover", variant="secondary")
                gr.Markdown(f"**Investigator mode:** {'Live model with a bounded tool loop' if service.settings.ai_mode == 'live' else 'Deterministic rules baseline. Configure a server-side model provider to enable live agentic AI.'}")
            with gr.Tab("Fleet inventory"):
                gr.Markdown("Three illustrative environments share one catalog: cluster → node → GPU → service → owner. Provenance, stale records, and desired-state drift remain visible.")
                inventory = gr.Dataframe(headers=["Asset", "Type", "Environment", "Owner", "Source", "Driver", "Health", "Evidence type"], interactive=False, wrap=True)
            with gr.Tab("Telemetry & SLOs"):
                gr.Markdown("**Availability:** successful responses / all eligible requests, target 99.5%. **Latency:** successful responses within 300 ms / all requests, target 99%. Both use a rolling 30-day request window. No traffic means no data. Maintenance does not remove failed requests.")
                slo = gr.JSON(label="SLIs, budgets, and observed-window burn rates")
                evidence = gr.Dataframe(headers=["Evidence ID", "Type", "Signal", "Description", "Source"], interactive=False, wrap=True, label="Recent evidence")
                gr.Markdown("The full observability profile adds Grafana, Prometheus, Loki, Tempo, and an OpenTelemetry Collector. The app always exposes `/metrics`, `/healthz`, and `/readyz`.")
            with gr.Tab("Architecture"):
                gr.HTML('<div class="architecture">' + (Path(__file__).parent / "assets/architecture.svg").read_text() + '</div>')
                gr.Markdown("**Solid connections execute in this project.** The Docker observability profile exports logs and traces to external backends. Real GPU and Kubernetes adapters accept operator-authenticated discovery and telemetry. GPU health, service latency, and fleet environments in the public lab are simulated.")
            with gr.Tab("Incident report"):
                postmortem = gr.Markdown()
                gr.Markdown("Use this generated report to explain the trigger, evidence, routing, fix, and prevention task during an interview.")
        views = [cards, chart, incidents, inventory, evidence, slo, postmortem, state]
        options = {"api_visibility": "private", "concurrency_id": "fleetops-lab", "concurrency_limit": 4}
        demo.load(presenter.start, [], [namespace, status, *views], **options)
        demo.load(replay, [replay_seed, replay_assets], replay_outputs, api_visibility="private", concurrency_id="reliability", concurrency_limit=2)
        inject.click(presenter.inject, [namespace, scenario], [status, *views], **options)
        probes.click(presenter.probe, [namespace, count], [status, *views], **options)
        investigate.click(presenter.investigate_ui, [namespace], [analysis, tool_trace, proposal, proposal_id, approval, fix, status, *views], **options)
        fix.click(presenter.fix_ui, [namespace, proposal_id, approval, actor], [proposal, proposal_id, fix, status, *views], **options)
        recovery.click(lambda ns: presenter.probe(ns, 80), [namespace], [status, *views], **options)
        maintenance.change(presenter.maintenance, [namespace, maintenance], [status, *views], **options)
        reset.click(presenter.reset_ui, [namespace], [analysis, tool_trace, proposal, proposal_id, approval, fix, maintenance, status, *views], **options)
    demo.queue(max_size=32, default_concurrency_limit=4)
    return demo
