from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

from triage import __version__
from triage.ingest.routes import ingest_router
from triage.ingest.service import IngestService
from triage.ports.event_bus import EventBus
from triage.ports.store import Store
from triage.runtime import AppState

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    *,
    store: Store,
    bus: EventBus,
    ingest: IngestService,
    token: str,
    state: AppState,
    clock,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = store
        app.state.bus = bus
        app.state.ingest = ingest
        app.state.state = state
        app.state.clock = clock
        yield

    app = FastAPI(title="Triage", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.include_router(ingest_router(ingest, token))

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__}

    @app.get("/api/overview")
    def overview() -> dict[str, Any]:
        assets = store.list_assets()
        open_inc = sum(
            1
            for i in store.list_incidents()
            if i.status in {"open", "fixing", "needs_human"}
        )
        up = sum(1 for a in assets if a.status == "up")
        down = sum(1 for a in assets if a.status == "down")
        return {
            "open_incidents": open_inc,
            "assets_up": up,
            "assets_down": down,
            "event_rate_per_min": _rate(store, clock),
            "agent_busy": state.agent_busy,
        }

    @app.get("/api/assets")
    def assets() -> dict[str, Any]:
        return {"items": [a.to_api() for a in store.list_assets()]}

    @app.get("/api/events")
    def events(
        asset: str | None = None,
        level: str | None = None,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        asset_id = asset
        if asset:
            found = store.get_asset(asset) or store.get_asset_by_name(asset)
            asset_id = found.id if found else asset
        items, total = store.list_events(
            asset_id=asset_id, level=level, limit=limit, offset=offset
        )
        return {"items": [e.to_api() for e in items], "total": total}

    @app.get("/api/incidents")
    def incidents() -> dict[str, Any]:
        return {"items": [i.to_api() for i in store.list_incidents()]}

    @app.get("/api/incidents/{incident_id}")
    def incident_detail(incident_id: str) -> dict[str, Any]:
        incident = store.get_incident(incident_id)
        if incident is None:
            raise HTTPException(404, "incident not found")
        events = store.events_for_fingerprint(incident.fingerprint, limit=100)
        actions = store.list_actions(incident_id)
        report = store.get_report_for_incident(incident_id)
        payload = incident.to_api()
        payload["events"] = [e.to_api() for e in events]
        payload["actions"] = [a.to_api() for a in actions]
        payload["report_path"] = report.path if report else None
        return payload

    @app.get("/api/terminals")
    def terminals() -> dict[str, Any]:
        items = state.terminal_items()
        if items:
            return {"items": items}
        derived = []
        for asset in store.list_assets():
            if asset.kind in {"process", "terminal"}:
                derived.append(
                    {
                        "id": asset.id,
                        "name": asset.name,
                        "asset_id": asset.id,
                        "alive": asset.status == "up",
                        "last_lines": [],
                    }
                )
        return {"items": derived}

    @app.get("/api/telemetry")
    def telemetry() -> dict[str, Any]:
        recent, _ = store.list_events(limit=20, offset=0)
        heartbeats = [e.to_api() for e in recent if e.source == "heartbeat"]
        if not heartbeats:
            heartbeats = [
                {
                    "hostname": h,
                    "last_seen": row.get("last_seen"),
                    "event_count": row.get("event_count"),
                }
                for h, row in state.collectors.items()
            ]
        return {
            "heartbeats": heartbeats,
            "health": list(state.health.values()),
            "collectors": [
                {
                    "hostname": h,
                    "last_seen": row.get("last_seen"),
                    "event_count": row.get("event_count"),
                }
                for h, row in state.collectors.items()
            ],
            "event_rate_per_min": _rate(store, clock),
        }

    @app.get("/api/stream")
    async def stream() -> StreamingResponse:
        q = bus.subscribe()

        async def gen():
            try:
                yield "event: ping\ndata: {}\n\n"
                while True:
                    topic, data = await q.get()
                    yield f"event: {topic}\ndata: {json.dumps(data)}\n\n"
            finally:
                bus.unsubscribe(q)

        return StreamingResponse(gen(), media_type="text/event-stream")

    # SPA: files under static/, else index.html. /api/* and /ingest stay JSON.
    @app.get("/{full_path:path}")
    def spa(full_path: str):
        path = "/" + full_path
        if (
            path == "/api"
            or path.startswith("/api/")
            or path == "/ingest"
            or path.startswith("/ingest/")
        ):
            raise HTTPException(404, "not found")
        index = STATIC_DIR / "index.html"
        if not STATIC_DIR.is_dir() or not index.is_file():
            return HTMLResponse("Triage is running")
        candidate = (STATIC_DIR / full_path).resolve() if full_path else index
        try:
            candidate.relative_to(STATIC_DIR)
        except ValueError:
            return _static_file(index)
        if candidate.is_file():
            return _static_file(candidate)
        return _static_file(index)

    return app


def _static_file(path: Path) -> FileResponse:
    response = FileResponse(path)
    if path.suffix in {".js", ".css", ".html"}:
        response.headers["Cache-Control"] = "no-store"
    return response


def _rate(store: Store, clock) -> float:
    since = clock.now() - timedelta(seconds=60)
    return float(len(store.events_since(since)))
