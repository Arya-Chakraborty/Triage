from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from triage.domain.entities import Event, Incident
from triage.domain.fingerprints import fingerprint
from triage.domain.incident_policy import (
    attach_or_open,
    higher_severity,
    severity_for,
    title_for,
)
from triage.ports.clock import Clock
from triage.ports.event_bus import EventBus
from triage.ports.store import Store

OnIncident = Callable[[str], None]


class IngestService:
    def __init__(
        self,
        store: Store,
        clock: Clock,
        bus: EventBus,
        on_incident: OnIncident | None = None,
        cooldown_seconds: int = 3600,
        state: Any | None = None,
    ) -> None:
        self.store = store
        self.clock = clock
        self.bus = bus
        self.on_incident = on_incident
        self.cooldown_seconds = cooldown_seconds
        self.state = state

    async def handle_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        kind = payload.get("type")
        if kind == "heartbeat":
            return await self._heartbeat(payload)
        if kind == "deploy":
            return await self._deploy(payload)
        events = payload.get("events")
        if not isinstance(events, list):
            raise ValueError("body must be events[], type=deploy, or type=heartbeat")
        stored = []
        for raw in events:
            stored.append(await self.ingest_event(raw))
        return {"ingested": len(stored)}

    async def ingest_event(self, raw: dict[str, Any]) -> Event:
        now = self.clock.now()
        ts = _ts(raw.get("ts"), now)
        level = str(raw.get("level") or "info").lower()
        if level not in {"debug", "info", "warning", "error", "fatal"}:
            level = "info"
        source = str(raw.get("source") or "unknown")
        message = str(raw.get("message") or "")[:4000]
        body = str(raw.get("body") or "")[:64_000]
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        asset_name = str(raw.get("asset_name") or meta.get("hostname") or source)
        asset_kind = str(raw.get("kind") or "server")
        if asset_kind not in {"process", "terminal", "server", "url", "deploy"}:
            asset_kind = "server"
        status = (
            "down"
            if level in {"error", "fatal"} and asset_kind in {"process", "url"}
            else "up"
        )
        if meta.get("ok") is True:
            status = "up"
        if meta.get("ok") is False:
            status = "down"
        asset = self.store.upsert_asset(
            kind=asset_kind,
            name=asset_name,
            source=source,
            status=status,
            meta=meta,
            last_seen=ts,
        )
        fp = fingerprint(source, message, body)
        event = Event(
            id=uuid.uuid4().hex,
            asset_id=asset.id,
            ts=ts,
            level=level,
            source=source,
            fingerprint=fp,
            message=message,
            body=body,
            meta=meta,
        )
        self.store.insert_event(event)
        await self.bus.publish("event", event.to_api())
        await self.bus.publish("asset", asset.to_api())
        if self.state is not None and asset_kind == "process":
            self.state.note_terminal(asset, message)

        existing = self.store.get_open_by_fingerprint(fp)
        action = attach_or_open(existing, event)
        if action == "append" and existing:
            sev = higher_severity(existing.severity, severity_for(event))
            if sev != existing.severity:
                self.store.update_incident(existing.id, severity=sev)
            return event
        if action == "open":
            last = self.store.last_resolved_by_fingerprint(fp)
            status_i = "open"
            reason = None
            if (
                last
                and last.resolved_at
                and (now - last.resolved_at) < timedelta(seconds=self.cooldown_seconds)
            ):
                status_i = "needs_human"
                reason = "same fingerprint recurred within cooldown"
            incident = self.store.insert_incident(
                Incident(
                    id=uuid.uuid4().hex,
                    fingerprint=fp,
                    title=title_for(event),
                    severity=severity_for(event),
                    status=status_i,
                    event_id=event.id,
                    started_at=now,
                    escalate_reason=reason,
                )
            )
            await self.bus.publish("incident", incident.to_api())
            if self.on_incident:
                self.on_incident(incident.id)

        if meta.get("recovered") and existing:
            others = [
                e
                for e in self.store.events_for_fingerprint(fp, limit=20)
                if e.source != "health" and e.level in {"error", "fatal"}
            ]
            if not others:
                self.store.update_incident(
                    existing.id, status="resolved", resolved_at=now
                )

        return event

    async def _heartbeat(self, payload: dict[str, Any]) -> dict[str, Any]:
        host = str(payload.get("hostname") or "unknown")
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        now = self.clock.now()
        asset = self.store.upsert_asset(
            kind="server",
            name=host,
            source="heartbeat",
            status="up",
            meta=meta,
            last_seen=now,
        )
        if self.state is not None:
            self.state.note_heartbeat(host, now)
        await self.bus.publish("asset", asset.to_api())
        return {"ok": True, "hostname": host}

    async def _deploy(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = str(payload.get("status") or "")
        sha = str(payload.get("sha") or "")
        env = str(payload.get("env") or "")
        level = "error" if status == "failed" else "info"
        event = await self.ingest_event(
            {
                "level": level,
                "source": "deploy",
                "message": f"deploy.{status}",
                "asset_name": f"deploy-{env or 'default'}",
                "kind": "deploy",
                "meta": {"type": "deploy", "status": status, "sha": sha, "env": env},
            }
        )
        return {"ok": True, "event_id": event.id}


def _ts(value: Any, now: datetime) -> datetime:
    if not value:
        return now
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        from triage.domain.entities import parse_iso

        return parse_iso(str(value))
    except ValueError:
        return now
