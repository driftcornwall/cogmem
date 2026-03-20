"""Tests for cross-session memory persistence."""
import pytest
from harness.lifecycle import AgentLifecycle


def test_lifecycle_session_counter_increments(tmp_agent_dir):
    """Each prime() call increments the session number."""
    lc = AgentLifecycle(agent_dir=tmp_agent_dir)
    lc.prime()
    assert lc.session_number == 1
    lc.consolidate()
    # New instance — without DB, session resets
    lc2 = AgentLifecycle(agent_dir=tmp_agent_dir)
    lc2.prime()
    assert lc2.session_number == 1  # Documents current behavior without DB


def test_identity_file_survives_sessions(tmp_agent_dir):
    """Identity file persists between lifecycle instances."""
    (tmp_agent_dir / "identity.md").write_text("# Nova\nI remember everything.\n")
    lc1 = AgentLifecycle(agent_dir=tmp_agent_dir)
    prompt1 = lc1.prime()
    assert "Nova" in prompt1
    assert "remember everything" in prompt1
    lc2 = AgentLifecycle(agent_dir=tmp_agent_dir)
    prompt2 = lc2.prime()
    assert "Nova" in prompt2
    assert "remember everything" in prompt2


def test_config_persists_across_instances(tmp_agent_dir):
    """Agent config is consistent across lifecycle instances."""
    lc1 = AgentLifecycle(agent_dir=tmp_agent_dir)
    lc2 = AgentLifecycle(agent_dir=tmp_agent_dir)
    assert lc1.agent_name == lc2.agent_name
    assert lc1.schema == lc2.schema
