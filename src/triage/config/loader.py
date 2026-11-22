from __future__ import annotations

import os
import secrets as secretslib
from getpass import getpass
from pathlib import Path

import yaml

from triage.config.models import Config, Secrets, config_from_dict

CONFIG_NAME = ".triage.yaml"


def project_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    return cur


def load_config(root: Path | None = None) -> Config:
    root = root or project_root()
    path = root / CONFIG_NAME
    data: dict = {}
    if path.is_file():
        try:
            loaded = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"{path}: invalid YAML ({exc})") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must be a mapping")
        data = loaded
    try:
        return config_from_dict(data, root)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def secrets_path() -> Path:
    override = os.environ.get("TRIAGE_SECRETS_PATH")
    if override:
        return Path(override)
    return Path.home() / ".triage" / "secrets"


def load_secrets() -> Secrets:
    path = secrets_path()
    values: dict[str, str] = {}
    if path.is_file():
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    return Secrets(
        gemini_api_key=values.get("GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_KEY", ""),
        ingest_token=values.get("INGEST_TOKEN") or os.environ.get("INGEST_TOKEN", ""),
        smtp_user=values.get("SMTP_USER", ""),
        smtp_password=values.get("SMTP_PASSWORD", ""),
    )


def run_init(root: Path | None = None) -> Path:
    """Write .triage.yaml and ~/.triage/secrets. Interactive unless TRIAGE_NONINTERACTIVE=1."""
    root = (root or Path.cwd()).resolve()
    noninteractive = os.environ.get("TRIAGE_NONINTERACTIVE") == "1"

    gemini = _prompt(
        "Gemini API key",
        env="TRIAGE_GEMINI_API_KEY",
        secret=True,
        required=True,
        noninteractive=noninteractive,
    )
    email = _prompt(
        "Alert email",
        env="TRIAGE_ALERT_EMAIL",
        default="",
        noninteractive=noninteractive,
    )
    smtp_host = _prompt(
        "SMTP host (empty to skip)",
        env="TRIAGE_SMTP_HOST",
        default="",
        noninteractive=noninteractive,
    )
    smtp_port = (
        _prompt(
            "SMTP port",
            env="TRIAGE_SMTP_PORT",
            default="587",
            noninteractive=noninteractive,
        )
        if smtp_host
        else "587"
    )
    smtp_user = (
        _prompt(
            "SMTP user",
            env="TRIAGE_SMTP_USER",
            default="",
            noninteractive=noninteractive,
        )
        if smtp_host
        else ""
    )
    smtp_password = (
        _prompt(
            "SMTP password",
            env="TRIAGE_SMTP_PASSWORD",
            secret=True,
            default="",
            noninteractive=noninteractive,
        )
        if smtp_host
        else ""
    )
    host = _prompt(
        "Dashboard host",
        env="TRIAGE_DASHBOARD_HOST",
        default="127.0.0.1",
        noninteractive=noninteractive,
    )
    port = _prompt(
        "Dashboard port",
        env="TRIAGE_DASHBOARD_PORT",
        default="8787",
        noninteractive=noninteractive,
    )
    token = os.environ.get("TRIAGE_INGEST_TOKEN") or secretslib.token_urlsafe(32)

    yaml_path = root / CONFIG_NAME
    doc = {
        "dashboard": {"host": host, "port": int(port or 8787)},
        "model": "gemini-3.5-flash-lite",
        "watch": {"logs": [], "health": [], "terminals": True},
        "ship": {"ingest_url": f"http://{host}:{port}/ingest", "docker_containers": []},
        "assets": [],
        "alerts": {
            "email": email,
            "smtp": {
                "host": smtp_host,
                "port": int(smtp_port or 587),
                "user": smtp_user,
            },
        },
        "agent": {
            "max_rounds": 12,
            "max_incidents_open": 3,
            "auto_fix": True,
            "allow_shell": True,
            "allow_git_commit": False,
            "sandbox_root": ".",
            "token_budget": 100000,
            "verify_after_seconds": 15,
            "recurrence_cooldown_seconds": 3600,
        },
    }
    yaml_path.write_text(yaml.safe_dump(doc, sort_keys=False))

    sdir = secrets_path().parent
    sdir.mkdir(mode=0o700, parents=True, exist_ok=True)
    lines = [
        f"GEMINI_API_KEY={gemini}",
        f"INGEST_TOKEN={token}",
    ]
    if smtp_user:
        lines.append(f"SMTP_USER={smtp_user}")
    if smtp_password:
        lines.append(f"SMTP_PASSWORD={smtp_password}")
    path = secrets_path()
    path.write_text("\n".join(lines) + "\n")
    os.chmod(path, 0o600)
    (root / ".triage").mkdir(exist_ok=True)
    return yaml_path


def _prompt(
    label: str,
    *,
    env: str,
    default: str | None = None,
    secret: bool = False,
    required: bool = False,
    noninteractive: bool = False,
) -> str:
    if noninteractive:
        val = os.environ.get(env, default if default is not None else "")
        if required and not val:
            raise SystemExit(f"{env} is required in non-interactive init")
        return val or ""
    hint = f" [{default}]" if default else ""
    raw = getpass(f"{label}: ") if secret else input(f"{label}{hint}: ")
    val = raw.strip() if raw else (default or "")
    if required and not val:
        raise SystemExit(f"{label} is required")
    return val
