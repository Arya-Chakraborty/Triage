from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from triage.domain.entities import Action, Asset, Event, Incident, Report


class StoreError(Exception):
    """Persistence failed. Implementations must raise this, not a sibling type."""


class Store(ABC):
    """Project SQLite (or test double). Every impl must honor these pre/postconditions."""

    @abstractmethod
    def upsert_asset(
        self,
        *,
        kind: str,
        name: str,
        source: str,
        status: str,
        meta: dict[str, Any] | None = None,
        last_seen: datetime | None = None,
        asset_id: str | None = None,
    ) -> Asset:
        """Create or update by name. Returns the stored asset."""

    @abstractmethod
    def get_asset(self, asset_id: str) -> Asset | None: ...

    @abstractmethod
    def get_asset_by_name(self, name: str) -> Asset | None: ...

    @abstractmethod
    def list_assets(self) -> list[Asset]: ...

    @abstractmethod
    def insert_event(self, event: Event) -> Event: ...

    @abstractmethod
    def get_event(self, event_id: str) -> Event | None: ...

    @abstractmethod
    def list_events(
        self,
        *,
        asset_id: str | None = None,
        level: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        """Return (page, total matching)."""

    @abstractmethod
    def events_since(self, ts: datetime) -> list[Event]: ...

    @abstractmethod
    def insert_incident(self, incident: Incident) -> Incident: ...

    @abstractmethod
    def get_incident(self, incident_id: str) -> Incident | None: ...

    @abstractmethod
    def list_incidents(self) -> list[Incident]: ...

    @abstractmethod
    def get_open_by_fingerprint(self, fingerprint: str) -> Incident | None:
        """Open or fixing incident for this fingerprint, or None."""

    @abstractmethod
    def last_resolved_by_fingerprint(self, fingerprint: str) -> Incident | None: ...

    @abstractmethod
    def update_incident(
        self,
        incident_id: str,
        *,
        status: str | None = None,
        severity: str | None = None,
        resolved_at: datetime | None = None,
        escalate_reason: str | None = None,
        title: str | None = None,
    ) -> Incident:
        """Missing id must raise StoreError."""

    @abstractmethod
    def count_agent_active(self) -> int:
        """Incidents in open or fixing (slots the agent may occupy)."""

    @abstractmethod
    def insert_action(self, action: Action) -> Action: ...

    @abstractmethod
    def list_actions(self, incident_id: str) -> list[Action]: ...

    @abstractmethod
    def insert_report(self, report: Report) -> Report: ...

    @abstractmethod
    def get_report_for_incident(self, incident_id: str) -> Report | None: ...

    @abstractmethod
    def last_report_for_fingerprint(self, fingerprint: str) -> Report | None: ...

    @abstractmethod
    def events_for_fingerprint(
        self, fingerprint: str, limit: int = 50
    ) -> list[Event]: ...
