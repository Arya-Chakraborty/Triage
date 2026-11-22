from __future__ import annotations

from typing import Any

from triage.agent.tools.base import Tool, ToolContext, ToolResult


class EscalateTool(Tool):
    name = "escalate"
    description = "Stop auto-fix and hand this incident to a human. Use when destructive, ambiguous, needs secrets, or unverifiable."
    schema = {
        "type": "object",
        "properties": {"reason": {"type": "string"}},
        "required": ["reason"],
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        reason = str(args.get("reason") or "model requested escalate")
        return ToolResult(ok=True, output=reason, escalate=True)
