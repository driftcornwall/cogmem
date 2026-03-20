"""Base classes for CogMem multi-agent team orchestration.

Defines the shared protocol that every team architecture must implement,
along with the TeamMessage dataclass used to carry inter-agent communication.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TeamMessage:
    """A single message produced during a team session.

    Parameters
    ----------
    agent:
        Name of the agent that produced this message.
    content:
        Text content of the message.
    round_num:
        Which discussion round this message belongs to (0-indexed by default).
    metadata:
        Arbitrary extra data (timestamps, token counts, source path, etc.).
    """

    agent: str
    content: str
    round_num: int = 0
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class TeamArchitecture(ABC):
    """Protocol that every CogMem team architecture must satisfy.

    Team architectures coordinate multiple agents around a shared prompt.
    They are stateful objects that configure agent participants, run
    discussion rounds, and optionally consolidate shared outcomes.
    """

    @abstractmethod
    def setup(self, agents: list[dict], config: dict) -> None:
        """Configure the team with participants and runtime options.

        Parameters
        ----------
        agents:
            List of agent configuration dicts.  Each dict should at minimum
            contain a ``"name"`` key; implementations may require additional
            keys (e.g. ``"path"``).
        config:
            Architecture-specific options (e.g. number of rounds, topic
            framing, memory scope).
        """
        ...  # pragma: no cover

    @abstractmethod
    async def run(self, prompt: str) -> AsyncIterator[TeamMessage]:
        """Execute the team discussion and stream messages.

        Parameters
        ----------
        prompt:
            The topic or task presented to the team.

        Yields
        ------
        TeamMessage
            Each contribution from each agent, in order.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def teardown(self) -> None:
        """Release resources and optionally consolidate shared memory."""
        ...  # pragma: no cover
