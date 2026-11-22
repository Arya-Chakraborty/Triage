from datetime import datetime, timezone

from triage.domain.entities import Event, Incident
from triage.domain.fingerprints import fingerprint, normalize_message
from triage.domain.incident_policy import attach_or_open, should_open_incident


def _event(**kwargs) -> Event:
    base = dict(
        id="e1",
        asset_id="a1",
        ts=datetime.now(timezone.utc),
        level="error",
        source="app",
        fingerprint="",
        message="boom",
        body="",
        meta={},
    )
    base.update(kwargs)
    return Event(**base)


def test_strips_timestamps_and_addresses():
    a = "ValueError: failed at 2026-01-02T03:04:05.123Z pid=4412 addr 0x7fffabc"
    b = "ValueError: failed at 2026-11-22T13:00:00Z pid=99 addr 0xdeadbeef"
    assert normalize_message(a) == normalize_message(b)
    assert fingerprint("app", a) == fingerprint("app", b)


def test_stack_frames_and_exception_class():
    body = (
        "Traceback (most recent call last):\n"
        '  File "/srv/app/foo.py", line 12, in bar\n'
        "    x()\n"
        "ValueError: boom 0x1\n"
    )
    body2 = (
        "Traceback (most recent call last):\n"
        '  File "/other/foo.py", line 12, in bar\n'
        "    x()\n"
        "ValueError: boom 0x99\n"
    )
    assert fingerprint("pty", "ValueError: boom 0x1", body) == fingerprint(
        "pty", "ValueError: boom 0x99", body2
    )
    other = body.replace("ValueError", "TypeError")
    assert fingerprint("pty", "TypeError: boom", other) != fingerprint(
        "pty", "ValueError: boom 0x1", body
    )


def test_info_does_not_open_incident():
    assert not should_open_incident(_event(level="info"))
    assert not should_open_incident(_event(level="debug"))
    assert should_open_incident(_event(level="error"))
    assert should_open_incident(_event(level="fatal"))


def test_health_needs_two_failures():
    one = _event(level="warning", source="health", meta={"consecutive_failures": 1})
    two = _event(level="warning", source="health", meta={"consecutive_failures": 2})
    assert not should_open_incident(one)
    assert should_open_incident(two)


def test_process_exit_and_deploy_failed():
    assert should_open_incident(_event(source="process", meta={"exit_code": 1}))
    assert not should_open_incident(
        _event(level="info", source="process", meta={"exit_code": 0})
    )
    assert should_open_incident(
        _event(level="info", meta={"type": "deploy", "status": "failed"})
    )
    assert not should_open_incident(
        _event(level="info", meta={"type": "deploy", "status": "succeeded"})
    )


def test_same_fingerprint_appends_while_open():
    fp = fingerprint("app", "ValueError: x")
    existing = Incident(
        id="i1",
        fingerprint=fp,
        title="x",
        severity="high",
        status="open",
        event_id="e0",
        started_at=datetime.now(timezone.utc),
    )
    event = _event(fingerprint=fp)
    assert attach_or_open(existing, event) == "append"
    existing.status = "needs_human"
    assert attach_or_open(existing, event) == "append"
    existing.status = "resolved"
    assert attach_or_open(existing, event) == "open"
    assert attach_or_open(None, event) == "open"
    assert attach_or_open(existing, _event(level="info")) == "ignore"
