"""CLI entrypoint."""

import argparse
import os

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run the GPU FleetOps Gradio reliability lab")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "7860")))
    parser.add_argument("--share", action="store_true", help="Create a temporary public Gradio link for the isolated simulation UI")
    args = parser.parse_args()
    if args.share:
        import gradio as gr

        from .config import Settings
        from .service import FleetOps
        from .ui import CSS, build_demo
        service = FleetOps(Settings.from_env())
        try:
            build_demo(service).launch(server_name=args.host, server_port=args.port, share=True,
                                       css=CSS, theme=gr.themes.Soft(primary_hue="emerald", secondary_hue="slate", neutral_hue="slate"),
                                       footer_links=[], show_error=False, run_history=False)
        finally:
            service.close()
        return
    uvicorn.run("fleetops.api:create_app", factory=True, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
