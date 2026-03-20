"""Tests for the tool registry decorator and registration system."""
import pytest
import asyncio
from harness.tools import ToolRegistry


def test_tool_registration():
    registry = ToolRegistry()
    @registry.tool(name="TestTool", category="test")
    async def test_tool(arg1: str, arg2: int = 5) -> str:
        """A test tool."""
        return f"{arg1}-{arg2}"
    assert "TestTool" in registry.tools
    assert registry.tools["TestTool"].category == "test"
    assert registry.tools["TestTool"].handler is test_tool


def test_tool_schema_generation():
    registry = ToolRegistry()
    @registry.tool(name="Store", category="memory")
    async def store(content: str, tags: list = None, emotional_weight: float = 0.5) -> str:
        """Store a memory with optional tags and emotional weight."""
        return "stored"
    schema = registry.get_tool_schema("Store")
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "Store"
    assert "content" in schema["function"]["parameters"]["properties"]
    assert schema["function"]["parameters"]["required"] == ["content"]


def test_tool_list_by_category():
    registry = ToolRegistry()
    @registry.tool(name="Store", category="memory")
    async def store(content: str) -> str:
        return "stored"
    @registry.tool(name="Bash", category="system")
    async def bash(command: str) -> str:
        return "ran"
    memory_tools = registry.get_tools_by_category("memory")
    assert len(memory_tools) == 1
    assert memory_tools[0].name == "Store"


def test_tool_dispatch():
    registry = ToolRegistry()
    @registry.tool(name="Echo", category="test")
    async def echo(message: str) -> str:
        """Echo the message back."""
        return message
    result = asyncio.run(registry.dispatch("Echo", {"message": "hello"}))
    assert result == "hello"


def test_unknown_tool_raises():
    registry = ToolRegistry()
    with pytest.raises(KeyError):
        asyncio.run(registry.dispatch("NonExistent", {}))
