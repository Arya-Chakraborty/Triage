from __future__ import annotations

from abc import ABC, abstractmethod


class Mailer(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None:
        """Deliver or raise. A configured-off impl may return without sending."""
