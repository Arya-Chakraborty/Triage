from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


def post_ingest(
    url: str, token: str, payload: dict[str, Any], timeout: float = 10.0
) -> bool:
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        return response.is_success
    except httpx.HTTPError:
        return False


def spool_append(path: Path, payload: dict[str, Any]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")


def flush_spool(path: Path, url: str, token: str) -> None:
    import json

    if not path.is_file():
        return
    lines = path.read_text().splitlines()
    kept: list[str] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not post_ingest(url, token, payload):
            kept.append(line)
    if kept:
        path.write_text("\n".join(kept) + "\n")
    else:
        path.unlink(missing_ok=True)
