from datetime import datetime, timezone
from pathlib import Path

from triage.adapters.memory_bus import MemoryEventBus
from triage.adapters.smtp_mailer import NullMailer
from triage.adapters.sqlite_store import SqliteStore
from triage.domain.entities import Event, Incident
from triage.escalate.report import Escalator
from triage.ports.clock import Clock


class FrozenClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_escalate_writes_report_without_smtp(tmp_path: Path):
    store = SqliteStore(tmp_path / "t.db")
    clock = FrozenClock()
    now = clock.now()
    fp = "abc123"
    event = Event(
        id="e1",
        asset_id=None,
        ts=now,
        level="error",
        source="app",
        fingerprint=fp,
        message="ValueError: boom api_key=secret-value",
        body="",
        meta={},
    )
    store.insert_event(event)
    incident = store.insert_incident(
        Incident(
            id="inc1",
            fingerprint=fp,
            title="ValueError: boom",
            severity="high",
            status="open",
            event_id=event.id,
            started_at=now,
        )
    )
    reports = tmp_path / "reports"
    escalator = Escalator(
        store=store,
        clock=clock,
        mailer=NullMailer(),
        bus=MemoryEventBus(),
        reports_dir=reports,
        email_to="",
        dashboard_url="http://127.0.0.1:8787",
    )
    path = escalator.escalate(incident.id, "needs a human")
    assert path.is_file()
    text = path.read_text()
    assert "needs a human" in text
    assert "secret-value" not in text
    assert incident.id in text
    row = store.get_report_for_incident(incident.id)
    assert row is not None
    assert row.emailed_to is None
    assert store.get_incident(incident.id).status == "needs_human"


def test_disabled_llm_guarded():
    from triage.adapters.gemini_llm import DisabledLLM
    from triage.ports.llm import LLMError, LLMRequest

    try:
        DisabledLLM().generate(
            LLMRequest(model="gemini-2.5-flash", system="", contents=[], tools=[])
        )
    except LLMError as exc:
        assert "GEMINI_API_KEY" in str(exc)
    else:
        raise AssertionError("DisabledLLM must fail closed without a key")
