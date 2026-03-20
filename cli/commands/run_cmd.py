"""CogMem run command — start an interactive agent session."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import click

from harness.lifecycle import AgentLifecycle
from harness.registry import AgentRegistry


@click.command("run")
@click.argument("name")
@click.option(
    "--continue-session",
    "continue_session",
    is_flag=True,
    default=False,
    help="Resume from the last session rather than starting fresh.",
)
@click.option(
    "--model",
    default=None,
    help="Override the model specified in cogmem.yaml.",
)
@click.option(
    "--agents-dir",
    "agents_dir",
    default=None,
    type=click.Path(),
    help="Directory to search for agents. Defaults to ~/.cogmem/agents/.",
)
def run_cmd(
    name: str,
    continue_session: bool,
    model: Optional[str],
    agents_dir: Optional[str],
) -> None:
    """Run an interactive session with a CogMem agent.

    NAME is the display name of the agent to run (e.g. Nova).

    The agent is primed, then enters a REPL loop. Type 'exit' or 'quit' to end
    the session; the agent will consolidate and dream before exiting.
    """
    registry = AgentRegistry(agents_dir=agents_dir)

    try:
        info = registry.get_agent_info(name)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    agent_dir = Path(info["path"])
    lifecycle = AgentLifecycle(agent_dir=agent_dir)

    # Prime the session
    system_prompt = lifecycle.prime()
    if system_prompt:
        click.echo("\n--- System Prompt ---")
        click.echo(system_prompt)
        click.echo("---------------------\n")

    session_label = "continued" if continue_session else "new"
    effective_model = model or info.get("model") or "claude-sonnet-4-6"
    click.echo(f"Starting {session_label} session with '{name}' (model: {effective_model})")
    click.echo("Type 'exit' or 'quit' to end.\n")

    # Select engine based on provider from config
    config = lifecycle._config
    provider = config.get("model", {}).get("provider", "claude-api")

    if provider in {"claude-api", "claude-account"}:
        try:
            from harness.claude_engine import ClaudeEngine
            engine = ClaudeEngine(config)
        except ImportError as exc:
            click.echo(
                f"Error: Could not import ClaudeEngine.\n{exc}",
                err=True,
            )
            raise SystemExit(1) from exc
    else:
        click.echo(f"Provider not yet supported: {provider}", err=True)
        raise SystemExit(1)

    async def conversation_loop() -> None:
        while True:
            try:
                user_input = click.prompt(f"{name}>", prompt_suffix=" ")
            except (EOFError, KeyboardInterrupt):
                click.echo()
                return

            stripped = user_input.strip()
            if stripped.lower() in {"exit", "quit"}:
                return
            if not stripped:
                continue

            try:
                async for message in engine.run(stripped, system_prompt=system_prompt):
                    if message.content:
                        click.echo(f"[{name}] {message.content}")
            except ImportError as exc:
                click.echo(
                    f"\nError: Claude Agent SDK not installed.\n{exc}\n",
                    err=True,
                )
                return
            except Exception as exc:  # noqa: BLE001
                click.echo(f"\nError during engine run: {exc}", err=True)
                return

    try:
        asyncio.run(conversation_loop())
    finally:
        click.echo("\nSession ending — consolidating...")
        lifecycle.consolidate()
        click.echo("Consolidation done. Running dream phase...")
        lifecycle.dream()
        click.echo("Done. Goodbye.")
