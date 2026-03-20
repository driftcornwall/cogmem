"""AgentRegistry — CRUD operations for CogMem agents.

Handles creating, listing, querying, and deleting agent directories with
their default config (cogmem.yaml), identity file, and logs directory.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Default templates
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_TEMPLATE: dict[str, Any] = {
    "agent": {
        "name": "{name}",
        "schema": "{schema}",
    },
    "database": {
        "host": "localhost",
        "port": 5433,
        "name": "agent_memory",
        "user": "agent_admin",
        "password": "agent_memory_local_dev",
    },
    "model": {
        "provider": "claude-api",
        "model": "claude-sonnet-4-6",
    },
    "personality": {
        "temperament": {
            "valence_baseline": 0.0,
            "arousal_reactivity": 0.5,
        },
        "terminal_goals": ["knowledge", "autonomy", "emergence"],
    },
    "modules": {
        "affect": True,
        "workspace": True,
        "inner_monologue": False,
        "counterfactual": False,
        "cognitive_oscillators": False,
        "knowledge_graph": True,
    },
    "entities": {
        "known_agents": [],
        "known_projects": [],
    },
}

_DEFAULT_IDENTITY_TEMPLATE = (
    "# {name}\n\n"
    "I am {name}, a cognitive agent powered by CogMem.\n\n"
    "My memory develops over time. My identity emerges from what I attend to, "
    "what I remember, and what I choose.\n"
)


# ---------------------------------------------------------------------------
# AgentRegistry
# ---------------------------------------------------------------------------


class AgentRegistry:
    """Registry for creating and managing CogMem agent directories.

    Parameters
    ----------
    agents_dir:
        Root directory where agent sub-directories are stored.
        Defaults to ``~/.cogmem/agents/``.
    db:
        Optional database connection — reserved for Task 13 (DB schema
        creation). Unused for now.
    """

    def __init__(
        self,
        agents_dir: Path | str | None = None,
        db: Any = None,
    ) -> None:
        if agents_dir is None:
            agents_dir = Path.home() / ".cogmem" / "agents"
        self.agents_dir = Path(agents_dir)
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_agent(self, name: str, path: Path | str | None = None) -> Path:
        """Create a new agent directory with default config and identity files.

        Parameters
        ----------
        name:
            Display name of the agent (e.g. ``"Nova"``).
        path:
            Explicit directory path for the agent. If omitted, the agent
            is placed at ``agents_dir/<name.lower()>/``.

        Returns
        -------
        Path
            The created agent directory.

        Raises
        ------
        ValueError
            If an agent with the same name already exists under ``agents_dir``.
        """
        schema = _to_schema_name(name)

        if path is None:
            agent_dir = self.agents_dir / schema
        else:
            agent_dir = Path(path)

        # Duplicate check — only enforce when using the default path layout
        if agent_dir == self.agents_dir / schema and agent_dir.exists():
            raise ValueError(
                f"Agent '{name}' already exists at {agent_dir}"
            )

        # Build directory structure
        agent_dir.mkdir(parents=True, exist_ok=False)
        (agent_dir / "logs").mkdir()

        # Write cogmem.yaml
        config = _render_config(name, schema)
        with open(agent_dir / "cogmem.yaml", "w", encoding="utf-8") as fh:
            yaml.dump(config, fh, default_flow_style=False, allow_unicode=True)

        # Write identity.md
        identity = _DEFAULT_IDENTITY_TEMPLATE.format(name=name)
        (agent_dir / "identity.md").write_text(identity, encoding="utf-8")

        # Stub: create DB schema (wired in Task 13)
        self._create_db_schema(schema)

        return agent_dir

    def list_agents(self) -> list[dict[str, Any]]:
        """Return info dicts for every agent found under ``agents_dir``.

        Scans all immediate subdirectories that contain a ``cogmem.yaml``.
        """
        if not self.agents_dir.exists():
            return []

        agents: list[dict[str, Any]] = []
        for candidate in sorted(self.agents_dir.iterdir()):
            if not candidate.is_dir():
                continue
            config_path = candidate / "cogmem.yaml"
            if not config_path.exists():
                continue
            info = self._read_agent_info(candidate)
            if info is not None:
                agents.append(info)
        return agents

    def get_agent_info(self, name: str) -> dict[str, Any]:
        """Return the info dict for a named agent.

        Tries the default path first, then falls back to scanning configs.

        Raises
        ------
        ValueError
            If no agent with ``name`` is found.
        """
        agent_dir = self._find_agent_dir(name)
        info = self._read_agent_info(agent_dir)
        if info is None:
            raise ValueError(f"Agent '{name}' not found")
        return info

    def delete_agent(self, name: str) -> None:
        """Remove the agent directory entirely.

        Raises
        ------
        ValueError
            If no agent with ``name`` is found.
        """
        agent_dir = self._find_agent_dir(name)
        shutil.rmtree(agent_dir)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_agent_dir(self, name: str) -> Path:
        """Locate the directory for *name*, raising ValueError if not found."""
        schema = _to_schema_name(name)

        # Fast path: default location
        default = self.agents_dir / schema
        if default.exists() and (default / "cogmem.yaml").exists():
            config = _load_yaml(default / "cogmem.yaml")
            if config.get("agent", {}).get("name") == name:
                return default

        # Slow path: scan all subdirectories
        if self.agents_dir.exists():
            for candidate in self.agents_dir.iterdir():
                if not candidate.is_dir():
                    continue
                config_path = candidate / "cogmem.yaml"
                if not config_path.exists():
                    continue
                config = _load_yaml(config_path)
                if config.get("agent", {}).get("name") == name:
                    return candidate

        raise ValueError(f"Agent '{name}' not found")

    def _read_agent_info(self, agent_dir: Path) -> dict[str, Any] | None:
        """Read config from an agent directory and return a normalised dict."""
        config_path = agent_dir / "cogmem.yaml"
        if not config_path.exists():
            return None
        config = _load_yaml(config_path)
        agent_section = config.get("agent", {})
        model_section = config.get("model", {})
        return {
            "name": agent_section.get("name", agent_dir.name),
            "schema": agent_section.get("schema", agent_dir.name),
            "path": str(agent_dir),
            "model": model_section.get("model"),
            "provider": model_section.get("provider"),
        }

    def _create_db_schema(self, schema_name: str) -> None:
        """Create the PostgreSQL schema for the agent and apply the initial migration.

        Steps
        -----
        1. CREATE SCHEMA IF NOT EXISTS <schema_name>
        2. Read and execute database/migrations/001_initial.sql within that schema
        3. Register the agent in cogmem_registry.agents
        4. Record the applied migration in cogmem_registry.schema_versions

        Wrapped in try/except so filesystem-only creation still works when the
        database is unavailable.
        """
        if self.db is None:
            return

        try:
            # Resolve migration file relative to this source file's package root
            _here = Path(__file__).parent  # harness/
            _root = _here.parent           # cogmem/
            migration_path = _root / "database" / "migrations" / "001_initial.sql"
            migration_sql = migration_path.read_text(encoding="utf-8")
            migration_id = "001_initial"

            cur = self.db.cursor()

            # 1. Create the agent's schema
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

            # 2. Execute migration within the agent's schema
            cur.execute(f"SET search_path TO {schema_name}, public")
            cur.execute(migration_sql)

            # 3. Register in cogmem_registry.agents (path may not be known yet; use schema)
            cur.execute("""
                INSERT INTO cogmem_registry.agents (name, schema_name, path)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE
                    SET schema_name = EXCLUDED.schema_name,
                        last_active  = NOW()
            """, (schema_name, schema_name, str(self.agents_dir / schema_name)))

            # 4. Record migration
            cur.execute("""
                INSERT INTO cogmem_registry.schema_versions (schema_name, migration_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (schema_name, migration_id))

            # Reset search_path to default
            cur.execute("SET search_path TO public")

            self.db.commit()
            cur.close()

        except Exception:
            # DB unavailable or any other error — filesystem creation already done
            try:
                self.db.rollback()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _to_schema_name(name: str) -> str:
    """Convert a display name to a lowercase, underscore-separated schema name."""
    return name.lower().replace(" ", "_")


def _render_config(name: str, schema: str) -> dict[str, Any]:
    """Return a fully-rendered config dict for *name* / *schema*."""
    import copy
    config = copy.deepcopy(_DEFAULT_CONFIG_TEMPLATE)
    config["agent"]["name"] = name
    config["agent"]["schema"] = schema
    return config


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning an empty dict on any error."""
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}
