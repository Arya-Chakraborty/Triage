"""When an event becomes an incident, and how duplicates attach."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from triage.domain.entities import Event, Incident

OPEN_STATUSES = ("open", "fixing", "needs_human")
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
GateAction = Literal["ignore", "append", "open", "needs_human"]


def severity_for(event: Event) -> str:
    if (
        event.level == "fatal"
        or event.meta.get("type") == "deploy"
        and event.meta.get("status") == "failed"
    ):
        env = str(event.meta.get("env") or "")
        if event.level == "fatal" or env.lower() in {"prod", "production"}:
            return "critical"
        return "high"
    if event.level == "error":
        return "high"
    if event.source == "health":
        return "high"
    if event.level == "warning":
        return "medium"
    return "low"


def should_open_incident(event: Event) -> bool:
    """Info/debug stay events. Error/fatal, 2x health fail, nonzero exit, deploy.failed open."""
    if event.level in {"error", "fatal"}:
        return True
    if event.meta.get("type") == "deploy" and event.meta.get("status") == "failed":
        return True
    if (
        event.source == "health"
        and int(event.meta.get("consecutive_failures") or 0) >= 2
    ):
        return True
    if event.source == "process" and event.meta.get("exit_code") not in (None, 0, "0"):
        return True
    return False


def attach_or_open(existing: Incident | None, event: Event) -> GateAction:
    if not should_open_incident(event):
        return "ignore"
    if existing is not None and existing.status in OPEN_STATUSES:
        return "append"
    return "open"


def recurrence_needs_human(
    last_resolved_at: datetime | None,
    now: datetime,
    cooldown_seconds: int,
) -> bool:
    if last_resolved_at is None:
        return False
    return (now - last_resolved_at) < timedelta(seconds=cooldown_seconds)


def higher_severity(current: str, incoming: str) -> str:
    if SEVERITY_RANK.get(incoming, 0) > SEVERITY_RANK.get(current, 0):
        return incoming
    return current


def title_for(event: Event) -> str:
    text = (event.message or event.body or "incident").strip().splitlines()[0]
    return text[:120] if text else "incident"
