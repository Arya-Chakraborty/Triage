"""Strip secrets before any LLM call or report."""

from __future__ import annotations

import re
from pathlib import Path

_ASSIGN = re.compile(
    r"(?i)(\b(?:api[_-]?key|secret|password|passwd|token|authorization|bearer)\b\s*[=:]\s*)(\S+)"
)
_PEM = re.compile(
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----"
)
_GOOGLE = re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")
_OPENAI = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_ENV_LINE = re.compile(r"^([A-Za-z_][\w]*)=(.+)$", re.M)

_SECRET_NAMES = {".env", "credentials", "credentials.json", "secrets"}
_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


def looks_secret_path(path: str | Path) -> bool:
    p = Path(path)
    name = p.name.lower()
    if name in _SECRET_NAMES or name.endswith(".env"):
        return True
    return p.suffix.lower() in _SECRET_SUFFIXES


def redact(text: str) -> str:
    if not text:
        return text
    out = _PEM.sub("<REDACTED_PEM>", text)
    out = _JWT.sub("<REDACTED_JWT>", out)
    out = _GOOGLE.sub("<REDACTED_KEY>", out)
    out = _OPENAI.sub("<REDACTED_KEY>", out)
    out = _ASSIGN.sub(r"\1<REDACTED>", out)
    return out


def redact_file_text(path: str | Path, text: str) -> str:
    if looks_secret_path(path):
        return _ENV_LINE.sub(r"\1=<REDACTED>", text)
    return redact(text)
