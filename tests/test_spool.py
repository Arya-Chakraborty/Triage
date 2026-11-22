from pathlib import Path

from triage.ingest.client import flush_spool, post_ingest, spool_append


def test_spool_when_ingest_down(tmp_path: Path):
    spool = tmp_path / ".triage" / "spool.jsonl"
    payload = {"events": [{"level": "error", "source": "ship", "message": "boom"}]}
    assert (
        post_ingest("http://127.0.0.1:1/ingest", "tok", payload, timeout=0.3) is False
    )
    spool_append(spool, payload)
    assert spool.is_file()
    assert "boom" in spool.read_text()


def test_flush_spool_drops_delivered_keeps_failed(tmp_path: Path, monkeypatch):
    spool = tmp_path / "spool.jsonl"
    spool_append(spool, {"n": 1})
    spool_append(spool, {"n": 2})

    def fake_post(_url, _token, payload, timeout=10.0):
        return payload.get("n") == 1

    monkeypatch.setattr("triage.ingest.client.post_ingest", fake_post)
    flush_spool(spool, "http://x/ingest", "tok")
    leftover = spool.read_text()
    assert '"n": 1' not in leftover
    assert '"n": 2' in leftover
