"""ClaudeEngine — AgentEngine implementation backed by the Claude Agent SDK.

The module can be imported safely even when ``claude_agent_sdk`` is not
installed.  Attempting to actually *run* the engine without the SDK will
raise an ``ImportError`` with a helpful install message.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncIterator

from harness.engine import AgentEngine, Message, ToolDefinition

if TYPE_CHECKING:
    pass  # keep type-checker happy; no runtime imports of optional deps here

logger = logging.getLogger(__name__)

_SDK_INSTALL_HINT = (
    "The Claude Agent SDK is required to use ClaudeEngine.\n"
    "Install it with:  pip install claude-agent-sdk\n"
    "See: https://github.com/anthropics/claude-agent-sdk"
)


class ClaudeEngine(AgentEngine):
    """AgentEngine implementation for Anthropic's Claude via the Agent SDK.

    Parameters
    ----------
    config:
        Full ``cogmem.yaml``-style config dict.  The ``model`` sub-dict is
        read for ``provider`` and ``model`` keys.

    Attributes
    ----------
    provider:
        The provider string from config (e.g. "claude-api").
    model:
        The model identifier (e.g. "claude-sonnet-4-6").
    """

    def __init__(self, config: dict) -> None:
        model_cfg = config.get("model", {})
        self.provider: str = model_cfg.get("provider", "claude-api")
        self.model: str = model_cfg.get("model", "claude-sonnet-4-6")
        self._client = None  # lazily initialised on first run()
        logger.debug(
            "ClaudeEngine initialised: provider=%s model=%s",
            self.provider,
            self.model,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_sdk(self):
        """Import and return the claude_agent_sdk module.

        Raises
        ------
        ImportError
            With a helpful install hint if the SDK is not installed.
        """
        try:
            import claude_agent_sdk  # type: ignore[import]
            return claude_agent_sdk
        except ImportError as exc:
            raise ImportError(_SDK_INSTALL_HINT) from exc

    def _build_tool_schemas(
        self, tools: list[ToolDefinition] | None
    ) -> list[dict]:
        """Convert ToolDefinition list to OpenAI-compatible schema list."""
        if not tools:
            return []
        return [td.to_schema() for td in tools]

    # ------------------------------------------------------------------
    # AgentEngine interface
    # ------------------------------------------------------------------

    async def run(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[Message]:
        """Start a new Claude Agent SDK session and stream Messages.

        Parameters
        ----------
        prompt:
            Initial user prompt / task description.
        system_prompt:
            System instructions (from AgentLifecycle.prime()).
        tools:
            Tool definitions to offer the model.

        Yields
        ------
        Message
            Each response turn from the agent.

        Raises
        ------
        ImportError
            If ``claude_agent_sdk`` is not installed.
        """
        sdk = self._get_sdk()
        tool_schemas = self._build_tool_schemas(tools)

        options: dict = {"model": self.model}
        if system_prompt:
            options["system_prompt"] = system_prompt
        if tool_schemas:
            options["tools"] = tool_schemas

        # Optionally wire in the MCP memory server when the SDK supports it
        try:
            from harness.tools.mcp_server import (
                create_memory_mcp_server,
                get_memory_tool_names,
            )
            mcp_server = create_memory_mcp_server()
            options.setdefault("mcp_servers", [])
            options["mcp_servers"].append(mcp_server)
            # Merge memory tool names into allowed_tools when present
            existing_allowed = options.get("allowed_tools", [])
            options["allowed_tools"] = existing_allowed + get_memory_tool_names()
            logger.debug(
                "ClaudeEngine.run(): MCP memory server attached, tools=%s",
                get_memory_tool_names(),
            )
        except ImportError as mcp_exc:
            logger.debug(
                "ClaudeEngine.run(): MCP memory server not available (%s), continuing without it",
                mcp_exc,
            )

        logger.info(
            "ClaudeEngine.run(): model=%s tools=%d",
            self.model,
            len(tool_schemas),
        )

        try:
            async for event in sdk.query(prompt=prompt, options=options):
                yield self._event_to_message(event)
        except Exception as exc:
            logger.error("ClaudeEngine.run() error: %s", exc)
            raise

    async def resume(self, session_id: str) -> AsyncIterator[Message]:
        """Resume an existing Claude Agent SDK session.

        Parameters
        ----------
        session_id:
            Opaque session identifier returned by a previous ``run()`` call.

        Yields
        ------
        Message
            Continuation messages.

        Raises
        ------
        ImportError
            If ``claude_agent_sdk`` is not installed.
        """
        sdk = self._get_sdk()

        options: dict = {"model": self.model, "resume": session_id}

        logger.info(
            "ClaudeEngine.resume(): model=%s session_id=%s",
            self.model,
            session_id,
        )

        try:
            async for event in sdk.query(prompt="", options=options):
                yield self._event_to_message(event)
        except Exception as exc:
            logger.error("ClaudeEngine.resume() error: %s", exc)
            raise

    async def stop(self) -> None:
        """Release any held SDK resources."""
        logger.debug("ClaudeEngine.stop(): releasing client")
        self._client = None

    # ------------------------------------------------------------------
    # Private: event conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _event_to_message(event) -> Message:
        """Convert a claude_agent_sdk event object to a ``Message``.

        The SDK may return plain dicts, dataclasses, or objects — we handle
        all three defensively.
        """
        if isinstance(event, dict):
            return Message(
                role=event.get("role", "assistant"),
                content=event.get("content", ""),
                tool_calls=event.get("tool_calls"),
                tool_call_id=event.get("tool_call_id"),
            )

        # Object with attributes
        return Message(
            role=getattr(event, "role", "assistant"),
            content=getattr(event, "content", ""),
            tool_calls=getattr(event, "tool_calls", None),
            tool_call_id=getattr(event, "tool_call_id", None),
        )
