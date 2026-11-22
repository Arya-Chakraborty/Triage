from __future__ import annotations

import json
from typing import Any

from triage.agent.tools.base import Tool, ToolContext, ToolResult


class QueryStoreTool(Tool):
    name = "query_store"
    description = "Read-only query of assets, events, or incidents."
    schema = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "description": "assets|events|incidents"},
            "limit": {"type": "integer"},
        },
        "required": ["kind"],
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        kind = str(args.get("kind") or "")
        limit = int(args.get("limit") or 20)
        if kind == "assets":
            payload = [a.to_api() for a in ctx.store.list_assets()[:limit]]
        elif kind == "events":
            items, _ = ctx.store.list_events(limit=limit, offset=0)
            payload = [e.to_api() for e in items]
        elif kind == "incidents":
            payload = [i.to_api() for i in ctx.store.list_incidents()[:limit]]
        else:
            return ToolResult(
                ok=False, output="kind must be assets, events, or incidents"
            )
        return ToolResult(ok=True, output=json.dumps(payload, default=str)[: 32 * 1024])
