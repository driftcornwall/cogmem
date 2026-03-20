"""CogMem CLI entry point."""
import click

from cli.commands.init_cmd import init_cmd
from cli.commands.agent_cmd import (
    create_agent_cmd,
    list_agents_cmd,
    agent_info_cmd,
    delete_agent_cmd,
)
from cli.commands.run_cmd import run_cmd
from cli.commands.maintain_cmd import consolidate_cmd, fingerprint_cmd, health_cmd
from cli.commands.team_cmd import team_cmd


@click.group()
@click.version_option("0.1.0", prog_name="cogmem")
def cli() -> None:
    """CogMem — cognitive memory-first agent harness.

    Build, manage, and run AI agents with biologically-grounded memory
    architectures. Identity emerges from what an agent attends to,
    remembers, and chooses.
    """


cli.add_command(init_cmd)
cli.add_command(create_agent_cmd)
cli.add_command(list_agents_cmd)
cli.add_command(agent_info_cmd)
cli.add_command(delete_agent_cmd)
cli.add_command(run_cmd)
cli.add_command(consolidate_cmd)
cli.add_command(fingerprint_cmd)
cli.add_command(health_cmd)
cli.add_command(team_cmd)
