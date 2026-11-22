from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from triage.domain.entities import (
    Action,
    Asset,
    Event,
    Incident,
    Report,
    parse_iso,
    to_iso,
)
from triage.ports.store import Store, StoreError

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}',
    last_seen TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    asset_id TEXT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    source TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    message TEXT NOT NULL,
    body TEXT,
    meta_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    event_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    resolved_at TEXT,
    escalate_reason TEXT
);
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    role TEXT NOT NULL,
    name TEXT NOT NULL,
    input_json TEXT NOT NULL DEFAULT '{}',
    output TEXT,
    ok INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (incident_id) REFERENCES incidents(id)
);
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    path TEXT NOT NULL,
    emailed_to TEXT,
    emailed_at TEXT,
    fingerprint TEXT,
    severity TEXT,
    FOREIGN KEY (incident_id) REFERENCES incidents(id)
);
CREATE INDEX IF NOT EXISTS idx_events_fp ON events(fingerprint);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_incidents_fp ON incidents(fingerprint);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
"""


def _id() -> str:
    return uuid.uuid4().hex


def _dumps(meta: dict[str, Any] | None) -> str:
    return json.dumps(meta or {}, default=str)


def _loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


class SqliteStore(Store):
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def upsert_asset(
        self,
        *,
        kind: str,
        name: str,
        source: str,
        status: str,
        meta: dict[str, Any] | None = None,
        last_seen: datetime | None = None,
        asset_id: str | None = None,
    ) -> Asset:
        now = last_seen
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM assets WHERE name = ?", (name,)
            ).fetchone()
            if row:
                merged = {**_loads(row["meta_json"]), **(meta or {})}
                self._conn.execute(
                    """UPDATE assets SET kind=?, source=?, status=?, meta_json=?, last_seen=? WHERE id=?""",
                    (
                        kind or row["kind"],
                        source or row["source"],
                        status,
                        _dumps(merged),
                        to_iso(now) or row["last_seen"],
                        row["id"],
                    ),
                )
                self._conn.commit()
                return self.get_asset(row["id"])  # type: ignore[return-value]
            aid = asset_id or _id()
            created = to_iso(now) or to_iso(datetime.now(timezone.utc))
            self._conn.execute(
                """INSERT INTO assets (id, kind, name, source, status, meta_json, last_seen, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    aid,
                    kind,
                    name,
                    source,
                    status,
                    _dumps(meta),
                    to_iso(now) or created,
                    created,
                ),
            )
            self._conn.commit()
            return self.get_asset(aid)  # type: ignore[return-value]

    def get_asset(self, asset_id: str) -> Asset | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM assets WHERE id = ?", (asset_id,)
            ).fetchone()
        return _asset(row) if row else None

    def get_asset_by_name(self, name: str) -> Asset | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM assets WHERE name = ?", (name,)
            ).fetchone()
        return _asset(row) if row else None

    def list_assets(self) -> list[Asset]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM assets ORDER BY name").fetchall()
        return [_asset(r) for r in rows]

    def insert_event(self, event: Event) -> Event:
        if not event.id:
            event.id = _id()
        with self._lock:
            self._conn.execute(
                """INSERT INTO events (id, asset_id, ts, level, source, fingerprint, message, body, meta_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.id,
                    event.asset_id,
                    to_iso(event.ts),
                    event.level,
                    event.source,
                    event.fingerprint,
                    event.message,
                    event.body or "",
                    _dumps(event.meta),
                ),
            )
            self._conn.commit()
        return event

    def get_event(self, event_id: str) -> Event | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
        return _event(row) if row else None

    def list_events(
        self,
        *,
        asset_id: str | None = None,
        level: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        where = []
        args: list[Any] = []
        if asset_id:
            where.append("asset_id = ?")
            args.append(asset_id)
        if level:
            where.append("level = ?")
            args.append(level)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        with self._lock:
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM events {clause}", args
            ).fetchone()[0]
            rows = self._conn.execute(
                f"SELECT * FROM events {clause} ORDER BY ts DESC LIMIT ? OFFSET ?",
                [*args, limit, offset],
            ).fetchall()
        return [_event(r) for r in rows], int(total)

    def events_since(self, ts: datetime) -> list[Event]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE ts >= ? ORDER BY ts DESC", (to_iso(ts),)
            ).fetchall()
        return [_event(r) for r in rows]

    def insert_incident(self, incident: Incident) -> Incident:
        if not incident.id:
            incident.id = _id()
        with self._lock:
            self._conn.execute(
                """INSERT INTO incidents
                   (id, fingerprint, title, severity, status, event_id, started_at, resolved_at, escalate_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    incident.id,
                    incident.fingerprint,
                    incident.title,
                    incident.severity,
                    incident.status,
                    incident.event_id,
                    to_iso(incident.started_at),
                    to_iso(incident.resolved_at),
                    incident.escalate_reason,
                ),
            )
            self._conn.commit()
        return incident

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM incidents WHERE id = ?", (incident_id,)
            ).fetchone()
        return _incident(row) if row else None

    def list_incidents(self) -> list[Incident]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM incidents ORDER BY started_at DESC"
            ).fetchall()
        return [_incident(r) for r in rows]

    def get_open_by_fingerprint(self, fingerprint: str) -> Incident | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM incidents WHERE fingerprint = ? AND status IN ('open','fixing') ORDER BY started_at DESC LIMIT 1",
                (fingerprint,),
            ).fetchone()
        return _incident(row) if row else None

    def last_resolved_by_fingerprint(self, fingerprint: str) -> Incident | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM incidents WHERE fingerprint = ? AND status = 'resolved' ORDER BY resolved_at DESC LIMIT 1",
                (fingerprint,),
            ).fetchone()
        return _incident(row) if row else None

    def update_incident(
        self,
        incident_id: str,
        *,
        status: str | None = None,
        severity: str | None = None,
        resolved_at: datetime | None = None,
        escalate_reason: str | None = None,
        title: str | None = None,
    ) -> Incident:
        current = self.get_incident(incident_id)
        if current is None:
            raise StoreError(f"incident {incident_id} not found")
        fields = {
            "status": status if status is not None else current.status,
            "severity": severity if severity is not None else current.severity,
            "resolved_at": to_iso(resolved_at)
            if resolved_at is not None
            else to_iso(current.resolved_at),
            "escalate_reason": escalate_reason
            if escalate_reason is not None
            else current.escalate_reason,
            "title": title if title is not None else current.title,
        }
        with self._lock:
            self._conn.execute(
                """UPDATE incidents SET status=?, severity=?, resolved_at=?, escalate_reason=?, title=? WHERE id=?""",
                (
                    fields["status"],
                    fields["severity"],
                    fields["resolved_at"],
                    fields["escalate_reason"],
                    fields["title"],
                    incident_id,
                ),
            )
            self._conn.commit()
        updated = self.get_incident(incident_id)
        if updated is None:
            raise StoreError(f"incident {incident_id} vanished")
        return updated

    def count_agent_active(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM incidents WHERE status IN ('open','fixing')"
            ).fetchone()
        return int(row[0])

    def insert_action(self, action: Action) -> Action:
        if not action.id:
            action.id = _id()
        with self._lock:
            self._conn.execute(
                """INSERT INTO actions (id, incident_id, ts, role, name, input_json, output, ok)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    action.id,
                    action.incident_id,
                    to_iso(action.ts),
                    action.role,
                    action.name,
                    _dumps(action.input),
                    action.output,
                    1 if action.ok else 0,
                ),
            )
            self._conn.commit()
        return action

    def list_actions(self, incident_id: str) -> list[Action]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM actions WHERE incident_id = ? ORDER BY ts ASC",
                (incident_id,),
            ).fetchall()
        return [_action(r) for r in rows]

    def insert_report(self, report: Report) -> Report:
        if not report.id:
            report.id = _id()
        with self._lock:
            self._conn.execute(
                """INSERT INTO reports (id, incident_id, path, emailed_to, emailed_at, fingerprint, severity)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    report.id,
                    report.incident_id,
                    report.path,
                    report.emailed_to,
                    to_iso(report.emailed_at),
                    report.fingerprint,
                    report.severity,
                ),
            )
            self._conn.commit()
        return report

    def get_report_for_incident(self, incident_id: str) -> Report | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM reports WHERE incident_id = ? ORDER BY emailed_at DESC, path DESC LIMIT 1",
                (incident_id,),
            ).fetchone()
        return _report(row) if row else None

    def last_report_for_fingerprint(self, fingerprint: str) -> Report | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM reports WHERE fingerprint = ? ORDER BY emailed_at DESC LIMIT 1",
                (fingerprint,),
            ).fetchone()
        return _report(row) if row else None

    def events_for_fingerprint(self, fingerprint: str, limit: int = 50) -> list[Event]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE fingerprint = ? ORDER BY ts DESC LIMIT ?",
                (fingerprint, limit),
            ).fetchall()
        return [_event(r) for r in rows]


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parse_iso(value)
    except ValueError:
        return None


