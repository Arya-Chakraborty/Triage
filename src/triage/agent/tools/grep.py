from __future__ import annotations

import re
from typing import Any

from triage.agent.tools.base import (
    SandboxError,
    Tool,
    ToolContext,
    ToolResult,
    resolve_in_sandbox,
)

_MAX = 32 * 1024


class GrepTool(Tool):
    name = "grep"
    description = "Search sandbox files for a regex."
    schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["pattern"],
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        try:
            regex = re.compile(str(args.get("pattern") or ""))
            root = resolve_in_sandbox(str(args.get("path") or "."), ctx.sandbox_root)
        except re.error as exc:
            return ToolResult(ok=False, output=f"bad pattern: {exc}")
        except SandboxError as exc:
            return ToolResult(ok=False, output=str(exc), sandbox_violation=True)
        hits: list[str] = []
        files = [root] if root.is_file() else root.rglob("*")
        for item in files:
            if not item.is_file() or ".git" in item.parts:
                continue
            try:
                raw = item.read_bytes()
            except OSError:
                continue
            if b"\0" in raw[:4096]:
                continue
            text = raw.decode("utf-8", errors="replace")
            rel = item.relative_to(ctx.sandbox_root)
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    hits.append(f"{rel}:{i}:{line}")
                    if len(hits) >= 100:
                        break
            if len(hits) >= 100:
                break
        out = "\n".join(hits)[:_MAX]
        return ToolResult(ok=True, output=out or "(no matches)")
