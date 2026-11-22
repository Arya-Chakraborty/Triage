from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _map(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping, got {type(value).__name__}")
    return value


def _int(
    value: Any,
    name: str,
    default: int,
    *,
    lo: int | None = None,
    hi: int | None = None,
) -> int:
    if value is None:
        value = default
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc
    if lo is not None and n < lo:
        raise ValueError(f"{name} must be >= {lo}, got {n}")
    if hi is not None and n > hi:
        raise ValueError(f"{name} must be <= {hi}, got {n}")
    return n


def _str(value: Any, name: str, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {value!r}")
    return value


def _bool(value: Any, name: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ValueError(f"{name} must be a boolean, got {value!r}")


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
    model: str = "gemini-3.5-flash"
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
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("config must be a mapping")
    dash_raw = _map(data.get("dashboard"), "dashboard")
    dash = DashboardConfig(
        host=_str(dash_raw.get("host"), "dashboard.host", "127.0.0.1") or "127.0.0.1",
        port=_int(dash_raw.get("port"), "dashboard.port", 8787, lo=1, hi=65535),
    )
    watch_raw = _map(data.get("watch"), "watch")
    logs: list[LogWatch] = []
    for i, item in enumerate(watch_raw.get("logs") or []):
        if isinstance(item, str):
            logs.append(LogWatch(path=item))
            continue
        item = _map(item, f"watch.logs[{i}]")
        path = item.get("path")
        if not path:
            raise ValueError(f"watch.logs[{i}] missing path")
        logs.append(LogWatch(path=str(path), name=str(item.get("name") or "")))
    health: list[HealthWatch] = []
    for i, item in enumerate(watch_raw.get("health") or []):
        item = _map(item, f"watch.health[{i}]")
        if not item.get("name") or not item.get("url"):
            raise ValueError(f"watch.health[{i}] requires name and url")
        health.append(
            HealthWatch(
                name=str(item["name"]),
                url=str(item["url"]),
                interval=_int(
                    item.get("interval"), f"watch.health[{i}].interval", 15, lo=1
                ),
            )
        )
    watch = WatchConfig(
        logs=logs,
        health=health,
        terminals=_bool(watch_raw.get("terminals"), "watch.terminals", True),
    )
    ship_raw = _map(data.get("ship"), "ship")
    containers = ship_raw.get("docker_containers") or []
    if not isinstance(containers, list):
        raise ValueError("ship.docker_containers must be a list")
    ship = ShipConfig(
        ingest_url=_str(
            ship_raw.get("ingest_url"),
            "ship.ingest_url",
            "http://127.0.0.1:8787/ingest",
        )
        or "http://127.0.0.1:8787/ingest",
        docker_containers=[str(c) for c in containers],
    )
    alerts_raw = _map(data.get("alerts"), "alerts")
    smtp_raw = _map(alerts_raw.get("smtp"), "alerts.smtp")
    alerts = AlertsConfig(
        email=_str(alerts_raw.get("email"), "alerts.email", ""),
        smtp=SmtpConfig(
            host=_str(smtp_raw.get("host"), "alerts.smtp.host", ""),
            port=_int(smtp_raw.get("port"), "alerts.smtp.port", 587, lo=1, hi=65535),
            user=_str(smtp_raw.get("user"), "alerts.smtp.user", ""),
        ),
    )
    agent_raw = _map(data.get("agent"), "agent")
    agent = AgentConfig(
        max_rounds=_int(agent_raw.get("max_rounds"), "agent.max_rounds", 12, lo=1),
        max_incidents_open=_int(
            agent_raw.get("max_incidents_open"), "agent.max_incidents_open", 3, lo=1
        ),
        auto_fix=_bool(agent_raw.get("auto_fix"), "agent.auto_fix", True),
        allow_shell=_bool(agent_raw.get("allow_shell"), "agent.allow_shell", True),
        allow_git_commit=_bool(
            agent_raw.get("allow_git_commit"), "agent.allow_git_commit", False
        ),
        sandbox_root=_str(agent_raw.get("sandbox_root"), "agent.sandbox_root", ".")
        or ".",
        token_budget=_int(
            agent_raw.get("token_budget"), "agent.token_budget", 100_000, lo=1
        ),
        verify_after_seconds=_int(
            agent_raw.get("verify_after_seconds"),
            "agent.verify_after_seconds",
            15,
            lo=0,
        ),
        recurrence_cooldown_seconds=_int(
            agent_raw.get("recurrence_cooldown_seconds"),
            "agent.recurrence_cooldown_seconds",
            3600,
            lo=0,
        ),
    )
    assets = data.get("assets") or []
    if not isinstance(assets, list):
        raise ValueError("assets must be a list")
    model = data.get("model") or "gemini-3.5-flash"
    if not isinstance(model, str):
        raise ValueError("model must be a string")
    return Config(
        dashboard=dash,
        model=model,
        watch=watch,
        ship=ship,
        assets=list(assets),
        alerts=alerts,
        agent=agent,
        project_root=project_root,
    )
