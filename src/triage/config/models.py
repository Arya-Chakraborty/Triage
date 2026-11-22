from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any


def _merge(cls, data: dict[str, Any] | None, **defaults: Any):
    data = data or {}
    names = {f.name for f in fields(cls)}
    kwargs = dict(defaults)
    kwargs.update({k: v for k, v in data.items() if k in names and v is not None})
    return cls(**kwargs)


@dataclass
class DashboardConfig:
    host: str = "127.0.0.1"
    port: int = 8787


@dataclass
class LogWatch:
    path: str
    name: str = ""


@dataclass
class HealthWatch:
    name: str
    url: str
    interval: int = 15


@dataclass
class WatchConfig:
    logs: list[LogWatch] = field(default_factory=list)
    health: list[HealthWatch] = field(default_factory=list)
    terminals: bool = True


@dataclass
class ShipConfig:
    ingest_url: str = "http://127.0.0.1:8787/ingest"
    docker_containers: list[str] = field(default_factory=list)


@dataclass
class SmtpConfig:
    host: str = ""
    port: int = 587
    user: str = ""


@dataclass
class AlertsConfig:
    email: str = ""
    smtp: SmtpConfig = field(default_factory=SmtpConfig)


@dataclass
class AgentConfig:
    max_rounds: int = 12
    max_incidents_open: int = 3
    auto_fix: bool = True
    allow_shell: bool = True
    allow_git_commit: bool = False
    sandbox_root: str = "."
    token_budget: int = 100_000
    verify_after_seconds: int = 15
    recurrence_cooldown_seconds: int = 3600


@dataclass
class Config:
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    model: str = "gemini-2.5-flash"
    watch: WatchConfig = field(default_factory=WatchConfig)
    ship: ShipConfig = field(default_factory=ShipConfig)
    assets: list[dict[str, Any]] = field(default_factory=list)
    alerts: AlertsConfig = field(default_factory=AlertsConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    project_root: Path = field(default_factory=lambda: Path("."))

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.dashboard.host}:{self.dashboard.port}"

    @property
    def ingest_url(self) -> str:
        return self.ship.ingest_url or f"{self.dashboard_url}/ingest"

    @property
    def db_path(self) -> Path:
        return self.project_root / ".triage" / "triage.db"

    @property
    def reports_dir(self) -> Path:
        return self.project_root / ".triage" / "reports"

    @property
    def sandbox(self) -> Path:
        root = Path(self.agent.sandbox_root)
        if not root.is_absolute():
            root = self.project_root / root
        return root.resolve()


@dataclass
class Secrets:
    gemini_api_key: str = ""
    ingest_token: str = ""
    smtp_user: str = ""
    smtp_password: str = ""


def config_from_dict(data: dict[str, Any], project_root: Path) -> Config:
    data = data or {}
    dash = _merge(DashboardConfig, data.get("dashboard"))
    watch_raw = data.get("watch") or {}
    logs = [
        LogWatch(**item) if isinstance(item, dict) else LogWatch(path=str(item))
        for item in watch_raw.get("logs") or []
    ]
    health = [HealthWatch(**item) for item in watch_raw.get("health") or []]
    watch = WatchConfig(
        logs=logs,
        health=health,
        terminals=bool(watch_raw.get("terminals", True)),
    )
    ship = _merge(ShipConfig, data.get("ship"))
    alerts_raw = data.get("alerts") or {}
    alerts = AlertsConfig(
        email=alerts_raw.get("email") or "",
        smtp=_merge(SmtpConfig, alerts_raw.get("smtp")),
    )
    agent = _merge(AgentConfig, data.get("agent"))
    return Config(
        dashboard=dash,
        model=data.get("model") or "gemini-2.5-flash",
        watch=watch,
        ship=ship,
        assets=list(data.get("assets") or []),
        alerts=alerts,
        agent=agent,
        project_root=project_root,
    )
