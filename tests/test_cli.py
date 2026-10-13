import sys

from fleetops.__main__ import main


def test_cli_starts_fastapi_factory(monkeypatch):
    recorded = {}
    monkeypatch.setattr(sys, "argv", ["fleetops", "--host", "127.0.0.1", "--port", "9876"])
    monkeypatch.setattr("fleetops.__main__.uvicorn.run", lambda *args, **kwargs: recorded.update({"app": args[0], **kwargs}))
    main()
    assert recorded == {"app": "fleetops.api:create_app", "factory": True, "host": "127.0.0.1", "port": 9876}


def test_share_cli_uses_isolated_gradio_ui_and_closes_service(monkeypatch):
    import gradio as gr

    from fleetops.service import FleetOps
    recorded = {}
    monkeypatch.setattr(sys, "argv", ["fleetops", "--share", "--port", "9877"])
    monkeypatch.setenv("FLEETOPS_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(gr.Blocks, "launch", lambda self, **kwargs: recorded.update(kwargs))
    monkeypatch.setattr(FleetOps, "close", lambda self: recorded.update(closed=True))
    main()
    assert recorded["share"]
    assert recorded["server_port"] == 9877
    assert not recorded["run_history"]
    assert recorded["closed"]
