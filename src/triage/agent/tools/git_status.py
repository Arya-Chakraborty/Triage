from __future__ import annotations

import subprocess
from typing import Any

from triage.agent.tools.base import Tool, ToolContext, ToolResult


class GitStatusTool(Tool):
    name = "git_status"
    description = "Show git status in the sandbox."
    schema = {"type": "object", "properties": {}}

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        proc = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=ctx.sandbox_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return ToolResult(
            ok=proc.returncode == 0, output=(proc.stdout or proc.stderr)[: 32 * 1024]
        )
