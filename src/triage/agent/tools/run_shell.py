from __future__ import annotations

import re
import subprocess
from typing import Any

from triage.agent.tools.base import Tool, ToolContext, ToolResult

_MAX = 32 * 1024
_TIMEOUT = 30

_DENIED = [
    re.compile(r"\brm\s+-[^\n]*\brf\b|\brm\s+-[^\n]*\bfr\b"),
    re.compile(r"\bsudo\b"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\b"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"push\s+--force|--force\s+push|git\s+push\s+[^\n]*\s-f\b"),
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"curl[^\n]*\|\s*(sh|bash|zsh)|wget[^\n]*\|"),
]


def command_denied(command: str) -> bool:
    return any(pat.search(command) for pat in _DENIED)


class RunShellTool(Tool):
    name = "run_shell"
    description = "Run a shell command in the sandbox. Denied: rm -rf, sudo, mkfs, dd, shutdown, git push, curl|pipe."
    schema = {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        if not ctx.allow_shell:
            return ToolResult(ok=False, output="shell disabled", denied=True)
        command = str(args.get("command") or "")
        if command_denied(command):
            return ToolResult(ok=False, output="command denied by policy", denied=True)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=ctx.sandbox_root,
                capture_output=True,
                timeout=_TIMEOUT,
                text=True,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, output=f"timeout after {_TIMEOUT}s")
        out = (proc.stdout or "") + (proc.stderr or "")
        return ToolResult(ok=proc.returncode == 0, output=out[:_MAX])
