"""Gradio views use the same calculated evidence as CLI/API exports."""

import gradio as gr
import plotly.graph_objects as go

from .readiness import assess, sample_evidence
from .reporting import technical_report

COLORS = ["#0f8b73", "#ec8951", "#6a79c9", "#b45f83"]


def layout(fig, title, yaxis):
    fig.update_layout(
        title=title,
        height=340,
        template="plotly_white",
        font={"family": "Inter, sans-serif", "size": 12},
        margin={"l": 55, "r": 25, "t": 65, "b": 45},
        yaxis_title=yaxis,
        legend={"orientation": "h", "y": 1.05},
    )
    return fig


def cards(bundle):
    s = bundle["analysis"]["summary"]
    values = [
        ("Logical GPUs", f"{s['entities']:,}", "Three fictional cloud providers"),
        (
            "Interruption episodes",
            f"{s['interruptions']:,}",
            f"{s['raw_records']:,} source records normalized",
        ),
        (
            "Observed MTBI",
            f"{s['mtbi_hours']:,.1f} h" if s["mtbi_hours"] else "Insufficient data",
            "Operating GPU-hours / GPU episodes",
        ),
        ("Lost GPU-hours", f"{s['lost_hours']:,.1f}", "Overlapping downtime counted once"),
    ]
    return (
        '<div class="kpis">'
        + "".join(
            f'<div class="kpi"><div class="label">{label}</div><strong>{value}</strong><small>{note}</small></div>'
            for label, value, note in values
        )
        + "</div>"
    )


def figures(bundle):
    a = bundle["analysis"]
    cohort = go.Figure()
    for color, driver in zip(COLORS, ("stable", "candidate"), strict=False):
        rows = [r for r in a["cohorts"] if r["driver"] == driver]
        values = [r["per_1000_hours"] or 0 for r in rows]
        cohort.add_bar(
            name=driver,
            x=[r["provider"].replace("csp-", "") for r in rows],
            y=values,
            marker_color=color,
            error_y=dict(
                type="data",
                symmetric=False,
                array=[r["rate_ci95"][1] - v for r, v in zip(rows, values, strict=True)],
                arrayminus=[v - r["rate_ci95"][0] for r, v in zip(rows, values, strict=True)],
            ),
        )
    layout(
        cohort,
        "Driver interruption rates",
        "Interruptions / 1,000 GPU-hours",
    )
    pareto = go.Figure(
        go.Bar(
            x=[r["domain"] for r in a["pareto"]],
            y=[r["lost_hours"] for r in a["pareto"]],
            marker_color=COLORS,
        )
    )
    layout(pareto, "Lost time by failure domain", "Lost observed GPU-hours")
    survival = go.Figure()
    rows = a["survival"]
    x = [r["hours"] for r in rows]
    survival.add_scatter(
        x=x,
        y=[r["upper"] for r in rows],
        mode="lines",
        line={"width": 0, "shape": "hv"},
        showlegend=False,
    )
    survival.add_scatter(
        x=x,
        y=[r["lower"] for r in rows],
        mode="lines",
        fill="tonexty",
        fillcolor="rgba(15,139,115,.13)",
        line={"width": 0, "shape": "hv"},
        name="Pointwise 95% interval",
    )
    survival.add_scatter(
        x=x,
        y=[r["survival"] for r in rows],
        mode="lines",
        name="Kaplan–Meier",
        line={"color": COLORS[0], "shape": "hv", "width": 3},
    )
    layout(
        survival, "Time to first interruption", "Probability of no interruption"
    )
    survival.update_layout(xaxis_title="Observed operating hours", yaxis_range=[0, 1.02])
    experiment = go.Figure()
    for color, arm in zip(COLORS, ("control", "canary"), strict=False):
        rows = [bundle["experiment"]["phases"][phase][arm] for phase in ("before", "after")]
        experiment.add_bar(
            name=arm,
            x=["Before intervention", "Concurrent follow-up"],
            y=[r["per_1000_hours"] for r in rows],
            marker_color=color,
        )
    layout(
        experiment,
        "Randomized mitigation trial",
        "Interruptions / 1,000 GPU-hours",
    )
    prediction = go.Figure()
    for color, method in zip(COLORS, ("rules", "logistic"), strict=False):
        row = bundle["prediction"][method]
        prediction.add_bar(
            name=method,
            x=["Precision", "Recall"],
            y=[row["precision"], row["recall"]],
            marker_color=color,
        )
    layout(prediction, "Prediction on held-out devices", "Fraction")
    prediction.update_yaxes(range=[0, 1])
    return cohort, pareto, survival, experiment, prediction


