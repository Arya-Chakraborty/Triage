from __future__ import annotations

import os
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path

from triage.config.loader import load_config, load_secrets
from triage.ingest.client import flush_spool, post_ingest, spool_append
from triage.watchers.base import traceback_kind


def run_ship(root: Path | None = None) -> None:
    """Remote collector: heartbeats, log tail, optional docker logs. Never runs agent tools."""
    cfg = load_config(root)
    secrets = load_secrets()
    url = cfg.ingest_url
    token = secrets.ingest_token
    if not token:
        raise SystemExit("INGEST_TOKEN missing; run triage init")
    spool = cfg.project_root / ".triage" / "spool.jsonl"
    host = socket.gethostname()
    stop = threading.Event()

    def send(payload: dict) -> None:
        flush_spool(spool, url, token)
        if not post_ingest(url, token, payload):
            spool_append(spool, payload)

    def heartbeat() -> None:
        while not stop.is_set():
            send({"type": "heartbeat", "hostname": host, "meta": {"pid": os.getpid()}})
            stop.wait(30)

    def tail_file(path: Path, name: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        with path.open("r", errors="replace") as fh:
            fh.seek(0, os.SEEK_END)
            while not stop.is_set():
                line = fh.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                kind = traceback_kind(line)
                send(
                    {
                        "events": [
                            {
                                "level": "error"
                                if kind or "error" in line.lower()
                                else "info",
                                "source": "ship",
                                "message": line.strip()[:2000],
                                "asset_name": name,
                                "kind": "server",
                                "meta": {"hostname": host, "path": str(path)},
                            }
                        ]
                    }
                )

    threads = [threading.Thread(target=heartbeat, daemon=True)]
    for spec in cfg.watch.logs:
        threads.append(
            threading.Thread(
                target=tail_file,
                args=(Path(spec.path), spec.name or Path(spec.path).name),
                daemon=True,
            )
        )
    for container in cfg.ship.docker_containers:
        threads.append(
            threading.Thread(
                target=_docker_logs, args=(container, host, send, stop), daemon=True
            )
        )
    for t in threads:
        t.start()

    def _stop(*_args) -> None:
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    while not stop.is_set():
        time.sleep(1)


def _docker_logs(container: str, host: str, send, stop) -> None:
    try:
        proc = subprocess.Popen(
            ["docker", "logs", "-f", "--since", "0s", container],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        return
    assert proc.stdout is not None
    while not stop.is_set():
        line = proc.stdout.readline()
        if not line:
            break
        send(
            {
                "events": [
                    {
                        "level": "error" if "error" in line.lower() else "info",
                        "source": "docker",
                        "message": line.strip()[:2000],
                        "asset_name": container,
                        "kind": "server",
                        "meta": {"hostname": host, "container": container},
                    }
                ]
            }
        )
    proc.terminate()
