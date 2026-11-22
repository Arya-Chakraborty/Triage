from __future__ import annotations

from typing import Any

from triage.agent.tools.base import (
    SandboxError,
    Tool,
    ToolContext,
    ToolResult,
    resolve_in_sandbox,
)


class ListDirTool(Tool):
    name = "list_dir"
    description = "List files in a sandbox directory."
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "recurse": {"type": "boolean"},
        },
        "required": ["path"],
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        try:
            path = resolve_in_sandbox(str(args.get("path") or "."), ctx.sandbox_root)
        except SandboxError as exc:
            return ToolResult(ok=False, output=str(exc), sandbox_violation=True)
        if not path.exists():
            return ToolResult(ok=False, output=f"missing: {path}")
        recurse = bool(args.get("recurse"))
        names: list[str] = []
        iterator = path.rglob("*") if recurse else path.iterdir()
        for item in iterator:
            if ".git" in item.parts:
                continue
            rel = item.relative_to(ctx.sandbox_root)
            names.append(str(rel) + ("/" if item.is_dir() else ""))
            if len(names) >= 500:
                names.append("...truncated")
                break
        return ToolResult(ok=True, output="\n".join(sorted(names)))
