from __future__ import annotations

import asyncio
import inspect
import re
from abc import ABC, abstractmethod
from typing import Any

_PY = re.compile(r"Traceback \(most recent call last\):")
_NODE = re.compile(r"^\s*at \S+ \(.+:\d+:\d+\)", re.M)
_JAVA = re.compile(r"Exception in thread |\tat [\w$.]+\([\w.]+:\d+\)")
_PANIC = re.compile(r"^panic: |\ngoroutine \d+ \[", re.M)


class Watcher(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...


async def cancel_task(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def emit_event(emit, payload: dict[str, Any]) -> None:
    result = emit(payload)
    if inspect.isawaitable(result):
        await result


def traceback_kind(text: str) -> str | None:
    if not text:
        return None
    if _PY.search(text):
        return "python"
    if _PANIC.search(text):
        return "panic"
    if _JAVA.search(text):
        return "java"
    if _NODE.search(text):
        return "node"
    return None