def _asset(row: sqlite3.Row) -> Asset:
    return Asset(
        id=row["id"],
        kind=row["kind"],
        name=row["name"],
        source=row["source"],
        status=row["status"],
        meta=_loads(row["meta_json"]),
        last_seen=_dt(row["last_seen"]),
        created_at=_dt(row["created_at"]),
    )


def _event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        asset_id=row["asset_id"],
        ts=_dt(row["ts"]) or datetime.now(timezone.utc),
        level=row["level"],
        source=row["source"],
        fingerprint=row["fingerprint"],
        message=row["message"],
        body=row["body"] or "",
        meta=_loads(row["meta_json"]),
    )


def _incident(row: sqlite3.Row) -> Incident:
    return Incident(
        id=row["id"],
        fingerprint=row["fingerprint"],
        title=row["title"],
        severity=row["severity"],
        status=row["status"],
        event_id=row["event_id"],
        started_at=_dt(row["started_at"]) or datetime.now(timezone.utc),
        resolved_at=_dt(row["resolved_at"]),
        escalate_reason=row["escalate_reason"],
    )


def _action(row: sqlite3.Row) -> Action:
    return Action(
        id=row["id"],
        incident_id=row["incident_id"],
        ts=_dt(row["ts"]) or datetime.now(timezone.utc),
        role=row["role"],
        name=row["name"],
        input=_loads(row["input_json"]),
        output=row["output"] or "",
        ok=bool(row["ok"]),
    )


def _report(row: sqlite3.Row) -> Report:
    return Report(
        id=row["id"],
        incident_id=row["incident_id"],
        path=row["path"],
        emailed_to=row["emailed_to"],
        emailed_at=_dt(row["emailed_at"]),
        fingerprint=row["fingerprint"] or "",
        severity=row["severity"] or "",
    )
