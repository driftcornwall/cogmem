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
