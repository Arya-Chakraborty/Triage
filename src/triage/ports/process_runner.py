from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence


class ProcessRunner(ABC):
    @abstractmethod
    def spawn(self, argv: Sequence[str], cwd: str | None = None) -> int:
        """Start argv detached. Returns pid. Raises RuntimeError on spawn failure."""

    @abstractmethod
    def is_alive(self, pid: int) -> bool: ...

    @abstractmethod
    def terminate(self, pid: int) -> None:
        """Best-effort terminate. Missing pid is not an error."""

    @abstractmethod
    def terminate_all(self) -> None:
        """Terminate every pid this runner spawned. Missing pids are not an error."""
