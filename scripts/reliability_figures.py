"""Export publication figures with Matplotlib; architecture is a code-native SVG."""

import argparse
import json
from html import escape
from pathlib import Path


def architecture(path):
    cards = [
        (
            "01 / SOURCES",
            [
                (
                    "Fictional CSP adapters",
                    "Aurora · Borealis · Cirrus",
                    "Explicit units and source IDs",
                ),
                (
                    "Live inputs when available",
                    "DCGM telemetry · local diagnostics",
                    "Raw evidence and software versions",
                ),
            ],
        ),
        (
            "02 / MEASUREMENT",
            [
                (
                    "Interruption episodes",
                    "Merge duplicate and overlapping logs",
                    "Keep shared incident identities",
                ),
                (
                    "Operating exposure",
                    "Separate GPU, node and job hours",
                    "Exclude maintenance and unknown time",
                ),
            ],
        ),
        (
            "03 / INTELLIGENCE",
            [
                (
                    "Statistical reliability",
                    "Pareto · Kaplan–Meier · Weibull",
                    "Matched cohorts and uncertainty",
                ),
                (
                    "Controlled experiments",
                    "Randomized canary and control",
                    "Held-out prediction benchmark",
                ),
            ],
        ),
        (
            "04 / DECISIONS",
            [
                (
                    "Evidence for engineers",
                    "Gradio · API · exported JSON",
                    "Technical and executive reports",
                ),
                (
                    "Readiness before rollout",
                    "Versioned lab acceptance policy",
                    "Pass · fail · insufficient evidence",
                ),
            ],
        ),
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="850" viewBox="0 0 1440 850" role="img" aria-labelledby="title desc">',
        '<title id="title">GPU Fleet Reliability Intelligence architecture</title><desc id="desc">Sources flow through interruption measurement and reliability analysis to engineering decisions. Live hardware remains an explicit optional input.</desc>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#72d9b4"/></marker></defs>',
        '<rect width="1440" height="850" rx="24" fill="#101d33"/>',
        '<g font-family="Arial, sans-serif">',
        '<text x="55" y="65" fill="#72d9b4" font-size="15" letter-spacing="3">GPU FLEETOPS / RELIABILITY INTELLIGENCE</text>',
        '<text x="55" y="120" fill="#ffffff" font-size="40" font-weight="700">From fleet evidence to a reliability decision.</text>',
        '<text x="55" y="158" fill="#b4c5d8" font-size="19">A reproducible lab for measuring interruptions, separating failure patterns, and evaluating a fix.</text>',
    ]
    for col, (label, boxes) in enumerate(cards):
        x = 55 + col * 345
        parts.append(
            f'<text x="{x}" y="222" fill="#72d9b4" font-size="14" letter-spacing="1">{label}</text>'
        )
        for row, (title, a, b) in enumerate(boxes):
            y = 250 + row * 170
            parts += [
                f'<rect x="{x}" y="{y}" width="305" height="140" rx="13" fill="#1a2b43" stroke="#35516c"/>',
                f'<text x="{x + 20}" y="{y + 38}" fill="#ffffff" font-size="20" font-weight="700">{escape(title)}</text>',
                f'<text x="{x + 20}" y="{y + 77}" fill="#b4c5d8" font-size="15">{escape(a)}</text>',
                f'<text x="{x + 20}" y="{y + 104}" fill="#b4c5d8" font-size="15">{escape(b)}</text>',
            ]
        if col < 3:
            parts.append(
                f'<path d="M {x + 311} 397 L {x + 337} 397" stroke="#72d9b4" stroke-width="2" marker-end="url(#arrow)"/>'
            )
    parts += [
        '<rect x="55" y="625" width="1330" height="152" rx="15" fill="#153c3c" stroke="#307264"/>',
        '<text x="80" y="663" fill="#a6f4d5" font-size="20" font-weight="700">The evidence stays inspectable.</text>',
        '<text x="80" y="703" fill="#d4ede7" font-size="17">Provenance → explicit denominators → source-linked hypotheses → controlled validation → recorded decision</text>',
        '<text x="80" y="741" fill="#a8cfc4" font-size="15">Synthetic replay demonstrates methodology. Physical GPU results require actual hardware. LLMs do not calculate reliability statistics.</text>',
        '<text x="55" y="818" fill="#90a8bf" font-size="13">Python · PostgreSQL / SQLite · SciPy · Prometheus · OpenTelemetry · Plotly · Gradio</text>',
        "</g></svg>",
    ]
    path.write_text("\n".join(parts))


