"""AgentEngine — abstract base class for all engine implementations.

Defines the shared protocol that every engine (Claude, OpenAI, local, mock)
must satisfy.  Two supporting dataclasses live here too:

- ``Message``        — a single turn in a conversation
- ``ToolDefinition`` — a tool the agent may call, with schema generation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Message:
    """A single message in an agent conversation.

    Parameters
    ----------
    role:
        One of "system", "user", "assistant", "tool".
    content:
        Text content of the message (may be empty string for tool-call-only turns).
    tool_calls:
        Optional list of tool-call dicts produced by the model.
    tool_call_id:
        When role=="tool", the ID of the tool call this message responds to.
    metadata:
        Arbitrary extra data (timestamps, token counts, etc.).
    """

    role: str
    content: str
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ToolDefinition:
    """A tool that can be offered to an engine.

    Parameters
    ----------
    name:
        Tool name (PascalCase by convention, e.g. "Store", "Ask").
    description:
        Human-readable description passed to the model.
    parameters:
        Dict mapping param name -> dict with keys ``type`` and optionally
        ``required`` (bool), ``description`` (str), ``enum`` (list).
    """

    name: str
    description: str
    parameters: dict

    def to_schema(self) -> dict:
        """Return an OpenAI-compatible function-calling schema dict.

        The ``required`` list is built from parameters whose dict contains
        ``"required": True``.  The per-parameter ``required`` key is then
        removed so the JSON Schema is valid.

        Returns
        -------
        dict
            ``{"type": "function", "function": {...}}`` shape.
        """
        required: list[str] = []
        properties: dict = {}

        for param_name, param_spec in self.parameters.items():
            spec = dict(param_spec)  # shallow copy — don't mutate caller's dict
            if spec.pop("required", False):
                required.append(param_name)
            properties[param_name] = spec

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class AgentEngine(ABC):
    """Protocol that every CogMem engine implementation must satisfy.

    Engines are stateful objects that wrap a model provider.  They receive
    a prompt and tools, stream ``Message`` objects back, and can be stopped
    cleanly.

    All I/O methods are *async generators* so that streaming responses,
    tool-call loops, and background consolidation can all be composed
    naturally with ``async for``.
    """

    @abstractmethod
    async def run(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[Message]:
        """Start a new session and stream response messages.

        Parameters
        ----------
        prompt:
            The initial user message / task.
        system_prompt:
            System-level instructions (from lifecycle.prime()).
        tools:
            Tool definitions to offer the model.

        Yields
        ------
        Message
            Each streamed turn: assistant text, tool calls, tool results, etc.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def resume(self, session_id: str) -> AsyncIterator[Message]:
        """Resume an existing session by ID.

        Parameters
        ----------
        session_id:
            Opaque identifier returned by a previous ``run()`` call.

        Yields
        ------
        Message
            Continuation messages from the resumed session.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def stop(self) -> None:
        """Tear down the engine and release any held resources."""
        ...  # pragma: no cover
