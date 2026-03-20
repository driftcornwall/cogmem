"""Shared test fixtures for cogmem harness tests."""
import os
import pytest
import yaml

@pytest.fixture
def tmp_agent_dir(tmp_path):
    """Create a temporary agent directory with minimal config."""
    agent_dir = tmp_path / "test_agent"
    agent_dir.mkdir()
    config = {
        "agent": {"name": "TestAgent", "schema": "test_agent"},
        "database": {
            "host": os.environ.get("COGMEM_TEST_DB_HOST", "localhost"),
            "port": int(os.environ.get("COGMEM_TEST_DB_PORT", "5433")),
            "name": os.environ.get("COGMEM_TEST_DB_NAME", "agent_memory"),
            "user": os.environ.get("COGMEM_TEST_DB_USER", "agent_admin"),
            "password": os.environ.get("COGMEM_TEST_DB_PASS", "agent_memory_local_dev"),
        },
        "model": {"provider": "claude-api", "model": "claude-sonnet-4-6"},
        "personality": {
            "temperament": {"valence_baseline": 0.0, "arousal_reactivity": 0.5},
            "terminal_goals": ["knowledge"],
        },
        "modules": {
            "affect": True, "workspace": True, "inner_monologue": False,
            "counterfactual": False, "cognitive_oscillators": False, "knowledge_graph": True,
        },
        "entities": {"known_agents": [], "known_projects": []},
    }
    with open(agent_dir / "cogmem.yaml", "w") as f:
        yaml.dump(config, f)
    (agent_dir / "identity.md").write_text("# TestAgent\n\nA test agent for CogMem harness tests.\n")
    (agent_dir / "logs").mkdir()
    return agent_dir

@pytest.fixture
def sample_config(tmp_agent_dir):
    """Load the sample config from the temp agent dir."""
    with open(tmp_agent_dir / "cogmem.yaml") as f:
        return yaml.safe_load(f)
