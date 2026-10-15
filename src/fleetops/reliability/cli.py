"""Run with python -m fleetops.reliability.cli; no model or GPU needed for replay."""

import argparse
import json
from pathlib import Path

from .analysis import analyze
from .contracts import Dataset
from .readiness import DiagnosticEvidence, assess, run_local
from .reporting import save_bundle


def main():
    parser = argparse.ArgumentParser(description="GPU fleet reliability intelligence")
    sub = parser.add_subparsers(dest="command", required=True)
    replay = sub.add_parser("replay", help="Build a reproducible synthetic evidence bundle")
    replay.add_argument("--seed", type=int, default=2026)
    replay.add_argument("--assets", type=int, default=1000)
    replay.add_argument("--output", type=Path, default=Path("reports/reliability"))
    analysis = sub.add_parser("analyze", help="Analyze a canonical operator-supplied dataset")
    analysis.add_argument("input", type=Path)
    analysis.add_argument("--unit", choices=["gpu", "node", "job"], default="gpu")
    analysis.add_argument("--output", type=Path, required=True)
    readiness = sub.add_parser("readiness", help="Assess a canonical diagnostic evidence envelope")
    readiness.add_argument("input", type=Path)
    readiness.add_argument("--output", type=Path, required=True)
    live = sub.add_parser("diagnose", help="Opt-in active tests on an idle local NVIDIA GPU")
    live.add_argument("--execute", action="store_true")
    live.add_argument("--idle-confirmed", action="store_true")
    live.add_argument("--gpu", type=int, default=0)
    live.add_argument("--output", type=Path, default=Path("reports/live-readiness"))
    args = parser.parse_args()
    if args.command == "replay":
        result = save_bundle(args.output, args.seed, args.assets)
        print(
            json.dumps(
                dict(
                    output=str(args.output),
                    summary=result["analysis"]["summary"],
                    execution=result["execution"],
                ),
                indent=2,
            )
        )
        return
    if args.command == "diagnose":
        print(
            json.dumps(
                run_local(
                    args.output,
                    execute=args.execute,
                    idle_confirmed=args.idle_confirmed,
                    gpu=args.gpu,
                ),
                indent=2,
            )
        )
        return
    if args.command == "analyze":
        result = analyze(Dataset.model_validate_json(args.input.read_text()), args.unit)
    else:
        result = assess(DiagnosticEvidence.model_validate_json(args.input.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                output=str(args.output),
                status=result.get("status", result.get("summary", {}).get("status")),
            )
        )
    )


if __name__ == "__main__":
    main()
