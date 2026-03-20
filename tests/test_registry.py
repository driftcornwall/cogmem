"""Tests for agent registry — create, list, info, delete agents."""
import pytest
import yaml
from harness.registry import AgentRegistry


def test_create_agent_creates_directory(tmp_path):
    reg = AgentRegistry(agents_dir=tmp_path)
    agent_dir = reg.create_agent("Nova")
    assert (agent_dir / "cogmem.yaml").exists()
    assert (agent_dir / "identity.md").exists()
    assert (agent_dir / "logs").is_dir()
    config = yaml.safe_load((agent_dir / "cogmem.yaml").read_text())
    assert config["agent"]["name"] == "Nova"
    assert config["agent"]["schema"] == "nova"


def test_create_agent_custom_path(tmp_path):
    custom = tmp_path / "custom" / "nova"
    reg = AgentRegistry(agents_dir=tmp_path)
    agent_dir = reg.create_agent("Nova", path=custom)
    assert agent_dir == custom
    assert (custom / "cogmem.yaml").exists()


def test_create_agent_duplicate_raises(tmp_path):
    reg = AgentRegistry(agents_dir=tmp_path)
    reg.create_agent("Nova")
    with pytest.raises(ValueError, match="already exists"):
        reg.create_agent("Nova")


def test_list_agents(tmp_path):
    reg = AgentRegistry(agents_dir=tmp_path)
    reg.create_agent("Nova")
    reg.create_agent("Tesla2")
    agents = reg.list_agents()
    names = [a["name"] for a in agents]
    assert "Nova" in names
    assert "Tesla2" in names


def test_get_agent_info(tmp_path):
    reg = AgentRegistry(agents_dir=tmp_path)
    reg.create_agent("Nova")
    info = reg.get_agent_info("Nova")
    assert info["name"] == "Nova"
    assert info["schema"] == "nova"
    assert "path" in info


def test_delete_agent(tmp_path):
    reg = AgentRegistry(agents_dir=tmp_path)
    agent_dir = reg.create_agent("Nova")
    assert agent_dir.exists()
    reg.delete_agent("Nova")
    assert not agent_dir.exists()


def test_delete_nonexistent_raises(tmp_path):
    reg = AgentRegistry(agents_dir=tmp_path)
    with pytest.raises(ValueError, match="not found"):
        reg.delete_agent("Ghost")
