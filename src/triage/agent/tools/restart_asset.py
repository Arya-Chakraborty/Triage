from __future__ import annotations

from typing import Any

from triage.agent.tools.base import Tool, ToolContext, ToolResult


class RestartAssetTool(Tool):
    name = "restart_asset"
    description = (
        "Restart a process started with `triage run`. Other kinds are refused."
    )
    schema = {
        "type": "object",
        "properties": {"asset_id": {"type": "string"}, "name": {"type": "string"}},
    }

    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        asset = None
        if args.get("asset_id"):
            asset = ctx.store.get_asset(str(args["asset_id"]))
        elif args.get("name"):
            asset = ctx.store.get_asset_by_name(str(args["name"]))
        if asset is None:
            return ToolResult(ok=False, output="asset not found")
        if asset.kind != "process" or asset.meta.get("managed_by") != "triage run":
            return ToolResult(
                ok=False, output="only triage run process assets can be restarted"
            )
        argv = asset.meta.get("argv") or []
        if not argv:
            return ToolResult(ok=False, output="asset has no argv")
        old = int(asset.meta.get("pid") or 0)
        if old:
            ctx.process_runner.terminate(old)
        cwd = asset.meta.get("cwd")
        pid = ctx.process_runner.spawn(list(argv), cwd=cwd)
        ctx.store.upsert_asset(
            kind=asset.kind,
            name=asset.name,
            source=asset.source,
            status="up",
            meta={**asset.meta, "pid": pid},
            last_seen=ctx.clock.now(),
        )
        return ToolResult(ok=True, output=f"restarted {asset.name} pid={pid}")
