import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from triage.adapters.memory_bus import MemoryEventBus
from triage.adapters.sqlite_store import SqliteStore
from triage.ingest.service import IngestService
from triage.ports.clock import Clock
from triage.runtime import AppState
from triage.web.app import create_app


class FrozenClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _build(tmp_path: Path, token: str = "test-token"):
    store = SqliteStore(tmp_path / "triage.db")
    clock = FrozenClock()
    bus = MemoryEventBus()
    state = AppState()
    ingest = IngestService(store, clock, bus, state=state)
    app = create_app(
        store=store, bus=bus, ingest=ingest, token=token, state=state, clock=clock
    )
    return app, store


def _client(tmp_path: Path, token: str = "test-token") -> TestClient:
    app, _store = _build(tmp_path, token)
    return TestClient(app)


def test_dashboard_health_and_api(tmp_path):
    client = _client(tmp_path)
    home = client.get("/")
    assert home.status_code == 200
    assert "Triage" in home.text
    for name in (
        "Overview",
        "Systems",
        "Terminals",
        "Events",
        "Incidents",
        "Telemetry",
    ):
        assert name in home.text, name
    css = client.get("/styles.css")
    assert css.status_code == 200
    spa = client.get("/not-a-route")
    assert spa.status_code == 200
    assert "Triage" in spa.text
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert "version" in body
    missing = client.get("/api/does-not-exist")
    assert missing.status_code == 404
    for path in (
        "/api/overview",
        "/api/assets",
        "/api/events",
        "/api/incidents",
        "/api/terminals",
        "/api/telemetry",
    ):
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.headers["content-type"].startswith("application/json")


def test_ingest_requires_auth_and_opens_incident(tmp_path):
    client = _client(tmp_path)
    body = {
        "events": [{"level": "error", "source": "app", "message": "ValueError: boom"}]
    }
    assert client.post("/ingest", json=body).status_code == 401
    r = client.post(
        "/ingest", json=body, headers={"Authorization": "Bearer test-token"}
    )
    assert r.status_code == 200
    incidents = client.get("/api/incidents").json()["items"]
    assert len(incidents) == 1
    detail = client.get(f"/api/incidents/{incidents[0]['id']}")
    assert detail.status_code == 200
    assert "events" in detail.json() and "actions" in detail.json()
    r2 = client.post(
        "/ingest", json=body, headers={"Authorization": "Bearer test-token"}
    )
    assert r2.status_code == 200
    assert len(client.get("/api/incidents").json()["items"]) == 1


def test_ingest_heartbeat_and_deploy(tmp_path):
    client = _client(tmp_path)
    auth = {"Authorization": "Bearer test-token"}
    assert (
        client.post(
            "/ingest", json={"type": "heartbeat", "hostname": "box1"}, headers=auth
        ).status_code
        == 200
    )
    failed = client.post(
        "/ingest",
        json={"type": "deploy", "status": "failed", "sha": "abc", "env": "prod"},
        headers=auth,
    )
    assert failed.status_code == 200
    items = client.get("/api/incidents").json()["items"]
    assert any(i["severity"] == "critical" for i in items)


def test_needs_human_duplicate_does_not_open_second(tmp_path):
    app, store = _build(tmp_path)
    client = TestClient(app)
    auth = {"Authorization": "Bearer test-token"}
    body = {
        "events": [{"level": "error", "source": "app", "message": "ValueError: boom"}]
    }
    assert client.post("/ingest", json=body, headers=auth).status_code == 200
    first = client.get("/api/incidents").json()["items"][0]
    store.update_incident(first["id"], status="needs_human", escalate_reason="human")
    assert client.post("/ingest", json=body, headers=auth).status_code == 200
    items = client.get("/api/incidents").json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == first["id"]


def test_live_uvicorn_endpoints(tmp_path):
    import uvicorn

    app, _store = _build(tmp_path)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    host, port = sock.getsockname()
    sock.close()
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://{host}:{port}"
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                if httpx.get(f"{base}/api/health", timeout=0.4).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.05)
        else:
            raise AssertionError("uvicorn did not start")
        spa = httpx.get(f"{base}/", timeout=2.0)
        assert spa.status_code == 200
        for name in (
            "Overview",
            "Systems",
            "Terminals",
            "Events",
            "Incidents",
            "Telemetry",
        ):
            assert name in spa.text
        css = httpx.get(f"{base}/styles.css", timeout=2.0)
        assert css.status_code == 200
        assert '[data-theme="dark"]' in css.text
        assert '[data-theme="light"]' in css.text
        for path in (
            "/api/overview",
            "/api/assets",
            "/api/events",
            "/api/incidents",
            "/api/terminals",
            "/api/telemetry",
            "/api/health",
        ):
            r = httpx.get(f"{base}{path}", timeout=2.0)
            assert r.status_code == 200, path
        body = {"events": [{"level": "error", "source": "app", "message": "boom"}]}
        assert httpx.post(f"{base}/ingest", json=body, timeout=2.0).status_code == 401
        ok = httpx.post(
            f"{base}/ingest",
            json=body,
            headers={"Authorization": "Bearer test-token"},
            timeout=2.0,
        )
        assert ok.status_code == 200
    finally:
        server.should_exit = True
        thread.join(timeout=3)
