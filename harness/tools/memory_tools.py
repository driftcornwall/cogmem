"""Memory tools — Store, Recall, Ask, Forget, Relate, Goals.

Wraps the CogMem facade as callable tools registered in a module-level
ToolRegistry. Uses lazy singleton injection so the full DB stack is not
required during import or testing.

Usage:
    from harness.tools.memory_tools import registry, set_cogmem
    set_cogmem(my_cogmem_instance)
    result = await registry.dispatch("Store", {"content": "hello"})
"""

import json
from typing import Optional

from harness.tools import ToolRegistry

# ---------------------------------------------------------------------------
# Module-level registry (own instance, not the shared default)
# ---------------------------------------------------------------------------

registry = ToolRegistry()

# ---------------------------------------------------------------------------
# CogMem singleton — lazy, injectable for testing
# ---------------------------------------------------------------------------

_cogmem_instance = None


def _get_cogmem():
    """Return the current CogMem instance, initialising lazily if needed."""
    global _cogmem_instance
    if _cogmem_instance is None:
        from memory import CogMem
        _cogmem_instance = CogMem()
    return _cogmem_instance


def set_cogmem(instance) -> None:
    """Inject a CogMem instance (or mock) for dependency injection / testing."""
    global _cogmem_instance
    _cogmem_instance = instance


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@registry.tool(name="Store", category="memory")
async def store(
    content: str,
    tags: list = None,
    emotional_weight: float = 0.5,
) -> str:
    """Store a memory with optional tags and emotional weight.

    Args:
        content: The text content to store.
        tags: Optional list of tag strings for categorisation.
        emotional_weight: Salience weight in [0.0, 1.0]. Default 0.5.

    Returns:
        JSON string: {"status": "stored", "memory_id": "<id>"}
    """
    cogmem = _get_cogmem()
    memory_id = cogmem.store(content, tags=tags or [], emotional_weight=emotional_weight)
    return json.dumps({"status": "stored", "memory_id": memory_id})


@registry.tool(name="Recall", category="memory")
async def recall(memory_id: str) -> str:
    """Retrieve a specific memory by its ID.

    Args:
        memory_id: Unique memory identifier.

    Returns:
        JSON string: {"memory": <dict>} or {"memory": null, "error": "not found"}
    """
    cogmem = _get_cogmem()
    mem = cogmem.recall(memory_id)
    if mem is None:
        return json.dumps({"memory": None, "error": "not found", "memory_id": memory_id})
    return json.dumps({"memory": mem})


@registry.tool(name="Ask", category="memory")
async def ask(query: str, limit: int = 10) -> str:
    """Semantic search across stored memories.

    Args:
        query: Natural-language query string.
        limit: Maximum number of results to return. Default 10.

    Returns:
        JSON string: {"query": "...", "results": [...], "count": N}
    """
    cogmem = _get_cogmem()
    results = cogmem.ask(query, top_k=limit)
    return json.dumps({
        "query": query,
        "results": results,
        "count": len(results),
    })


@registry.tool(name="Forget", category="memory")
async def forget(memory_id: str) -> str:
    """Soft-archive a memory so it no longer surfaces in search.

    The memory record is preserved in the database but flagged as archived.

    Args:
        memory_id: Unique memory identifier.

    Returns:
        JSON string: {"status": "archived"|"error", "memory_id": "..."}
    """
    try:
        from memory.memory_manager import archive_memory
        archive_memory(memory_id)
        return json.dumps({"status": "archived", "memory_id": memory_id})
    except ImportError:
        # Fallback: attempt direct DB archive
        try:
            from memory.db_adapter import get_db
            db = get_db()
            db.archive_memory(memory_id)
            return json.dumps({"status": "archived", "memory_id": memory_id})
        except Exception as exc:
            return json.dumps({
                "status": "error",
                "memory_id": memory_id,
                "error": str(exc),
            })
    except Exception as exc:
        return json.dumps({
            "status": "error",
            "memory_id": memory_id,
            "error": str(exc),
        })


@registry.tool(name="Relate", category="memory")
async def relate(source_id: str, target_id: str, relationship: str) -> str:
    """Create a directed relationship edge between two memories in the knowledge graph.

    Args:
        source_id: ID of the source memory node.
        target_id: ID of the target memory node.
        relationship: Relationship type string (e.g. "related_to", "causes", "supports").

    Returns:
        JSON string: {"status": "related"|"error", "source_id": ..., "target_id": ..., "relationship": ...}
    """
    try:
        from memory.knowledge_graph import add_edge
        add_edge(source_id, target_id, relationship)
        return json.dumps({
            "status": "related",
            "source_id": source_id,
            "target_id": target_id,
            "relationship": relationship,
        })
    except ImportError:
        # Module not yet available
        return json.dumps({
            "status": "unavailable",
            "source_id": source_id,
            "target_id": target_id,
            "relationship": relationship,
            "error": "knowledge_graph module not available",
        })
    except Exception as exc:
        return json.dumps({
            "status": "error",
            "source_id": source_id,
            "target_id": target_id,
            "relationship": relationship,
            "error": str(exc),
        })


@registry.tool(name="Goals", category="memory")
async def goals(action: str = "list", goal_text: str = None) -> str:
    """Manage agent goals — list active goals or add a new goal.

    Args:
        action: One of "list" (default) or "add".
        goal_text: Goal description, required when action is "add".

    Returns:
        JSON string: {"action": "...", "goals": [...]} or {"action": "add", "status": "..."}
    """
    try:
        import memory.goal_generator as goal_module
        if action == "add" and goal_text:
            try:
                add_fn = getattr(goal_module, "add_goal", None)
                if add_fn:
                    add_fn(goal_text)
                    return json.dumps({"action": "add", "status": "added", "goal_text": goal_text})
                return json.dumps({
                    "action": "add",
                    "status": "unsupported",
                    "error": "add_goal not available in this version",
                })
            except Exception as exc:
                return json.dumps({"action": "add", "status": "error", "error": str(exc)})
        else:
            # list
            try:
                list_fn = getattr(goal_module, "list_goals", None) or getattr(goal_module, "get_goals", None)
                if list_fn:
                    goal_list = list_fn()
                    return json.dumps({"action": "list", "goals": goal_list or []})
                return json.dumps({"action": "list", "goals": [], "note": "list_goals not available"})
            except Exception as exc:
                return json.dumps({"action": "list", "goals": [], "error": str(exc)})
    except ImportError:
        return json.dumps({
            "action": action,
            "goals": [],
            "error": "goal_generator module not available",
        })
    except Exception as exc:
        return json.dumps({"action": action, "goals": [], "error": str(exc)})
