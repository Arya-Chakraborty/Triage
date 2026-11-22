from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from triage.domain.entities import Asset, to_iso


@dataclass
class AppState:
    agent_busy: bool = False
    terminals: dict[str, dict[str, Any]] = field(default_factory=dict)
    health: dict[str, dict[str, Any]] = field(default_factory=dict)
    collectors: dict[str, dict[str, Any]] = field(default_factory=dict)

    def set_busy(self, busy: bool) -> None:
        self.agent_busy = busy

    def note_health(self, row: dict[str, Any]) -> None:
        self.health[row["name"]] = row

    def note_heartbeat(self, hostname: str, now: datetime) -> None:
        prev = self.collectors.get(hostname) or {"hostname": hostname, "event_count": 0}
        prev["last_seen"] = to_iso(now)
        prev["event_count"] = int(prev.get("event_count") or 0) + 1
        self.collectors[hostname] = prev

    def note_terminal(self, asset: Asset, line: str) -> None:
        item = self.terminals.get(asset.id) or {
            "id": asset.id,
            "name": asset.name,
            "asset_id": asset.id,
            "alive": asset.status == "up",
            "last_lines": deque(maxlen=50),
        }
        item["alive"] = asset.status == "up"
        item["name"] = asset.name
        if line:
            item["last_lines"].append(line[:500])
        self.terminals[asset.id] = item

    def terminal_items(self) -> list[dict[str, Any]]:
        out = []
        for item in self.terminals.values():
            lines = item.get("last_lines") or []
            out.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "asset_id": item["asset_id"],
                    "alive": bool(item.get("alive")),
                    "last_lines": list(lines),
                }
            )
        return out
