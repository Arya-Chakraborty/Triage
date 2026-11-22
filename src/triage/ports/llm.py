from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class LLMError(Exception):
    """LLM call failed. Implementations must raise this, not a sibling type."""


@dataclass
class FunctionCall:
    name: str
    args: dict[str, Any]


@dataclass
class LLMRequest:
    model: str
    system: str
    contents: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    max_tokens: int | None = None


@dataclass
class LLMResponse:
    text: str = ""
    function_calls: list[FunctionCall] = field(default_factory=list)
    tokens_used: int = 0


class LLMClient(ABC):
    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """One model turn. Must not execute tools (no automatic function calling)."""
