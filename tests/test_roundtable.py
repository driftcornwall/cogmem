"""Tests for roundtable team architecture."""
import pytest
import asyncio
from teams.base import TeamMessage
from teams.roundtable import RoundtableArchitecture


def test_team_message_dataclass():
    msg = TeamMessage(agent="Nova", content="Hello", round_num=1)
    assert msg.agent == "Nova"
    assert msg.round_num == 1


def test_roundtable_setup():
    rt = RoundtableArchitecture()
    agents = [
        {"name": "Nova", "path": "/tmp/nova"},
        {"name": "Tesla2", "path": "/tmp/tesla2"},
    ]
    rt.setup(agents=agents, config={"rounds": 2})
    assert rt.rounds == 2
    assert len(rt.agent_configs) == 2


def test_roundtable_validates_minimum_agents():
    rt = RoundtableArchitecture()
    with pytest.raises(ValueError, match="at least 2"):
        rt.setup(agents=[{"name": "Solo"}], config={"rounds": 1})


def test_roundtable_run_yields_messages():
    rt = RoundtableArchitecture()
    agents = [{"name": "Nova", "path": "/tmp/nova"}, {"name": "Tesla2", "path": "/tmp/tesla2"}]
    rt.setup(agents=agents, config={"rounds": 2})
    messages = asyncio.run(_collect_messages(rt, "Test topic"))
    # 2 agents * 2 rounds = 4 messages
    assert len(messages) == 4
    assert all(isinstance(m, TeamMessage) for m in messages)
    agent_names = [m.agent for m in messages]
    assert "Nova" in agent_names
    assert "Tesla2" in agent_names


async def _collect_messages(rt, prompt):
    msgs = []
    async for msg in rt.run(prompt):
        msgs.append(msg)
    return msgs
