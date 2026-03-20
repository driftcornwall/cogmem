"""Tool registry with decorator-based registration for CogMem agents.

Usage:
    registry = ToolRegistry()

    @registry.tool(name="Store", category="memory")
    async def store(content: str, tags: list = None) -> str:
        \"\"\"Store a memory.\"\"\"
        return "stored"

    schema = registry.get_tool_schema("Store")
    result = await registry.dispatch("Store", {"content": "hello"})

Module-level convenience (shared default registry):
    from harness.tools import cogmem_tool, get_registry

    @cogmem_tool(name="MyTool", category="custom")
    async def my_tool(x: str) -> str:
        return x
"""

import inspect
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, get_type_hints


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RegisteredTool:
    """Metadata + handler for a single registered tool."""
    name: str
    category: str
    description: str
    handler: Callable
    parameters: Dict[str, Any]  # JSON-schema-compatible parameter map


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Registry that maps tool names to handlers with schema generation."""

    def __init__(self) -> None:
        self.tools: Dict[str, RegisteredTool] = {}

    # ------------------------------------------------------------------
    # Decorator
    # ------------------------------------------------------------------

    def tool(self, name: str, category: str):
        """Decorator factory — registers an async function as a named tool.

        Args:
            name: Tool name used in schemas and dispatch.
            category: Logical grouping (e.g. "memory", "system", "test").

        Returns:
            Decorator that registers the function and returns it unchanged.
        """
        def decorator(func: Callable) -> Callable:
            description = (inspect.getdoc(func) or "").strip()
            parameters = self._extract_parameters(func)
            self.tools[name] = RegisteredTool(
                name=name,
                category=category,
                description=description,
                handler=func,
                parameters=parameters,
            )
            return func
        return decorator

    # ------------------------------------------------------------------
    # Schema generation
    # ------------------------------------------------------------------

    def get_tool_schema(self, name: str) -> Dict[str, Any]:
        """Return an OpenAI-compatible function-calling schema for *name*.

        Raises:
            KeyError: If the tool is not registered.
        """
        tool = self.tools[name]  # intentional KeyError if missing
        required = [
            param_name
            for param_name, info in tool.parameters.items()
            if info.get("required", False)
        ]
        properties = {
            param_name: {k: v for k, v in info.items() if k != "required"}
            for param_name, info in tool.parameters.items()
        }
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Return OpenAI-compatible schemas for every registered tool."""
        return [self.get_tool_schema(name) for name in self.tools]

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def get_tools_by_category(self, category: str) -> List[RegisteredTool]:
        """Return all tools whose category matches *category* exactly."""
        return [t for t in self.tools.values() if t.category == category]

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, name: str, args: Dict[str, Any]) -> Any:
        """Execute the tool registered under *name* with *args*.

        Args:
            name: Registered tool name.
            args: Keyword arguments passed to the handler.

        Returns:
            Whatever the handler returns.

        Raises:
            KeyError: If no tool with *name* is registered.
        """
        tool = self.tools[name]  # intentional KeyError if missing
        result = tool.handler(**args)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_parameters(self, func: Callable) -> Dict[str, Dict[str, Any]]:
        """Build a parameter map from a function's signature and type hints.

        Each entry has:
            type (str): JSON schema type string.
            description (str): Empty string (no inline docstring extraction).
            required (bool): True when the parameter has no default.

        "self" and return annotation are excluded.
        """
        try:
            hints = get_type_hints(func)
        except Exception:
            hints = getattr(func, "__annotations__", {})

        sig = inspect.signature(func)
        params: Dict[str, Dict[str, Any]] = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            # Skip return annotation
            if param_name == "return":
                continue

            hint = hints.get(param_name)
            json_type = self._python_type_to_json(hint)
            required = param.default is inspect.Parameter.empty

            params[param_name] = {
                "type": json_type,
                "description": "",
                "required": required,
            }

        return params

    @staticmethod
    def _python_type_to_json(hint: Any) -> str:
        """Map a Python type annotation to a JSON schema type string.

        Supported: str -> "string", int -> "integer", float -> "number",
                   bool -> "boolean", list -> "array".
        Unknown or None hints default to "string".
        """
        _MAP = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
        }
        # Handle bare types
        if hint in _MAP:
            return _MAP[hint]
        # Handle Optional[X] / Union[X, None] — extract first arg
        origin = getattr(hint, "__origin__", None)
        if origin is not None:
            args = getattr(hint, "__args__", ())
            for arg in args:
                if arg is not type(None) and arg in _MAP:
                    return _MAP[arg]
            # List[X] or list
            import types
            if origin in (list,):
                return "array"
        return "string"


# ---------------------------------------------------------------------------
# Module-level convenience (shared default registry)
# ---------------------------------------------------------------------------

_default_registry: ToolRegistry = ToolRegistry()


def cogmem_tool(name: str, category: str):
    """Decorator that registers a tool in the module-level default registry."""
    return _default_registry.tool(name=name, category=category)


def get_registry() -> ToolRegistry:
    """Return the module-level default ToolRegistry instance."""
    return _default_registry
