"""CogMem init command — bootstrap infrastructure."""
import click


@click.command("init")
@click.option("--with-docker", is_flag=True, default=False, help="Start Docker containers for DB/embeddings.")
@click.option("--db-only", is_flag=True, default=False, help="Bootstrap database only (no other services).")
def init_cmd(with_docker: bool, db_only: bool) -> None:
    """Initialise CogMem infrastructure.

    Sets up the PostgreSQL schema, pgvector extension, and optionally
    starts the supporting Docker containers.
    """
    click.echo("CogMem init starting...")

    if with_docker:
        click.echo("  [TODO] Starting Docker containers (DB, text-embed, image-embed, NLI, ollama)...")
    elif db_only:
        click.echo("  [TODO] Bootstrapping database schema only...")
    else:
        click.echo("  [TODO] Run with --with-docker to start all services, or --db-only for DB alone.")

    click.echo("Done.")
