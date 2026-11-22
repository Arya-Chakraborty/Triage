from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class Asset:
    id: str
    kind: str
    name: str
    source: str
    status: str
    meta: dict[str, Any] = field(default_factory=dict)
    last_seen: datetime | None = None
    created_at: datetime | None = None

    def to_api(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "source": self.source,
            "status": self.status,
            "meta": self.meta,
            "last_seen": to_iso(self.last_seen),
        }


@dataclass
class Event:
    id: str
    asset_id: str | None
    ts: datetime
    level: str
    source: str
    fingerprint: str
    message: str
    body: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_api(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "ts": to_iso(self.ts),
            "level": self.level,
            "source": self.source,
            "fingerprint": self.fingerprint,
            "message": self.message,
            "body": self.body,
            "meta": self.meta,
        }


@dataclass
class Incident:
    id: str
    fingerprint: str
    title: str
    severity: str
    status: str
    event_id: str
    started_at: datetime
    resolved_at: datetime | None = None
    escalate_reason: str | None = None

    def to_api(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fingerprint": self.fingerprint,
            "title": self.title,
            "severity": self.severity,
            "status": self.status,
            "event_id": self.event_id,
            "started_at": to_iso(self.started_at),
            "resolved_at": to_iso(self.resolved_at),
            "escalate_reason": self.escalate_reason,
        }


@dataclass
class Action:
    id: str
    incident_id: str
    ts: datetime
    role: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)
    output: str = ""
    ok: bool = True

    def to_api(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": to_iso(self.ts),
            "role": self.role,
            "name": self.name,
            "input": self.input,
            "output": self.output,
            "ok": self.ok,
        }


@dataclass
class Report:
    id: str
    incident_id: str
    path: str
    emailed_to: str | None = None
    emailed_at: datetime | None = None
    fingerprint: str = ""
    severity: str = ""
