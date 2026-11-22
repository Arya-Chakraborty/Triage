from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

from triage.adapters.gemini_llm import DisabledLLM, GeminiLLM
from triage.adapters.memory_bus import MemoryEventBus
from triage.adapters.pty_runner import PtyProcessRunner
from triage.adapters.smtp_mailer import NullMailer, SmtpMailer
from triage.adapters.sqlite_store import SqliteStore
from triage.adapters.system_clock import SystemClock
from triage.agent.loop import AgentLoop, AgentScheduler
from triage.agent.policy import AgentPolicy
from triage.agent.tools import default_tools
from triage.config.loader import load_config, load_secrets
from triage.escalate.report import Escalator
from triage.ingest.service import IngestService
from triage.runtime import AppState
from triage.watchers.health import HealthWatcher
from triage.watchers.log_tail import LogTailWatcher
from triage.watchers.process import ProcessWatcher
from triage.web.app import create_app

log = logging.getLogger("triage")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, _JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root.handlers = [handler]
    root.setLevel(logging.INFO)


async def run_watch(root: Path | None = None) -> None:
    configure_logging()
    cfg = load_config(root)
    secrets = load_secrets()
    cfg.project_root.joinpath(".triage").mkdir(exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)

    store = SqliteStore(cfg.db_path)
    clock = SystemClock()
    bus = MemoryEventBus()
    runner = PtyProcessRunner()
    state = AppState()
    mailer = (
        SmtpMailer(
            host=cfg.alerts.smtp.host,
            port=cfg.alerts.smtp.port,
            user=secrets.smtp_user or cfg.alerts.smtp.user,
            password=secrets.smtp_password,
            sender=cfg.alerts.email,
        )
        if cfg.alerts.smtp.host
        else NullMailer()
    )
    llm = GeminiLLM(secrets.gemini_api_key) if secrets.gemini_api_key else DisabledLLM()
    escalator = Escalator(
        store=store,
        clock=clock,
        mailer=mailer,
        bus=bus,
        reports_dir=cfg.reports_dir,
        email_to=cfg.alerts.email if cfg.alerts.smtp.host else "",
        dashboard_url=cfg.dashboard_url,
    )

    def publish(topic: str, payload: dict) -> None:
        try:
            asyncio.get_running_loop().create_task(bus.publish(topic, payload))
        except RuntimeError:
            pass

    def on_escalate(incident_id: str, reason: str) -> None:
        escalator.escalate(incident_id, reason)
        incident = store.get_incident(incident_id)
        if incident is None:
            return
        publish("incident", incident.to_api())

    def on_action(action) -> None:
        payload = action.to_api()
        payload["incident_id"] = action.incident_id
        publish("action", payload)

    def on_incident(incident) -> None:
        publish("incident", incident.to_api())

    def set_busy(busy: bool) -> None:
        state.set_busy(busy)
        publish("agent", {"busy": busy})

    policy = AgentPolicy(
        max_rounds=cfg.agent.max_rounds,
        token_budget=cfg.agent.token_budget,
        cooldown_seconds=cfg.agent.recurrence_cooldown_seconds,
    )
    loop = AgentLoop(
        llm=llm,
        store=store,
        clock=clock,
        process_runner=runner,
        tools=default_tools(),
        policy=policy,
        model=cfg.model,
        sandbox_root=cfg.sandbox,
        allow_shell=cfg.agent.allow_shell,
        allow_git_commit=cfg.agent.allow_git_commit,
        verify_after_seconds=cfg.agent.verify_after_seconds,
        auto_fix=cfg.agent.auto_fix,
        on_escalate=on_escalate,
        on_action=on_action,
        on_incident=on_incident,
    )
    scheduler = AgentScheduler(loop, cfg.agent.max_incidents_open, set_busy=set_busy)
    ingest = IngestService(
        store,
        clock,
        bus,
        on_incident=scheduler.enqueue,
        cooldown_seconds=cfg.agent.recurrence_cooldown_seconds,
        state=state,
    )

    async def emit(raw: dict) -> None:
        await ingest.ingest_event(raw)

    watchers = [
        LogTailWatcher(
            cfg.watch.logs, cfg.project_root / ".triage" / "tail_offsets.json", emit
        ),
        HealthWatcher(cfg.watch.health, emit, on_check=state.note_health),
        ProcessWatcher(store, runner, emit),
    ]
    app = create_app(
        store=store,
        bus=bus,
        ingest=ingest,
        token=secrets.ingest_token,
        state=state,
        clock=clock,
        requeue=scheduler.requeue,
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=cfg.dashboard.host,
            port=cfg.dashboard.port,
            log_level="info",
            log_config=None,
        )
    )
    server.install_signal_handlers = lambda: None
    loop_ = asyncio.get_running_loop()

    def _stop() -> None:
        server.should_exit = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop_.add_signal_handler(sig, _stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_args: _stop())
    scheduler_task = asyncio.create_task(scheduler.run(), name="agent-scheduler")
    for w in watchers:
        await w.start()
    log.info("dashboard %s", cfg.dashboard_url)
    try:
        await server.serve()
    finally:
        log.info("shutting down")
        runner.terminate_all()
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        for w in watchers:
            await w.stop()
        store.close()


def run_watch_sync(root: Path | None = None) -> None:
    asyncio.run(run_watch(root))
