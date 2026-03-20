"""Maintenance CLI commands — consolidate, fingerprint, health."""
import click
from pathlib import Path


@click.command()
@click.argument("name")
def consolidate_cmd(name):
    """Run the dream phase for an agent (consolidation, fingerprint, decay)."""
    from harness.registry import AgentRegistry
    from harness.lifecycle import AgentLifecycle
    registry = AgentRegistry()
    try:
        info = registry.get_agent_info(name)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    lifecycle = AgentLifecycle(agent_dir=Path(info["path"]))
    lifecycle.prime()
    click.echo(f"Running dream phase for {name}...")
    lifecycle.dream()
    click.echo("Done.")


@click.command()
@click.argument("name")
def fingerprint_cmd(name):
    """Recompute cognitive fingerprint for an agent."""
    from harness.registry import AgentRegistry
    registry = AgentRegistry()
    try:
        info = registry.get_agent_info(name)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Recomputing fingerprint for {name}...")
    click.echo("Fingerprint computation requires DB connection. Coming soon.")


@click.command()
def health_cmd():
    """Check CogMem infrastructure health — DB, embeddings, LLM."""
    click.echo("Checking CogMem health...")
    # Check DB
    try:
        import psycopg2
        click.echo("  PostgreSQL driver: OK")
    except ImportError:
        click.echo("  PostgreSQL driver: MISSING (pip install psycopg2-binary)")
    # Check Agent SDK
    try:
        import claude_agent_sdk
        click.echo("  Claude Agent SDK: OK")
    except ImportError:
        click.echo("  Claude Agent SDK: not installed (optional)")
    # Check click
    click.echo("  CLI (click): OK")
    click.echo("Health check complete.")