def timeline(path):
    chunks = [
        (0, 2, "Operating", "#248d78"),
        (2, 4, "Maintenance", "#8795b1"),
        (4, 5, "Operating", "#248d78"),
        (5, 6, "Interrupted", "#e78c55"),
        (6, 8, "Unknown", "#655f94"),
        (8, 10, "Operating", "#248d78"),
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="370" viewBox="0 0 1200 370"><rect width="1200" height="370" rx="18" fill="#f5f8fb"/><g font-family="Arial,sans-serif"><text x="45" y="55" font-size="27" fill="#142b40" font-weight="700">An explicit exposure clock</text><text x="45" y="90" font-size="17" fill="#53667b">An interruption spans hours 5–7. Coverage becomes unknown at hour 6.</text>'
    ]
    for a, b, label, color in chunks:
        x = 45 + a * 110
        parts += [
            f'<rect x="{x}" y="135" width="{(b - a) * 110 - 3}" height="68" rx="5" fill="{color}"/>',
            f'<text x="{x + 8}" y="176" fill="#ffffff" font-size="14">{label}</text>',
        ]
    for i in range(11):
        parts.append(f'<text x="{45 + i * 110}" y="230" fill="#53667b" font-size="15">{i} h</text>')
    parts += [
        '<text x="45" y="290" fill="#142b40" font-size="22" font-weight="700">5 operating hours / 1 interruption = 5 hours observed MTBI</text>',
        '<text x="45" y="327" fill="#53667b" font-size="17">2 maintenance hours + 2 unknown hours + 1 observed lost hour are excluded from operating exposure.</text>',
        "</g></svg>",
    ]
    path.write_text("\n".join(parts))


def plots(bundle, directory):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    a = bundle["analysis"]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#3a516b",
            "text.color": "#152c43",
            "axes.titleweight": "bold",
        }
    )
    fig, axs = plt.subplots(2, 2, figsize=(15, 10), layout="constrained")
    providers = sorted({r["provider"] for r in a["cohorts"]})
    x = np.arange(len(providers))
    for offset, driver, color in [(-0.18, "stable", "#138b73"), (0.18, "candidate", "#e78c55")]:
        rows = [
            next(r for r in a["cohorts"] if r["provider"] == p and r["driver"] == driver)
            for p in providers
        ]
        y = [r["per_1000_hours"] for r in rows]
        axs[0, 0].bar(
            x + offset,
            y,
            0.34,
            label=driver,
            color=color,
            yerr=[
                [v - r["rate_ci95"][0] for v, r in zip(y, rows, strict=True)],
                [r["rate_ci95"][1] - v for v, r in zip(y, rows, strict=True)],
            ],
            capsize=3,
        )
    axs[0, 0].set(
        xticks=x,
        xticklabels=[p.replace("csp-", "").title() for p in providers],
        ylabel="Interruptions / 1,000 GPU-hours",
        title="Compare driver cohorts across providers",
    )
    axs[0, 0].legend(frameon=False)
    axs[0, 1].bar(
        [r["domain"] for r in a["pareto"]],
        [r["lost_hours"] for r in a["pareto"]],
        color=["#138b73", "#e78c55", "#7686cb", "#a5678e", "#b6bec8"],
    )
    axs[0, 1].set(ylabel="Lost observed GPU-hours", title="Prioritize by lost time")
    rows = a["survival"]
    x = [r["hours"] for r in rows]
    axs[1, 0].step(x, [r["survival"] for r in rows], where="post", color="#138b73", lw=2)
    axs[1, 0].fill_between(
        x,
        [r["lower"] for r in rows],
        [r["upper"] for r in rows],
        step="post",
        alpha=0.15,
        color="#138b73",
    )
    axs[1, 0].set(
        xlabel="Observed operating hours",
        ylabel="Probability of no interruption",
        ylim=(0, 1.02),
        title="Time to first interruption · right-censored",
    )
    x = np.arange(2)
    for offset, arm, color in [(-0.18, "control", "#138b73"), (0.18, "canary", "#e78c55")]:
        vals = [
            bundle["experiment"]["phases"][p][arm]["per_1000_hours"] for p in ("before", "after")
        ]
        axs[1, 1].bar(x + offset, vals, 0.34, label=arm, color=color)
    axs[1, 1].set(
        xticks=x,
        xticklabels=["Before intervention", "Concurrent follow-up"],
        ylabel="Interruptions / 1,000 GPU-hours",
        title="Evaluate a randomized mitigation",
    )
    axs[1, 1].legend(frameon=False)
    fig.suptitle(
        f"GPU Fleet Reliability Intelligence\nSynthetic replay · {a['summary']['entities']:,} logical GPUs · seed {bundle['ground_truth']['seed']}",
        fontsize=20,
        fontweight="bold",
    )
    for ax in axs.flat:
        ax.grid(axis="y", alpha=0.15)
        ax.set_axisbelow(True)
    for extension in ("svg", "png"):
        fig.savefig(directory / f"reliability-results.{extension}", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path("reports/reliability/bundle.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/reliability/figures"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    architecture(args.output / "architecture.svg")
    timeline(args.output / "exposure-clock.svg")
    plots(json.loads(args.report.read_text()), args.output)
