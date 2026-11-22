"""Escalate vs auto-fix is CODE, not the model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from triage.agent.tools.base import ToolResult
from triage.domain.incident_policy import recurrence_needs_human


class Decision(str, Enum):
    CONTINUE = "continue"
    RESOLVED = "resolved"
    NEEDS_HUMAN = "needs_human"


@dataclass(frozen=True)
class PolicyVerdict:
    decision: Decision
    reason: str = ""


class AgentPolicy:
    def __init__(
        self,
        *,
        max_rounds: int = 12,
        token_budget: int = 100_000,
        cooldown_seconds: int = 3600,
        repeat_limit: int = 3,
    ) -> None:
        self.max_rounds = max_rounds
        self.token_budget = token_budget
        self.cooldown_seconds = cooldown_seconds
        self.repeat_limit = repeat_limit

    def on_start(
        self,
        *,
        last_resolved_at: datetime | None,
        now: datetime,
        auto_fix: bool,
    ) -> PolicyVerdict | None:
        if not auto_fix:
            return PolicyVerdict(Decision.NEEDS_HUMAN, "auto_fix disabled")
        if recurrence_needs_human(last_resolved_at, now, self.cooldown_seconds):
            return PolicyVerdict(
                Decision.NEEDS_HUMAN, "same fingerprint recurred within cooldown"
            )
        return None

    def after_round(
        self,
        *,
        round_index: int,
        tokens_used: int,
        repeats: dict[str, int],
        tool_name: str | None,
        result: ToolResult | None,
        claimed_fix: bool,
        verified_healthy: bool,
    ) -> PolicyVerdict | None:
        if result is not None and result.escalate:
            return PolicyVerdict(Decision.NEEDS_HUMAN, result.output or "escalate tool")
        if result is not None and result.sandbox_violation:
            return PolicyVerdict(Decision.NEEDS_HUMAN, "write/path outside sandbox")
        if result is not None and result.denied:
            return PolicyVerdict(Decision.NEEDS_HUMAN, "shell command denied")
        if tool_name and repeats.get(tool_name, 0) >= self.repeat_limit:
            return PolicyVerdict(Decision.NEEDS_HUMAN, "same tool+args repeated 3x")
        if tokens_used > self.token_budget:
            return PolicyVerdict(Decision.NEEDS_HUMAN, "token budget exceeded")
        if claimed_fix and verified_healthy:
            return PolicyVerdict(Decision.RESOLVED, "claimed fix verified")
        if round_index >= self.max_rounds:
            return PolicyVerdict(Decision.NEEDS_HUMAN, "rounds exhausted")
        return None
