"""Tests for memory tools — Store, Recall, Ask, Forget, Relate, Goals."""
import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch

from harness.tools.memory_tools import registry


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

def test_store_tool_registered():
    """Store is in registry with category 'memory'."""
    assert "Store" in registry.tools
    assert registry.tools["Store"].category == "memory"


def test_ask_tool_registered():
    """Ask is in registry with category 'memory'."""
    assert "Ask" in registry.tools
    assert registry.tools["Ask"].category == "memory"


def test_recall_tool_registered():
    """Recall is in registry with category 'memory'."""
    assert "Recall" in registry.tools
    assert registry.tools["Recall"].category == "memory"


def test_forget_tool_registered():
    """Forget is in registry with category 'memory'."""
    assert "Forget" in registry.tools
    assert registry.tools["Forget"].category == "memory"


def test_relate_tool_registered():
    """Relate is in registry with category 'memory'."""
    assert "Relate" in registry.tools
    assert registry.tools["Relate"].category == "memory"


def test_goals_tool_registered():
    """Goals is in registry with category 'memory'."""
    assert "Goals" in registry.tools
    assert registry.tools["Goals"].category == "memory"


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_all_memory_tools_have_schemas():
    """All 6 tools generate valid OpenAI-compatible schemas."""
    tool_names = ["Store", "Recall", "Ask", "Forget", "Relate", "Goals"]
    for name in tool_names:
        schema = registry.get_tool_schema(name)
        assert schema["type"] == "function", f"{name}: missing 'type'"
        func = schema["function"]
        assert "name" in func, f"{name}: missing function.name"
        assert "description" in func, f"{name}: missing function.description"
        assert "parameters" in func, f"{name}: missing function.parameters"
        params = func["parameters"]
        assert params["type"] == "object", f"{name}: parameters.type != object"
        assert "properties" in params, f"{name}: missing properties"
        assert "required" in params, f"{name}: missing required"


def test_store_schema_has_required_content():
    """Store schema marks 'content' as required."""
    schema = registry.get_tool_schema("Store")
    required = schema["function"]["parameters"]["required"]
    assert "content" in required
    # tags and emotional_weight have defaults, so not required
    assert "tags" not in required
    assert "emotional_weight" not in required


def test_ask_schema_has_required_query():
    """Ask schema marks 'query' as required; limit is optional."""
    schema = registry.get_tool_schema("Ask")
    required = schema["function"]["parameters"]["required"]
    assert "query" in required
    assert "limit" not in required


def test_recall_schema_has_required_memory_id():
    """Recall schema marks 'memory_id' as required."""
    schema = registry.get_tool_schema("Recall")
    required = schema["function"]["parameters"]["required"]
    assert "memory_id" in required


# ---------------------------------------------------------------------------
# Dispatch / delegation tests
# ---------------------------------------------------------------------------

def test_store_calls_cogmem_store():
    """Store tool dispatches to cogmem.store() with correct arguments."""
    mock_cogmem = MagicMock()
    mock_cogmem.store.return_value = "mem-abc123"

    with patch("harness.tools.memory_tools._get_cogmem", return_value=mock_cogmem):
        result_json = asyncio.run(
            registry.dispatch("Store", {"content": "test memory", "tags": ["test"]})
        )

    result = json.loads(result_json)
    mock_cogmem.store.assert_called_once_with(
        "test memory", tags=["test"], emotional_weight=0.5
    )
    assert result["memory_id"] == "mem-abc123"
    assert result["status"] == "stored"


def test_ask_calls_cogmem_ask():
    """Ask tool dispatches to cogmem.ask() with correct arguments."""
    mock_cogmem = MagicMock()
    mock_cogmem.ask.return_value = [
        {"id": "m1", "content": "relevant memory", "score": 0.9}
    ]

    with patch("harness.tools.memory_tools._get_cogmem", return_value=mock_cogmem):
        result_json = asyncio.run(
            registry.dispatch("Ask", {"query": "what do I know about testing?"})
        )

    result = json.loads(result_json)
    mock_cogmem.ask.assert_called_once_with(
        "what do I know about testing?", top_k=10
    )
    assert result["query"] == "what do I know about testing?"
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == "m1"


def test_recall_calls_cogmem_recall():
    """Recall tool dispatches to cogmem.recall() with correct memory_id."""
    mock_cogmem = MagicMock()
    mock_cogmem.recall.return_value = {
        "id": "mem-xyz", "content": "recalled memory"
    }

    with patch("harness.tools.memory_tools._get_cogmem", return_value=mock_cogmem):
        result_json = asyncio.run(
            registry.dispatch("Recall", {"memory_id": "mem-xyz"})
        )

    result = json.loads(result_json)
    mock_cogmem.recall.assert_called_once_with("mem-xyz")
    assert result["memory"]["id"] == "mem-xyz"


def test_store_returns_json_string():
    """Store tool always returns a JSON string."""
    mock_cogmem = MagicMock()
    mock_cogmem.store.return_value = "mem-001"

    with patch("harness.tools.memory_tools._get_cogmem", return_value=mock_cogmem):
        result = asyncio.run(
            registry.dispatch("Store", {"content": "hello"})
        )

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert isinstance(parsed, dict)


def test_ask_returns_json_string():
    """Ask tool always returns a JSON string."""
    mock_cogmem = MagicMock()
    mock_cogmem.ask.return_value = []

    with patch("harness.tools.memory_tools._get_cogmem", return_value=mock_cogmem):
        result = asyncio.run(
            registry.dispatch("Ask", {"query": "anything"})
        )

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert "results" in parsed


def test_forget_returns_json_string():
    """Forget tool returns a JSON string (graceful even without DB)."""
    result = asyncio.run(
        registry.dispatch("Forget", {"memory_id": "mem-999"})
    )
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert "memory_id" in parsed


def test_relate_returns_json_string():
    """Relate tool returns a JSON string (graceful even without DB)."""
    result = asyncio.run(
        registry.dispatch("Relate", {
            "source_id": "m1",
            "target_id": "m2",
            "relationship": "related_to",
        })
    )
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert "source_id" in parsed
    assert "target_id" in parsed


def test_goals_returns_json_string():
    """Goals tool returns a JSON string (graceful even without DB)."""
    result = asyncio.run(
        registry.dispatch("Goals", {"action": "list"})
    )
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert "action" in parsed


def test_store_with_default_tags():
    """Store tool handles None tags gracefully (uses empty list)."""
    mock_cogmem = MagicMock()
    mock_cogmem.store.return_value = "mem-defaults"

    with patch("harness.tools.memory_tools._get_cogmem", return_value=mock_cogmem):
        result_json = asyncio.run(
            registry.dispatch("Store", {"content": "no tags here"})
        )

    result = json.loads(result_json)
    mock_cogmem.store.assert_called_once_with(
        "no tags here", tags=[], emotional_weight=0.5
    )
    assert result["status"] == "stored"
