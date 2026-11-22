from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from triage.config.models import LogWatch
from triage.watchers.base import Watcher, emit_event, traceback_kind

Emit = Callable[[dict[str, Any]], None]


class LogTailWatcher(Watcher):
    def __init__(
        self, logs: list[LogWatch], offsets_path: Path, emit: Emit, poll: float = 0.5
    ) -> None:
        self.logs = logs
        self.offsets_path = offsets_path
        self.emit = emit
        self.poll = poll
        self._task: asyncio.Task | None = None
        self._offsets: dict[str, int] = {}

    async def start(self) -> None:
        self._offsets = _load(self.offsets_path)
        self._task = asyncio.create_task(self._run(), name="log-tail")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        while True:
            for spec in self.logs:
                await self._poll_one(spec)
            await asyncio.sleep(self.poll)

    async def _poll_one(self, spec: LogWatch) -> None:
        path = Path(spec.path)
        if not path.is_file():
            return
        key = str(path.resolve())
        size = path.stat().st_size
        offset = self._offsets.get(key, 0)
        if size < offset:
            offset = 0
        if size == offset:
            return
        data = path.read_bytes()[offset:size]
        self._offsets[key] = size
        _save(self.offsets_path, self._offsets)
        name = spec.name or path.name
        buf = data.decode("utf-8", errors="replace")
        kind = traceback_kind(buf)
        for line in buf.splitlines():
            if not line.strip():
                continue
            level = "error" if kind or "error" in line.lower() else "info"
            await emit_event(
                self.emit,
                {
                    "level": level,
                    "source": "log",
                    "message": line[:2000],
                    "body": buf[:8000] if kind else "",
                    "asset_name": name,
                    "kind": "server",
                    "meta": {"path": str(path), "traceback": kind},
                },
            )
            if kind:
                kind = None  # one incident-quality event per chunk


def _load(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    try:
        return {k: int(v) for k, v in json.loads(path.read_text()).items()}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _save(path: Path, offsets: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(offsets))
