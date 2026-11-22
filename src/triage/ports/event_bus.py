from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# Topics used by SSE: event, incident, asset, terminal
SSE_TOPICS = ("event", "incident", "asset", "terminal")


class EventBus(ABC):
    @abstractmethod
    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Fan out to subscribers. Must not raise if there are none."""

    @abstractmethod
    def subscribe(self) -> Any:
        """Return a queue-like object with async get() -> tuple[str, dict]."""

    @abstractmethod
    def unsubscribe(self, sub: Any) -> None: ...
