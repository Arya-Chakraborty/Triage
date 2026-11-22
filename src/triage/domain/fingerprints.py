"""Stable incident fingerprints from noisy log/traceback text."""

from __future__ import annotations

import hashlib
import re

_TS = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
    r"|\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b"
)
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_MEM = re.compile(r"\b0x[0-9a-fA-F]+\b")
_HEX_ID = re.compile(r"\b[0-9a-fA-F]{8,}\b")
_PID = re.compile(r"\bpid[=: ]?\d+\b", re.I)

_PY_FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')
_NODE_FRAME = re.compile(r"at (\S+) \(([^):]+):(\d+)(?::\d+)?\)")
_JAVA_FRAME = re.compile(r"at ([\w.$]+)\(([^:]+):(\d+)\)")
_GO_FRAME = re.compile(r"(\S+\.go):(\d+)(?: \+0x[0-9a-fA-F]+)?")

_PY_EXC = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Exit|Fault)):", re.M)
_JAVA_EXC = re.compile(r"\b([\w.$]*(?:Exception|Error))\b")
_PANIC = re.compile(r"^panic:", re.M)


def normalize_message(message: str) -> str:
    text = message or ""
    text = _TS.sub("<TS>", text)
    text = _UUID.sub("<ID>", text)
    text = _MEM.sub("<ADDR>", text)
    text = _PID.sub("<PID>", text)
    text = _HEX_ID.sub("<HEX>", text)
    return re.sub(r"\s+", " ", text).strip()


def exception_class(text: str) -> str:
    if not text:
        return ""
    if _PANIC.search(text):
        return "panic"
    match = _PY_EXC.search(text)
    if match:
        return match.group(1)
    match = _JAVA_EXC.search(text)
    if match:
        return match.group(1)
    return ""


def top_stack_frames(text: str, limit: int = 3) -> list[str]:
    if not text:
        return []
    frames: list[str] = []
    for match in _PY_FRAME.finditer(text):
        frames.append(f"{_basename(match.group(1))}:{match.group(2)}:{match.group(3)}")
    for match in _NODE_FRAME.finditer(text):
        frames.append(f"{_basename(match.group(2))}:{match.group(3)}:{match.group(1)}")
    for match in _JAVA_FRAME.finditer(text):
        frames.append(f"{match.group(2)}:{match.group(3)}:{match.group(1)}")
    if not frames:
        for match in _GO_FRAME.finditer(text):
            frames.append(f"{_basename(match.group(1))}:{match.group(2)}")
    return frames[:limit]


def fingerprint(source: str, message: str, body: str = "") -> str:
    """sha1(source + exception_class + top_3_stack_frames + normalized_message)."""
    blob = "\n".join(filter(None, [body, message]))
    exc = exception_class(blob)
    frames = "".join(top_stack_frames(blob, 3))
    payload = f"{source}{exc}{frames}{normalize_message(message)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").split("/")[-1]
