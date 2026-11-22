from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable
from typing import Any

from triage.agent.policy import AgentPolicy, Decision
from triage.agent.tools.base import Tool, ToolContext, ToolResult
from triage.domain.entities import Action
from triage.domain.redaction import redact
from triage.ports.clock import Clock
from triage.ports.llm import LLMClient, LLMError, LLMRequest
from triage.ports.process_runner import ProcessRunner
from triage.ports.store import Store

SYSTEM = (
    "You are Triage. Diagnose from events + repo. Smallest fix. Use tools. "
    "Call `escalate` when destructive, ambiguous, needs secrets/prod credentials, or unverifiable. "
    "Do not push. Do not exfiltrate secrets."
)


class AgentLoop:
    def __init__(
        self,
        *,
        llm: LLMClient,
        store: Store,
        clock: Clock,
        process_runner: ProcessRunner,
        tools: list[Tool],
        policy: AgentPolicy,
        model: str,
        sandbox_root,
        allow_shell: bool,
        allow_git_commit: bool,
        verify_after_seconds: int,
        auto_fix: bool,
        on_escalate: Callable[..., Any],
        on_resolved: Callable[..., Any] | None = None,
    ) -> None:
        self.llm = llm
        self.store = store
        self.clock = clock
        self.process_runner = process_runner
        self.tools = {t.name: t for t in tools}
        self.policy = policy
        self.model = model
        self.sandbox_root = sandbox_root
        self.allow_shell = allow_shell
        self.allow_git_commit = allow_git_commit
        self.verify_after_seconds = verify_after_seconds
        self.auto_fix = auto_fix
        self.on_escalate = on_escalate
        self.on_resolved = on_resolved

    async def handle(self, incident_id: str) -> None:
        incident = self.store.get_incident(incident_id)
        if incident is None:
            return
        last = self.store.last_resolved_by_fingerprint(incident.fingerprint)
        early = self.policy.on_start(
            last_resolved_at=last.resolved_at if last else None,
            now=self.clock.now(),
            auto_fix=self.auto_fix,
        )
        if early is not None:
            await self._finish(incident_id, early.decision, early.reason)
            return

        self.store.update_incident(incident_id, status="fixing")
        events = self.store.events_for_fingerprint(incident.fingerprint, limit=30)
        prompt = _brief(incident, events)
        contents: list[dict[str, Any]] = [{"role": "user", "text": redact(prompt)}]
        decls = [t.declaration() for t in self.tools.values()]
        repeats: dict[str, int] = {}
        tokens = 0
        ctx = ToolContext(
            sandbox_root=self.sandbox_root,
            store=self.store,
            clock=self.clock,
            process_runner=self.process_runner,
            incident=incident,
            allow_shell=self.allow_shell,
            allow_git_commit=self.allow_git_commit,
        )

        for round_index in range(1, self.policy.max_rounds + 1):
            try:
                response = await asyncio.to_thread(
                    self.llm.generate,
                    LLMRequest(
                        model=self.model, system=SYSTEM, contents=contents, tools=decls
                    ),
                )
            except LLMError as exc:
                await self._finish(
                    incident_id, Decision.NEEDS_HUMAN, f"llm error: {exc}"
                )
                return

            tokens += response.tokens_used
            self.store.insert_action(
                Action(
                    id=uuid.uuid4().hex,
                    incident_id=incident_id,
                    ts=self.clock.now(),
                    role="model",
                    name="generate",
                    input={"round": round_index},
                    output=redact(response.text)
                    or json.dumps([c.name for c in response.function_calls]),
                    ok=True,
                )
            )

            if response.function_calls:
                contents.append(
                    {
                        "role": "model",
                        "calls": [
                            {"name": c.name, "args": c.args}
                            for c in response.function_calls
                        ],
                    }
                )
                for call in response.function_calls:
                    key = f"{call.name}:{json.dumps(call.args, sort_keys=True, default=str)}"
                    repeats[key] = repeats.get(key, 0) + 1
                    tool = self.tools.get(call.name)
                    if tool is None:
                        result = ToolResult(
                            ok=False, output=f"unknown tool {call.name}"
                        )
                    else:
                        result = await asyncio.to_thread(
                            tool.execute, ctx, call.args or {}
                        )
                    self.store.insert_action(
                        Action(
                            id=uuid.uuid4().hex,
                            incident_id=incident_id,
                            ts=self.clock.now(),
                            role="tool",
                            name=call.name,
                            input=call.args or {},
                            output=redact(result.output)[:8000],
                            ok=result.ok,
                        )
                    )
                    contents.append(
                        {
                            "role": "user",
                            "tool": call.name,
                            "text": redact(result.output)[:8000],
                        }
                    )
                    verdict = self.policy.after_round(
                        round_index=round_index,
                        tokens_used=tokens,
                        repeats={key: repeats[key]},
                        tool_name=key,
                        result=result,
                        claimed_fix=False,
                        verified_healthy=False,
                    )
                    if verdict is not None:
                        await self._finish(
                            incident_id, verdict.decision, verdict.reason
                        )
                        return
                continue

            contents.append({"role": "model", "text": response.text})
            healthy = await self._verify()
            verdict = self.policy.after_round(
                round_index=round_index,
                tokens_used=tokens,
                repeats=repeats,
                tool_name=None,
                result=None,
                claimed_fix=bool(response.text),
                verified_healthy=healthy,
            )
            if verdict is not None:
                await self._finish(incident_id, verdict.decision, verdict.reason)
                return
            await self._finish(
                incident_id, Decision.NEEDS_HUMAN, "model stopped without verified fix"
            )
            return

        await self._finish(incident_id, Decision.NEEDS_HUMAN, "rounds exhausted")

    async def _verify(self) -> bool:
        if self.verify_after_seconds > 0:
            await asyncio.sleep(self.verify_after_seconds)
        # ponytail: global health, per-incident assets if mixed-fleet false positives
        assets = self.store.list_assets()
        live = [a for a in assets if a.status in {"up", "degraded"}]
        down = [a for a in assets if a.status == "down"]
        return bool(live) and not down if assets else True

    async def _finish(self, incident_id: str, decision: Decision, reason: str) -> None:
        self.store.insert_action(
            Action(
                id=uuid.uuid4().hex,
                incident_id=incident_id,
                ts=self.clock.now(),
                role="system",
                name=decision.value,
                input={},
                output=reason,
                ok=decision != Decision.NEEDS_HUMAN,
            )
        )
        if decision == Decision.RESOLVED:
            self.store.update_incident(
                incident_id, status="resolved", resolved_at=self.clock.now()
            )
            if self.on_resolved:
                self.on_resolved(incident_id, reason)
            return
        self.on_escalate(incident_id, reason)


