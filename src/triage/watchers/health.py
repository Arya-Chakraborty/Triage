from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import httpx

from triage.config.models import HealthWatch
from triage.watchers.base import Watcher, cancel_task, emit_event

Emit = Callable[[dict[str, Any]], None]


class HealthWatcher(Watcher):
    def __init__(
        self,
        targets: list[HealthWatch],
        emit: Emit,
        on_check: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.targets = targets
        self.emit = emit
        self.on_check = on_check
        self._fails: dict[str, int] = {}
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="health")

    async def stop(self) -> None:
        await cancel_task(self._task)
        self._task = None

    async def _run(self) -> None:
        while True:
            delay = min((t.interval for t in self.targets), default=15)
            for target in self.targets:
                await self._check(target)
            await asyncio.sleep(max(1, delay))

    async def _check(self, target: HealthWatch) -> None:
        start = datetime.now(timezone.utc)
        ok = False
        latency = 0
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(target.url)
            latency = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            ok = response.is_success
        except httpx.HTTPError:
            latency = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            ok = False

        if self.on_check:
            self.on_check(
                {
                    "name": target.name,
                    "url": target.url,
                    "ok": ok,
                    "latency_ms": latency,
                    "last_check": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            )

        if ok:
            was = self._fails.get(target.name, 0)
            self._fails[target.name] = 0
            await emit_event(
                self.emit,
                {
                    "level": "info",
                    "source": "health",
                    "message": f"{target.name} recovered"
                    if was
                    else f"{target.name} ok",
                    "asset_name": target.name,
                    "kind": "url",
                    "meta": {
                        "url": target.url,
                        "ok": True,
                        "consecutive_failures": 0,
                        "recovered": was >= 2,
                    },
                },
            )
            return

        n = self._fails.get(target.name, 0) + 1
        self._fails[target.name] = n
        await emit_event(
            self.emit,
            {
                "level": "error" if n >= 2 else "warning",
                "source": "health",
                "message": f"{target.name} health failed ({n}x)",
                "asset_name": target.name,
                "kind": "url",
                "meta": {"url": target.url, "ok": False, "consecutive_failures": n},
            },
        )
