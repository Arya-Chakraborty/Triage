from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from triage.domain.entities import Incident
from triage.ports.clock import Clock
from triage.ports.process_runner import ProcessRunner
from triage.ports.store import Store


class SandboxError(PermissionError):
    """Path escaped sandbox_root."""


@dataclass
class ToolResult:
    ok: bool
    output: str
    denied: bool = False
    sandbox_violation: bool = False
    escalate: bool = False
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolContext:
    sandbox_root: Path
    store: Store
    clock: Clock
    process_runner: ProcessRunner
    incident: Incident
    allow_shell: bool
    allow_git_commit: bool


class Tool(ABC):
    name: str = ""
    description: str = ""
    schema: dict[str, Any] = {}

    @abstractmethod
    def execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        """Always return ToolResult. Never raise a type the loop does not catch."""

    def declaration(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "schema": self.schema,
        }


def resolve_in_sandbox(path: str, root: Path) -> Path:
    root = root.resolve()
    raw = Path(path)
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve()
    if resolved != root and not _is_relative_to(resolved, root):
        raise SandboxError(f"{path} is outside sandbox")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
