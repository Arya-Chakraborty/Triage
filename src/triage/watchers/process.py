from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from triage.ports.process_runner import ProcessRunner
from triage.ports.store import Store
from triage.watchers.base import Watcher, cancel_task, emit_event

Emit = Callable[[dict[str, Any]], None]


class ProcessWatcher(Watcher):
    """Poll `triage run` assets; nonzero exit is an incident."""

    def __init__(
        self, store: Store, runner: ProcessRunner, emit: Emit, interval: float = 2.0
    ) -> None:
        self.store = store
        self.runner = runner
        self.emit = emit
        self.interval = interval
        self._task: asyncio.Task | None = None
        self._announced: set[str] = set()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="process-watch")

    async def stop(self) -> None:
        await cancel_task(self._task)
        self._task = None

    async def _run(self) -> None:
        while True:
            for asset in self.store.list_assets():
                if asset.kind != "process":
                    continue
                pid = int(asset.meta.get("pid") or 0)
                if not pid:
                    continue
                alive = self.runner.is_alive(pid)
                if alive:
                    self._announced.discard(asset.id)
                    if asset.status != "up":
                        self.store.upsert_asset(
                            kind=asset.kind,
                            name=asset.name,
                            source=asset.source,
                            status="up",
                            meta=asset.meta,
                        )
                    continue
                if asset.id in self._announced:
                    continue
                self._announced.add(asset.id)
                self.store.upsert_asset(
                    kind=asset.kind,
                    name=asset.name,
                    source=asset.source,
                    status="down",
                    meta=asset.meta,
                )
                await emit_event(
                    self.emit,
                    {
                        "level": "error",
                        "source": "process",
                        "message": f"{asset.name} process not running (pid {pid})",
                        "asset_name": asset.name,
                        "kind": "process",
                        "meta": {
                            "pid": pid,
                            "exit_code": asset.meta.get("exit_code", 1),
                        },
                    },
                )
            await asyncio.sleep(self.interval)
