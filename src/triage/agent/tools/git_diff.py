from __future__ import annotations

import subprocess
from typing import Any

from triage.agent.tools.base import Tool, ToolContext, ToolResult


class GitDiffTool(Tool):
    name = "git_diff"
    description = "Show git diff in the sandbox."
    schema = {
        "type": "object",
        "properties": {"staged": {"type": "boolean"}},
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        cmd = ["git", "diff"]
        if args.get("staged"):
            cmd.append("--cached")
        proc = subprocess.run(
            cmd, cwd=ctx.sandbox_root, capture_output=True, text=True, timeout=15
        )
        return ToolResult(
            ok=proc.returncode == 0, output=(proc.stdout or proc.stderr)[: 32 * 1024]
        )
