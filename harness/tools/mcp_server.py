"""MCP server exposing CogMem memory tools to the Claude Agent SDK.

Creates an in-process MCP server so memory tools appear as native
tools alongside Read, Edit, Bash in the Agent SDK.
"""
import json
import logging

logger = logging.getLogger(__name__)


def create_memory_mcp_server():
    """Create an in-process MCP server with all memory tools.

    Returns a dict suitable for ClaudeAgentOptions.mcp_servers.
    Requires claude-agent-sdk to be installed.
    """
    try:
        from claude_agent_sdk import tool as sdk_tool, create_sdk_mcp_server
    except ImportError:
        raise ImportError(
            "claude-agent-sdk is required to create MCP server. "
            "Install with: pip install claude-agent-sdk"
        )

    from harness.tools.memory_tools import registry as memory_registry

    mcp_tools = []

    for name, registered_tool in memory_registry.tools.items():
        # Build parameter types dict for the SDK tool decorator
        param_types = {}
        for param_name, param_info in registered_tool.parameters.items():
            type_map = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": list,
            }
            param_types[param_name] = type_map.get(param_info.get("type", "string"), str)

        # Create closure to capture the tool name
        def make_handler(tool_name):
            async def handler(args):
                result = await memory_registry.dispatch(tool_name, args)
                return {"content": [{"type": "text", "text": str(result)}]}
            return handler

        decorated = sdk_tool(name, registered_tool.description, param_types)(
            make_handler(name)
        )
        mcp_tools.append(decorated)

    return create_sdk_mcp_server(
        name="cogmem-memory",
        version="0.1.0",
        tools=mcp_tools,
    )


def get_memory_tool_names():
    """Get the MCP-qualified tool names for allowed_tools config.

    Returns names like 'mcp__cogmem-memory__Store'.
    """
    from harness.tools.memory_tools import registry
    return [f"mcp__cogmem-memory__{name}" for name in registry.tools]
