"""Tests for engine abstraction and Claude engine."""
import pytest
from harness.engine import AgentEngine, Message, ToolDefinition


def test_engine_is_abstract():
    with pytest.raises(TypeError):
        AgentEngine()


def test_message_dataclass():
    msg = Message(role="assistant", content="hello")
    assert msg.role == "assistant"
    assert msg.content == "hello"
    assert msg.tool_calls is None


def test_tool_definition_to_schema():
    td = ToolDefinition(
        name="Store",
        description="Store a memory",
        parameters={"content": {"type": "string", "required": True}},
    )
    schema = td.to_schema()
    assert schema["function"]["name"] == "Store"
    assert schema["function"]["parameters"]["required"] == ["content"]


def test_claude_engine_init():
    from harness.claude_engine import ClaudeEngine
    config = {"model": {"provider": "claude-api", "model": "claude-sonnet-4-6"}}
    engine = ClaudeEngine(config)
    assert engine.model == "claude-sonnet-4-6"
    assert engine.provider == "claude-api"