def _brief(incident, events) -> str:
    lines = [
        f"Incident {incident.id}",
        f"title: {incident.title}",
        f"severity: {incident.severity}",
        f"fingerprint: {incident.fingerprint}",
        "events:",
    ]
    for event in reversed(events):
        lines.append(f"- [{event.level}] {event.source}: {event.message}")
        if event.body:
            lines.append(event.body[:2000])
    return "\n".join(lines)


class AgentScheduler:
    def __init__(
        self,
        loop: AgentLoop,
        max_open: int,
        set_busy: Callable[[bool], None] | None = None,
    ) -> None:
        self.loop = loop
        self._sem = asyncio.Semaphore(max(1, max_open))
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._seen: set[str] = set()
        self._inflight = 0
        self._set_busy = set_busy

    def enqueue(self, incident_id: str) -> None:
        if incident_id in self._seen:
            return
        self._seen.add(incident_id)
        self._queue.put_nowait(incident_id)

    async def run(self) -> None:
        while True:
            incident_id = await self._queue.get()
            await self._sem.acquire()
            asyncio.create_task(
                self._run_one(incident_id), name=f"triage-agent-{incident_id}"
            )

    async def _run_one(self, incident_id: str) -> None:
        self._inflight += 1
        if self._set_busy:
            self._set_busy(True)
        try:
            await self.loop.handle(incident_id)
        finally:
            self._inflight -= 1
            self._seen.discard(incident_id)
            self._sem.release()
            if self._set_busy and self._inflight == 0:
                self._set_busy(False)
