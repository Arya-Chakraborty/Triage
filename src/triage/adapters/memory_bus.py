from __future__ import annotations

import asyncio
from typing import Any

from triage.ports.event_bus import EventBus


class MemoryEventBus(EventBus):
    def __init__(self) -> None:
        self._subs: list[asyncio.Queue] = []

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait((event_type, data))
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subs.append(q)
        return q

    def unsubscribe(self, sub: Any) -> None:
        try:
            self._subs.remove(sub)
        except ValueError:
            pass
