"""Authenticated operator API plus the public, isolated Gradio simulation."""

import hmac
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from .adapters import parse_kubernetes_nodes
from .config import Settings
from .models import (
    AlertRequest,
    AssetSnapshot,
    Contract,
    DCGMRequest,
    FaultRequest,
    FixRequest,
    MaintenanceRequest,
    ProbeRequest,
)
from .service import FleetOps
from .store import ConflictError


class KubernetesRequest(Contract):
    document: dict
    cluster_id: str = Field(min_length=1, max_length=120)
    environment: str = "on-prem"


def create_app(settings: Settings | None = None, *, mount_ui: bool = True) -> FastAPI:
    service = FleetOps(settings or Settings.from_env())

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.close()

    app = FastAPI(title="GPU FleetOps", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
    app.state.service = service

    def operator(authorization: str = Header(default="")):
        if not service.settings.api_token:
            raise HTTPException(503, "Operator API is disabled; configure FLEETOPS_API_TOKEN on the server")
        expected = "Bearer " + service.settings.api_token
        if not hmac.compare_digest(authorization.encode(), expected.encode()):
            raise HTTPException(401, "A valid operator bearer token is required")

    def lab(x_fleetops_session: str = Header(...), _=Depends(operator)):
        return service.session(x_fleetops_session)

    @app.exception_handler(ConflictError)
    async def conflict(request: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.middleware("http")
    async def request_metrics(request, call_next):
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", "/demo")
        if path not in {"/metrics", "/healthz", "/readyz"}:
            service.telemetry.api_requests.labels(path if path.startswith("/api/") else "/demo", str(response.status_code)).inc()
        return response

    @app.get("/healthz")
    def health():
        return {"status": "ok", "version": "1.0.0", "mode": "simulation"}

    @app.get("/readyz")
    def ready():
        with service.store.engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(service.telemetry.exposition(), media_type="text/plain; version=0.0.4")

    @app.post("/api/v1/sessions", dependencies=[Depends(operator)], status_code=201)
    def new_session():
        return {"session_id": service.new_session(), "mode": "simulation"}

    @app.get("/api/v1/summary")
    def summary(current=Depends(lab)):
        return current.summary()

    @app.get("/api/v1/inventory")
    def inventory(current=Depends(lab)):
        return current.inventory.all(current.now)

    @app.post("/api/v1/inventory")
    def discover(snapshot: AssetSnapshot, current=Depends(lab)):
        with current.lock:
            return current.inventory.reconcile(snapshot, current.now)

    @app.post("/api/v1/integrations/kubernetes")
    def kubernetes(payload: KubernetesRequest, current=Depends(lab)):
        snapshots = parse_kubernetes_nodes(payload.document, cluster_id=payload.cluster_id,
                                           environment=payload.environment, observed_at=current.now)
        with current.lock:
            return {"results": [current.inventory.reconcile(snapshot, current.now) for snapshot in snapshots]}

    @app.post("/api/v1/integrations/dcgm")
    def dcgm(payload: DCGMRequest, current=Depends(lab)):
        return current.ingest_dcgm(payload.exposition)

    @app.post("/api/v1/faults")
    def inject(payload: FaultRequest, current=Depends(lab)):
        return current.inject(payload.fault)

    @app.post("/api/v1/probes")
    def probes(payload: ProbeRequest, current=Depends(lab)):
        return current.probe(payload.count, payload.text)

    @app.post("/api/v1/maintenance")
    def maintenance(payload: MaintenanceRequest, current=Depends(lab)):
        return current.maintenance(payload.minutes)

    @app.get("/api/v1/slo")
    def slo(current=Depends(lab)):
        return current.slo()

    @app.get("/api/v1/incidents")
    def incidents(current=Depends(lab)):
        return current.incidents()

    @app.post("/api/v1/alerts")
    def alert(payload: AlertRequest, current=Depends(lab)):
        return current.emit_alert(payload.fingerprint, payload.summary, payload.evidence_ids, service_id=payload.service_id)

    @app.post("/api/v1/incidents/{incident_id}/investigate")
    def investigate(incident_id: str, current=Depends(lab)):
        return service.investigator.investigate(current, incident_id)

    @app.post("/api/v1/recovery")
    def recover(payload: FixRequest, current=Depends(lab)):
        return current.fix(payload.proposal_id, approved=payload.approved, actor=payload.actor)

    @app.get("/api/v1/incidents/{incident_id}/postmortem", response_class=PlainTextResponse)
    def postmortem(incident_id: str, current=Depends(lab)):
        return current.postmortem(incident_id)

    @app.get("/api/v1/evidence")
    def evidence(current=Depends(lab)):
        return current.store.list(current.namespace, "evidence", limit=100)

    app.mount("/assets", StaticFiles(directory=Path(__file__).parent / "assets"), name="assets")
    if mount_ui:
        import gradio as gr

        from .ui import CSS, build_demo
        blocks = build_demo(service)
        app = gr.mount_gradio_app(app, blocks, path="/", footer_links=[], run_history=False, css=CSS,
                                  theme=gr.themes.Soft(primary_hue="emerald", secondary_hue="slate", neutral_hue="slate"),
                                  show_error=False)
        app.state.service = service
        app.state.demo = blocks
    return app
