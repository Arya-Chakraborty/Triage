from __future__ import annotations

import hmac
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from triage.ingest.service import IngestService

MAX_BODY = 256 * 1024


def ingest_router(service: IngestService, token: str) -> APIRouter:
    router = APIRouter()

    @router.post("/ingest")
    async def ingest(request: Request) -> dict[str, Any]:
        raw = await request.body()
        if len(raw) > MAX_BODY:
            raise HTTPException(413, "body exceeds 256KB")
        _require_bearer(request.headers.get("Authorization", ""), token)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(400, "invalid json") from exc
        if not isinstance(payload, dict):
            raise HTTPException(400, "json object required")
        try:
            return await service.handle_payload(payload)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    return router


def _require_bearer(header: str, token: str) -> None:
    if not token or not header.startswith("Bearer "):
        raise HTTPException(401, "unauthorized")
    got = header[7:].strip()
    if not hmac.compare_digest(got, token):
        raise HTTPException(401, "unauthorized")
