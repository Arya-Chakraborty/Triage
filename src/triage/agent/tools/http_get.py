from __future__ import annotations

from typing import Any

import httpx

from triage.agent.tools.base import Tool, ToolContext, ToolResult

_MAX = 32 * 1024


class HttpGetTool(Tool):
    name = "http_get"
    description = "HTTP GET a URL and return text (32KB cap)."
    schema = {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        url = str(args.get("url") or "")
        if not url.startswith(("http://", "https://")):
            return ToolResult(ok=False, output="url must be http(s)")
        try:
            response = httpx.get(url, timeout=10.0, follow_redirects=True)
        except httpx.HTTPError as exc:
            return ToolResult(ok=False, output=str(exc))
        return ToolResult(
            ok=response.is_success,
            output=f"status={response.status_code}\n{response.text[:_MAX]}",
        )
