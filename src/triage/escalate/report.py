from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path

from triage.domain.entities import Report, to_iso
from triage.domain.incident_policy import SEVERITY_RANK
from triage.domain.redaction import redact
from triage.ports.clock import Clock
from triage.ports.event_bus import EventBus
from triage.ports.mailer import Mailer
from triage.ports.store import Store


class Escalator:
    def __init__(
        self,
        store: Store,
        clock: Clock,
        mailer: Mailer,
        bus: EventBus,
        reports_dir: Path,
        email_to: str,
        dashboard_url: str,
    ) -> None:
        self.store = store
        self.clock = clock
        self.mailer = mailer
        self.bus = bus
        self.reports_dir = reports_dir
        self.email_to = email_to
        self.dashboard_url = dashboard_url

    def escalate(self, incident_id: str, reason: str) -> Path:
        incident = self.store.get_incident(incident_id)
        if incident is None:
            raise ValueError(f"incident {incident_id} not found")
        now = self.clock.now()
        incident = self.store.update_incident(
            incident_id,
            status="needs_human",
            escalate_reason=reason,
        )
        events = self.store.events_for_fingerprint(incident.fingerprint, limit=20)
        actions = self.store.list_actions(incident_id)
        trigger = events[0] if events else None
        asset = (
            self.store.get_asset(trigger.asset_id)
            if trigger and trigger.asset_id
            else None
        )
        diffs = [a.output for a in actions if a.name == "write_file" and a.ok]

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.reports_dir / f"incident-{incident.id}.md"
        body = _markdown(
            incident, reason, trigger, asset, actions, diffs, self.dashboard_url
        )
        path.write_text(body)

        emailed_to = None
        emailed_at = None
        if self.email_to and self._should_mail(incident):
            try:
                self.mailer.send(
                    self.email_to,
                    f"[triage] {incident.severity} {incident.title}",
                    body,
                )
                emailed_to = self.email_to
                emailed_at = now
            except Exception:
                pass  # file-only is success

        self.store.insert_report(
            Report(
                id=uuid.uuid4().hex,
                incident_id=incident.id,
                path=str(path),
                emailed_to=emailed_to,
                emailed_at=emailed_at,
                fingerprint=incident.fingerprint,
                severity=incident.severity,
            )
        )
        # fire-and-forget publish; escalate is sync
        return path

    def _should_mail(self, incident) -> bool:
        last = self.store.last_report_for_fingerprint(incident.fingerprint)
        if last is None or last.emailed_at is None:
            return True
        within = self.clock.now() - last.emailed_at < timedelta(hours=1)
        if not within:
            return True
        return SEVERITY_RANK.get(incident.severity, 0) > SEVERITY_RANK.get(
            last.severity, 0
        )


def _markdown(
    incident, reason, trigger, asset, actions, diffs, dashboard_url: str
) -> str:
    trig = ""
    if trigger:
        trig = redact((trigger.message + "\n" + (trigger.body or ""))[:1500])
    lines = [
        f"# Incident {incident.id}",
        "",
        f"- **Title**: {incident.title}",
        f"- **Severity**: {incident.severity}",
        f"- **Fingerprint**: {incident.fingerprint}",
        f"- **Asset**: {asset.name if asset else 'unknown'}",
        f"- **Started**: {to_iso(incident.started_at)}",
        f"- **Why human**: {reason}",
        f"- **Dashboard**: {dashboard_url}/  (id={incident.id})",
        "",
        "## Trigger",
        "",
        "```",
        trig or "(none)",
        "```",
        "",
        "## Tool timeline",
        "",
    ]
    for action in actions:
        flag = "ok" if action.ok else "fail"
        lines.append(
            f"- `{to_iso(action.ts)}` [{action.role}/{action.name} {flag}] {redact(action.output)[:400]}"
        )
    lines += ["", "## Diffs applied", ""]
    if diffs:
        lines.extend(["```", *diffs[:20], "```"])
    else:
        lines.append("(none)")
    return "\n".join(lines) + "\n"
