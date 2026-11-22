from datetime import datetime, timezone
from pathlib import Path

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


def _client(tmp_path: Path, token: str = "test-token") -> TestClient:
    store = SqliteStore(tmp_path / "triage.db")
    clock = FrozenClock()
    bus = MemoryEventBus()
    state = AppState()
    ingest = IngestService(store, clock, bus, state=state)
    app = create_app(
        store=store, bus=bus, ingest=ingest, token=token, state=state, clock=clock
    )
    return TestClient(app)


def test_dashboard_health_and_api(tmp_path):
    client = _client(tmp_path)
    home = client.get("/")
    assert home.status_code == 200
    assert "Triage" in home.text
    assert "Overview" in home.text
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
