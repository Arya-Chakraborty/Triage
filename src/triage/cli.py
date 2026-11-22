from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

import httpx

from triage import __version__
from triage.adapters.pty_runner import run_pty
from triage.config.loader import load_config, load_secrets, run_init
from triage.ingest.client import post_ingest, spool_append
from triage.watchers.base import traceback_kind


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="triage", description="Project-local incident control plane"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Write .triage.yaml and ~/.triage/secrets")
    sub.add_parser("watch", help="Run watchers, ingest, agent, and dashboard")

    run_p = sub.add_parser("run", help="PTY-wrap a process and stream events")
    run_p.add_argument("--name", required=True)
    # dest must not be "cmd" — that would overwrite the subparser name
    run_p.add_argument("argv", nargs=argparse.REMAINDER)

    sub.add_parser("ship", help="Remote collector (heartbeats, logs, docker)")
    sub.add_parser("status", help="Daemon URL, asset health, open incidents")

    ev = sub.add_parser("event", help="Manual/CI ingest of a deploy event")
    ev.add_argument(
        "name", choices=["deploy.started", "deploy.failed", "deploy.succeeded"]
    )
    ev.add_argument("--sha", default="")
    ev.add_argument("--env", default="")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "init":
            path = run_init()
            print(f"wrote {path}")
            return 0
        if args.cmd == "watch":
            from triage.daemon import run_watch_sync

            run_watch_sync()
            return 0
        if args.cmd == "run":
            return _run(args)
        if args.cmd == "ship":
            from triage.collector.shipper import run_ship

            run_ship()
            return 0
        if args.cmd == "status":
            return _status()
        if args.cmd == "event":
            return _event(args)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


def _send(payload: dict) -> None:
    cfg = load_config()
    secrets = load_secrets()
    url = cfg.ingest_url
    token = secrets.ingest_token
    if not post_ingest(url, token, payload):
        spool_append(cfg.project_root / ".triage" / "spool.jsonl", payload)


def _run(args: argparse.Namespace) -> int:
    argv = list(args.argv)
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print("triage run --name NAME -- CMD", file=sys.stderr)
        return 2
    cfg = load_config()  # noqa: F841 — validates config exists
    buf = b""
    meta = {
        "managed_by": "triage run",
        "argv": argv,
        "cwd": str(Path.cwd()),
        "host": socket.gethostname(),
    }

    def on_bytes(chunk: bytes) -> None:
        nonlocal buf
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            text = line.decode("utf-8", errors="replace")
            kind = traceback_kind(text)
            _send(
                {
                    "events": [
                        {
                            "level": "error" if kind else "info",
                            "source": "pty",
                            "message": text[:2000],
                            "asset_name": args.name,
                            "kind": "process",
                            "meta": meta,
                        }
                    ]
                }
            )

    _send(
        {
            "events": [
                {
                    "level": "info",
                    "source": "process",
                    "message": f"started {' '.join(argv)}",
                    "asset_name": args.name,
                    "kind": "process",
                    "meta": {**meta, "pid": 0},
                }
            ]
        }
    )

    def on_pid(pid: int) -> None:
        meta["pid"] = pid
        _send(
            {
                "events": [
                    {
                        "level": "info",
                        "source": "process",
                        "message": f"{args.name} pid {pid}",
                        "asset_name": args.name,
                        "kind": "process",
                        "meta": meta,
                    }
                ]
            }
        )

    code = run_pty(argv, on_bytes, on_pid=on_pid)
    _send(
        {
            "events": [
                {
                    "level": "error" if code else "info",
                    "source": "process",
                    "message": f"{args.name} exited {code}",
                    "asset_name": args.name,
                    "kind": "process",
                    "meta": {**meta, "exit_code": code},
                }
            ]
        }
    )
    return code


def _status() -> int:
    cfg = load_config()
    base = cfg.dashboard_url
    try:
        overview = httpx.get(f"{base}/api/overview", timeout=5.0).json()
        incidents = httpx.get(f"{base}/api/incidents", timeout=5.0).json()
        assets = httpx.get(f"{base}/api/assets", timeout=5.0).json()
    except httpx.HTTPError:
        print(f"daemon unreachable at {base}")
        return 1
    print(f"daemon: {base}")
    print(f"assets: {overview.get('assets_up')} up, {overview.get('assets_down')} down")
    print(f"open incidents: {overview.get('open_incidents')}")
    print(f"event rate/min: {overview.get('event_rate_per_min')}")
    print(f"agent busy: {overview.get('agent_busy')}")
    for item in incidents.get("items") or []:
        if item.get("status") in {"open", "fixing", "needs_human"}:
            print(
                f"  [{item.get('severity')}] {item.get('title')} ({item.get('id')[:8]}) {item.get('status')}"
            )
    for item in assets.get("items") or []:
        print(f"  asset {item.get('name')} {item.get('status')}")
    return 0


def _event(args: argparse.Namespace) -> int:
    status = args.name.split(".", 1)[1]
    _send({"type": "deploy", "status": status, "sha": args.sha, "env": args.env})
    print(f"sent {args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
