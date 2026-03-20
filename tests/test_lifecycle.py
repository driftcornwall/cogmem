"""Tests for agent lifecycle — prime, consolidate, dream."""
import pytest
from harness.lifecycle import AgentLifecycle


def test_prime_returns_system_prompt(tmp_agent_dir):
    lc = AgentLifecycle(agent_dir=tmp_agent_dir)
    prompt = lc.prime()
    assert isinstance(prompt, str)
    assert "TestAgent" in prompt
    assert len(prompt) > 0


def test_prime_loads_identity(tmp_agent_dir):
    (tmp_agent_dir / "identity.md").write_text("# Nova\nI am Nova, a test agent.\n")
    lc = AgentLifecycle(agent_dir=tmp_agent_dir)
    prompt = lc.prime()
    assert "Nova" in prompt


def test_prime_tracks_session_number(tmp_agent_dir):
    lc = AgentLifecycle(agent_dir=tmp_agent_dir)
    lc.prime()
    assert lc.session_number == 1
    lc.prime()
    assert lc.session_number == 2


def test_consolidate_without_errors(tmp_agent_dir):
    lc = AgentLifecycle(agent_dir=tmp_agent_dir)
    lc.prime()
    lc.consolidate()  # Should not raise


def test_dream_without_errors(tmp_agent_dir):
    lc = AgentLifecycle(agent_dir=tmp_agent_dir)
    lc.prime()
    lc.dream()  # Should not raise


def test_lifecycle_flow(tmp_agent_dir):
    lc = AgentLifecycle(agent_dir=tmp_agent_dir)
    prompt = lc.prime()
    assert isinstance(prompt, str)
    lc.consolidate()
    lc.dream()
