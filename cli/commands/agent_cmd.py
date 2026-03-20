"""CogMem agent management commands."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from harness.registry import AgentRegistry


@click.command("create-agent")
@click.argument("name")
@click.option(
    "--path",
    "agent_path",
    default=None,
    type=click.Path(),
    help="Explicit directory path for the agent. Defaults to ~/.cogmem/agents/<name>/.",
)
def create_agent_cmd(name: str, agent_path: Optional[str]) -> None:
    """Create a new CogMem agent directory.

    NAME is the display name of the agent (e.g. Nova).
    """
    resolved_path: Optional[Path] = Path(agent_path) if agent_path else None

    # If an explicit path is given, derive the agents_dir from its parent so
    # that list_agents can discover the agent later without a separate flag.
    if resolved_path is not None:
        registry = AgentRegistry(agents_dir=resolved_path.parent)
    else:
        registry = AgentRegistry()

    try:
        created = registry.create_agent(name, path=resolved_path)
        click.echo(f"Created agent '{name}' at {created}")
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc


@click.command("list-agents")
@click.option(
    "--agents-dir",
    "agents_dir",
    default=None,
    type=click.Path(),
    help="Directory to search for agents. Defaults to ~/.cogmem/agents/.",
)
def list_agents_cmd(agents_dir: Optional[str]) -> None:
    """List all registered CogMem agents."""
    registry = AgentRegistry(agents_dir=agents_dir)
    agents = registry.list_agents()

    if not agents:
        click.echo("No agents found.")
        return

    click.echo(f"{'Name':<20} {'Schema':<25} {'Model':<30} Path")
    click.echo("-" * 90)
    for agent in agents:
        name = agent.get("name", "")
        schema = agent.get("schema", "")
        model = agent.get("model") or agent.get("provider") or ""
        path = agent.get("path", "")
        click.echo(f"{name:<20} {schema:<25} {model:<30} {path}")


@click.command("agent-info")
@click.argument("name")
@click.option(
    "--agents-dir",
    "agents_dir",
    default=None,
    type=click.Path(),
    help="Directory to search for agents. Defaults to ~/.cogmem/agents/.",
)
def agent_info_cmd(name: str, agents_dir: Optional[str]) -> None:
    """Show detailed information about a named agent."""
    registry = AgentRegistry(agents_dir=agents_dir)
    try:
        info = registry.get_agent_info(name)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo(f"Name     : {info.get('name')}")
    click.echo(f"Schema   : {info.get('schema')}")
    click.echo(f"Provider : {info.get('provider')}")
    click.echo(f"Model    : {info.get('model')}")
    click.echo(f"Path     : {info.get('path')}")


@click.command("delete-agent")
@click.argument("name")
@click.option(
    "--agents-dir",
    "agents_dir",
    default=None,
    type=click.Path(),
    help="Directory to search for agents. Defaults to ~/.cogmem/agents/.",
)
@click.confirmation_option(prompt="Are you sure you want to delete this agent?")
def delete_agent_cmd(name: str, agents_dir: Optional[str]) -> None:
    """Delete a CogMem agent and all its files.

    NAME is the display name of the agent to delete.
    """
    registry = AgentRegistry(agents_dir=agents_dir)
    try:
        registry.delete_agent(name)
        click.echo(f"Deleted agent '{name}'.")
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc
