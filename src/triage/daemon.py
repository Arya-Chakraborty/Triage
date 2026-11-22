from __future__ import annotations

import asyncio
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


async def run_watch(root: Path | None = None) -> None:
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
        email_to=cfg.alerts.email,
        dashboard_url=cfg.dashboard_url,
    )

    def on_escalate(incident_id: str, reason: str) -> None:
        escalator.escalate(incident_id, reason)
        incident = store.get_incident(incident_id)
        if incident is None:
            return
        try:
            asyncio.get_running_loop().create_task(
                bus.publish("incident", incident.to_api())
            )
        except RuntimeError:
            pass

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
    )
    scheduler = AgentScheduler(
        loop, cfg.agent.max_incidents_open, set_busy=state.set_busy
    )
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
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app, host=cfg.dashboard.host, port=cfg.dashboard.port, log_level="info"
        )
    )
    scheduler_task = asyncio.create_task(scheduler.run(), name="agent-scheduler")
    for w in watchers:
        await w.start()
    print(f"triage dashboard {cfg.dashboard_url}")
    try:
        await server.serve()
    finally:
        scheduler_task.cancel()
        for w in watchers:
            await w.stop()
        store.close()


def run_watch_sync(root: Path | None = None) -> None:
    asyncio.run(run_watch(root))
