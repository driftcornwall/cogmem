"""AgentLifecycle — prime, consolidate, dream.

Manages the three phases of an agent session:

  prime()       — Build the system prompt for a new session. Loads identity,
                  session info, and stubs for memory/affect/goals priming.
  consolidate() — End-of-session flush: pending memories, co-occurrence, session
                  summary. All operations no-op without a DB connection.
  dream()       — Background maintenance: decay, fingerprint, resonance, merkle.
                  Each phase is individually wrapped in try/except so one failure
                  cannot cascade and crash the others.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class AgentLifecycle:
    """Lifecycle manager for a CogMem agent session.

    Parameters
    ----------
    agent_dir:
        Path to the agent directory containing ``cogmem.yaml`` and
        ``identity.md``.
    db:
        Optional database connection — stub phases are no-ops without it.
        Reserved for Task 13 wiring.
    """

    def __init__(
        self,
        agent_dir: Path | str,
        db: Any = None,
    ) -> None:
        self.agent_dir = Path(agent_dir)
        self.db = db
        self.session_number: int = 0
        self.session_start_time: datetime | None = None

        self._config = self._load_config()
        self._agent_name: str = (
            self._config.get("agent", {}).get("name", self.agent_dir.name)
        )
        self._schema: str = (
            self._config.get("agent", {}).get("schema", self.agent_dir.name)
        )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def agent_name(self) -> str:
        """The agent's display name, from cogmem.yaml ``agent.name``."""
        return self._agent_name

    @property
    def schema(self) -> str:
        """The agent's DB schema name, from cogmem.yaml ``agent.schema``."""
        return self._schema

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prime(self) -> str:
        """Build and return the system prompt for a new session.

        Each call increments :attr:`session_number` and records
        :attr:`session_start_time`.

        Returns
        -------
        str
            A system-prompt string that includes identity, session info, and
            any available cognitive priming (stubs return "" without DB).
        """
        self.session_number += 1
        self.session_start_time = datetime.now(tz=timezone.utc)

        logger.info(
            "Priming session %d for agent %s",
            self.session_number,
            self._agent_name,
        )

        parts: list[str] = []

        # 1. Identity file
        identity = self._load_identity()
        if identity:
            parts.append(identity.strip())

        # 2. Session info line
        parts.append(
            f"Session {self.session_number} | "
            f"Started: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        # 3–5. Stubs — return "" without DB; will be wired in Task 13+
        memory_prime = self._prime_memories()
        if memory_prime:
            parts.append(memory_prime)

        affect_state = self._prime_affect()
        if affect_state:
            parts.append(affect_state)

        goals_prime = self._prime_goals()
        if goals_prime:
            parts.append(goals_prime)

        return "\n\n".join(parts)

    def consolidate(self) -> None:
        """Flush pending session data to long-term storage.

        Calls stubs for:
        - flush_pending_memories
        - flush_cooccurrence
        - write_session_summary

        All operations are no-ops without a DB connection.
        """
        logger.info(
            "Consolidating session %d for agent %s",
            self.session_number,
            self._agent_name,
        )
        self._flush_pending_memories()
        self._flush_cooccurrence()
        self._write_session_summary()
        logger.info("Consolidation complete.")

    def dream(self) -> None:
        """Run background maintenance phases.

        Each phase is individually wrapped in try/except so a failure in one
        phase cannot cascade and crash the others.

        Phases:
        - decay (reduce salience of old memories)
        - fingerprint (update cognitive fingerprint)
        - resonance (detect resonant memory clusters)
        - merkle (extend attestation chain)
        """
        logger.info(
            "Dream phase starting for agent %s (session %d)",
            self._agent_name,
            self.session_number,
        )

        # Decay
        try:
            self._dream_decay()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dream: decay phase failed — %s", exc)

        # Fingerprint
        try:
            self._dream_fingerprint()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dream: fingerprint phase failed — %s", exc)

        # Resonance
        try:
            self._dream_resonance()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dream: resonance phase failed — %s", exc)

        # Merkle
        try:
            self._dream_merkle()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dream: merkle phase failed — %s", exc)

        logger.info("Dream phase complete.")

    # ------------------------------------------------------------------
    # Private: config & identity loaders
    # ------------------------------------------------------------------

    def _load_config(self) -> dict[str, Any]:
        """Load cogmem.yaml from agent_dir; return empty dict on failure."""
        config_path = self.agent_dir / "cogmem.yaml"
        if not config_path.exists():
            logger.debug("No cogmem.yaml found at %s", config_path)
            return {}
        try:
            with open(config_path, encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load cogmem.yaml: %s", exc)
            return {}

    def _load_identity(self) -> str:
        """Load identity.md from agent_dir; return "" if missing."""
        identity_path = self.agent_dir / "identity.md"
        if not identity_path.exists():
            return ""
        try:
            return identity_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load identity.md: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Private: prime stubs
    # ------------------------------------------------------------------

    def _prime_memories(self) -> str:
        """Stub — retrieve primed memories from DB. Returns "" without DB."""
        return ""

    def _prime_affect(self) -> str:
        """Stub — retrieve current affect state from DB. Returns "" without DB."""
        return ""

    def _prime_goals(self) -> str:
        """Stub — retrieve active goals from DB. Returns "" without DB."""
        return ""

    # ------------------------------------------------------------------
    # Private: consolidate stubs
    # ------------------------------------------------------------------

    def _flush_pending_memories(self) -> None:
        """Stub — write pending in-memory stores to DB. No-op without DB."""
        logger.debug("flush_pending_memories: stub (no DB)")

    def _flush_cooccurrence(self) -> None:
        """Stub — flush co-occurrence edge updates to DB. No-op without DB."""
        logger.debug("flush_cooccurrence: stub (no DB)")

    def _write_session_summary(self) -> None:
        """Stub — write structured session summary record. No-op without DB."""
        logger.debug("write_session_summary: stub (no DB)")

    # ------------------------------------------------------------------
    # Private: dream stubs
    # ------------------------------------------------------------------

    def _dream_decay(self) -> None:
        """Stub — apply salience decay to old memories. No-op without DB."""
        logger.debug("dream_decay: stub (no DB)")

    def _dream_fingerprint(self) -> None:
        """Stub — recompute cognitive fingerprint. No-op without DB."""
        logger.debug("dream_fingerprint: stub (no DB)")

    def _dream_resonance(self) -> None:
        """Stub — run resonance scanner over memory graph. No-op without DB."""
        logger.debug("dream_resonance: stub (no DB)")

    def _dream_merkle(self) -> None:
        """Stub — extend merkle attestation chain. No-op without DB."""
        logger.debug("dream_merkle: stub (no DB)")
