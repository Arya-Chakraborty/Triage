from __future__ import annotations

from typing import Any

from triage.agent.tools.base import (
    SandboxError,
    Tool,
    ToolContext,
    ToolResult,
    resolve_in_sandbox,
)
from triage.domain.redaction import redact_file_text

_MAX = 64 * 1024


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a UTF-8 file under the sandbox."
    schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        try:
            path = resolve_in_sandbox(str(args.get("path") or ""), ctx.sandbox_root)
        except SandboxError as exc:
            return ToolResult(ok=False, output=str(exc), sandbox_violation=True)
        if not path.is_file():
            return ToolResult(ok=False, output=f"not a file: {path}")
        data = path.read_bytes()[:_MAX]
        text = data.decode("utf-8", errors="replace")
        return ToolResult(ok=True, output=redact_file_text(path, text))
