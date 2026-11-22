from __future__ import annotations

from typing import Any

from triage.agent.tools.base import (
    SandboxError,
    Tool,
    ToolContext,
    ToolResult,
    resolve_in_sandbox,
)


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write a UTF-8 file under the sandbox. Creates parents."
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        try:
            path = resolve_in_sandbox(str(args.get("path") or ""), ctx.sandbox_root)
        except SandboxError as exc:
            return ToolResult(ok=False, output=str(exc), sandbox_violation=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(args.get("content") or ""), encoding="utf-8")
        return ToolResult(ok=True, output=f"wrote {path}")