def render(bundle):
    a = bundle["analysis"]
    patterns = [
        [
            p["domain"],
            p["classification"],
            p["episodes"],
            ", ".join(p["providers"]),
            p["explanation"],
        ]
        for p in a["patterns"]
    ]
    lean = {k: v for k, v in bundle.items() if k != "analysis"}
    lean["analysis"] = {
        k: v for k, v in a.items() if k not in {"episodes", "entity_metrics", "survival"}
    }
    cohort, pareto, survival, experiment, prediction = figures(bundle)
    return (
        cards(bundle),
        cohort,
        pareto,
        survival,
        patterns,
        experiment,
        prediction,
        technical_report(bundle),
        lean,
    )


def mount(service):
    gr.Markdown(
        "### GPU Fleet Reliability Intelligence\nMeasure interruptions, compare providers, and test a mitigation. Every chart uses a **synthetic controlled fleet**, with explicit exposure and source provenance."
    )
    with gr.Row():
        seed = gr.Number(value=2026, precision=0, minimum=0, maximum=2**32 - 1, label="Replay seed")
        assets = gr.Slider(minimum=60, maximum=1500, step=20, value=1000, label="Logical GPUs")
        run = gr.Button("Run reliability experiment", variant="primary")
    metrics = gr.HTML()
    with gr.Row():
        cohort = gr.Plot()
        pareto = gr.Plot()
    gr.Markdown(
        "Raw rates above are descriptive. Exact matching compares provider, rack, GPU model, firmware/configuration, workload and age. Shared rack failures violate independent-Poisson confidence assumptions."
    )
    patterns = gr.Dataframe(
        headers=[
            "Domain",
            "Candidate explanation",
            "GPU episodes",
            "Providers",
            "Evidence interpretation",
        ],
        wrap=True,
        interactive=False,
        label="Failure patterns and uncertainty",
    )
    with gr.Row():
        survival = gr.Plot()
        experiment = gr.Plot()
    with gr.Accordion("Predictive health: rules versus a trained model", open=False):
        prediction = gr.Plot()
        gr.Markdown(
            "Training/validation use two providers and earlier times. Testing holds out a third provider, later days and its devices. Normalization uses training data; threshold selection uses validation. Inspect false-alert rate and warning time in the evidence export."
        )
    with gr.Accordion("Hardware readiness: pass, fail and missing evidence", open=False):
        gr.Markdown(
            "Authored policy examples. Test an idle supported GPU with the documented local DCGM CLI. Physical GPU execution is unavailable in this recorded laptop run."
        )
        case = gr.Dropdown(
            ["pass", "fail", "incomplete"], value="incomplete", label="Diagnostic evidence example"
        )
        readiness = gr.JSON(value=assess(sample_evidence("incomplete")))
        case.change(
            lambda c: assess(sample_evidence(c)), [case], [readiness], api_visibility="private"
        )
    with gr.Accordion("Technical reliability review", open=False):
        review = gr.Markdown()
    with gr.Accordion("Inspect calculated evidence", open=False):
        evidence = gr.JSON()
    outputs = [
        metrics,
        cohort,
        pareto,
        survival,
        patterns,
        experiment,
        prediction,
        review,
        evidence,
    ]

    def replay(seed, assets):
        return render(service.reliability_replay(int(seed), int(assets)))

    run.click(
        replay,
        [seed, assets],
        outputs,
        api_visibility="private",
        concurrency_id="reliability",
        concurrency_limit=2,
    )
    return replay, seed, assets, outputs
