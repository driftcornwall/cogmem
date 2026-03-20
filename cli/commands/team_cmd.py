"""Team orchestration CLI command."""
import asyncio
import click


@click.command()
@click.argument("architecture", type=click.Choice(["roundtable", "council", "delegate"]))
@click.argument("agents", nargs=-1, required=True)
@click.option("--rounds", default=3, help="Number of rounds (roundtable)")
def team_cmd(architecture, agents, rounds):
    """Run a multi-agent team conversation."""
    if len(agents) < 2:
        click.echo("Error: Team requires at least 2 agents.", err=True)
        raise SystemExit(1)

    from harness.registry import AgentRegistry
    registry = AgentRegistry()
    agent_configs = []
    for name in agents:
        try:
            info = registry.get_agent_info(name)
            agent_configs.append(info)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

    if architecture == "roundtable":
        from teams.roundtable import RoundtableArchitecture
        arch = RoundtableArchitecture()
        arch.setup(agents=agent_configs, config={"rounds": rounds})
        click.echo(f"Roundtable: {', '.join(agents)} — {rounds} rounds")
        asyncio.run(_run_team(arch))
    else:
        click.echo(f"Architecture '{architecture}' not yet implemented.")
        raise SystemExit(1)


async def _run_team(arch):
    prompt = input("\nTopic: ")
    async for msg in arch.run(prompt):
        print(f"\n[{msg.agent}, Round {msg.round_num}]: {msg.content}")
    await arch.teardown()
    print("\nTeam session ended.")
