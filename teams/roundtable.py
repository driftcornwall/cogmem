"""Roundtable team architecture.

Every agent speaks once per round, in registration order.  The full
conversation history is accumulated across rounds so later agents can
read earlier contributions before responding.

Current implementation yields placeholder responses.  A future task will
wire each agent to its own AgentEngine instance.
"""

from __future__ import annotations

from typing import AsyncIterator

from teams.base import TeamArchitecture, TeamMessage


class RoundtableArchitecture(TeamArchitecture):
    """A structured discussion where each agent takes a turn per round.

    Setup
    -----
    Call :meth:`setup` with at least two agent configs and a ``config`` dict
    that includes a ``"rounds"`` key.

    Run
    ---
    ``async for msg in rt.run(prompt)`` yields one :class:`~teams.base.TeamMessage`
    per (agent, round) pair.  The full conversation history up to that point
    is available in ``msg.metadata["history"]``.

    Teardown
    --------
    :meth:`teardown` is a stub for future cross-agent memory consolidation.
    """

    def __init__(self) -> None:
        self.agent_configs: list[dict] = []
        self.rounds: int = 1
        self._config: dict = {}

    # ------------------------------------------------------------------
    # TeamArchitecture implementation
    # ------------------------------------------------------------------

    def setup(self, agents: list[dict], config: dict) -> None:
        """Validate and store team configuration.

        Parameters
        ----------
        agents:
            At least two agent config dicts.  Each must contain ``"name"``.
        config:
            Must contain ``"rounds"`` (int >= 1).

        Raises
        ------
        ValueError
            If fewer than 2 agents are provided.
        """
        if len(agents) < 2:
            raise ValueError(
                "RoundtableArchitecture requires at least 2 agents; "
                f"got {len(agents)}."
            )
        self.agent_configs = list(agents)
        self._config = dict(config)
        self.rounds = int(config.get("rounds", 1))

    async def run(self, prompt: str) -> AsyncIterator[TeamMessage]:
        """Run the roundtable discussion and yield each agent's contribution.

        For each round, each agent produces a :class:`~teams.base.TeamMessage`.
        The accumulated ``conversation_history`` list is attached to every
        message's ``metadata`` so callers can inspect the full context.

        Parameters
        ----------
        prompt:
            Topic or task presented to all agents.

        Yields
        ------
        TeamMessage
            One message per (round, agent) pair.
        """
        conversation_history: list[dict] = []

        for round_num in range(self.rounds):
            for agent_cfg in self.agent_configs:
                agent_name = agent_cfg["name"]

                # TODO: wire to AgentEngine — replace placeholder with real call
                content = (
                    f"[Round {round_num + 1}] {agent_name} responds to: {prompt}"
                )

                msg = TeamMessage(
                    agent=agent_name,
                    content=content,
                    round_num=round_num,
                    metadata={
                        "history": list(conversation_history),
                        "agent_path": agent_cfg.get("path", ""),
                    },
                )

                conversation_history.append(
                    {"agent": agent_name, "round": round_num, "content": content}
                )

                yield msg

    async def teardown(self) -> None:
        """Stub for cross-agent memory consolidation (not yet implemented)."""
        # TODO: consolidate shared memories across agents after the session
        pass
