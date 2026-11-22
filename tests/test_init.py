from pathlib import Path

import pytest

from triage.cli import main
from triage.config.loader import load_secrets, run_init


def test_noninteractive_init(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    secrets = tmp_path / "secrets"
    monkeypatch.setenv("TRIAGE_SECRETS_PATH", str(secrets))
    monkeypatch.setenv("TRIAGE_NONINTERACTIVE", "1")
    monkeypatch.setenv("TRIAGE_GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("TRIAGE_ALERT_EMAIL", "ops@example.com")
    monkeypatch.setenv("TRIAGE_INGEST_TOKEN", "tok")
    path = run_init(tmp_path)
    assert path.is_file()
    text = path.read_text()
    assert "8787" in text
    assert secrets.is_file()
    assert secrets.stat().st_mode & 0o777 == 0o600
    loaded = load_secrets()
    assert loaded.gemini_api_key == "gemini-test-key"
    assert loaded.ingest_token == "tok"


def test_cli_help_and_init(tmp_path: Path, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "init" in capsys.readouterr().out
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TRIAGE_SECRETS_PATH", str(tmp_path / "secrets"))
    monkeypatch.setenv("TRIAGE_NONINTERACTIVE", "1")
    monkeypatch.setenv("TRIAGE_GEMINI_API_KEY", "k")
    monkeypatch.setenv("TRIAGE_INGEST_TOKEN", "tok")
    assert main(["init"]) == 0
    assert (tmp_path / ".triage.yaml").is_file()
