from __future__ import annotations

import subprocess
from typing import Any

from triage.agent.tools.base import (
    SandboxError,
    Tool,
    ToolContext,
    ToolResult,
    resolve_in_sandbox,
)


class GitCommitTool(Tool):
    name = "git_commit"
    description = "Commit listed files. Off unless allow_git_commit. Never pushes."
    schema = {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "files": {"type": "array"},
        },
        "required": ["message", "files"],
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        if not ctx.allow_git_commit:
            return ToolResult(ok=False, output="git_commit disabled")
        files = args.get("files") or []
        if not files:
            return ToolResult(ok=False, output="files required")
        rels = []
        try:
            for f in files:
                path = resolve_in_sandbox(str(f), ctx.sandbox_root)
                rels.append(str(path.relative_to(ctx.sandbox_root)))
        except SandboxError as exc:
            return ToolResult(ok=False, output=str(exc), sandbox_violation=True)
        add = subprocess.run(
            ["git", "add", "--", *rels],
            cwd=ctx.sandbox_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if add.returncode != 0:
            return ToolResult(ok=False, output=add.stderr or add.stdout)
        proc = subprocess.run(
            ["git", "commit", "-m", str(args.get("message") or "triage fix")],
            cwd=ctx.sandbox_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return ToolResult(
            ok=proc.returncode == 0, output=(proc.stdout or proc.stderr)[: 32 * 1024]
        )
