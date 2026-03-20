#!/usr/bin/env python3
"""
CogMem Database Initializer — Sets up PostgreSQL schema from cogmem.yaml.

Usage:
    python -m scripts.init_db                       # Create schema
    python -m scripts.init_db --swarm               # Also create swarm tables
    python -m scripts.init_db --reindex-embeddings   # Re-create embedding index
"""

import sys
import os
import argparse
from pathlib import Path

# Ensure memory/ is importable
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "memory"))
sys.path.insert(0, str(_ROOT))


def create_registry_schema(conn) -> None:
    """Create the cogmem_registry schema and its tables.

    Safe to call multiple times — all statements are IF NOT EXISTS.
    """
    cur = conn.cursor()

    # Schema
    cur.execute("CREATE SCHEMA IF NOT EXISTS cogmem_registry")

    # Agents table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cogmem_registry.agents (
            name VARCHAR PRIMARY KEY,
            schema_name VARCHAR UNIQUE NOT NULL,
            path TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_active TIMESTAMPTZ DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'
        )
    """)

    # Schema versions table (tracks which migrations have been applied)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cogmem_registry.schema_versions (
            schema_name VARCHAR NOT NULL,
            migration_id VARCHAR NOT NULL,
            applied_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (schema_name, migration_id)
        )
    """)

    cur.close()


def main():
    parser = argparse.ArgumentParser(description="Initialize CogMem database")
    parser.add_argument('--config', type=str, default=None, help='Path to cogmem.yaml')
    parser.add_argument('--swarm', action='store_true', help='Also create swarm coordination tables')
    parser.add_argument('--reindex-embeddings', action='store_true', help='Drop and recreate embedding index')
    args = parser.parse_args()

    # Load config
    from config import load_config
    config = load_config(args.config)

    agent_name = config['agent']['schema']
    db_cfg = config['database']
    embed_dims = config['models']['embeddings']['dimensions']

    print(f"CogMem Database Init")
    print(f"  Agent: {config['agent']['name']} (schema: {agent_name})")
    print(f"  Database: {db_cfg['host']}:{db_cfg['port']}/{db_cfg['name']}")
    print(f"  Embedding dimensions: {embed_dims}")
    print()

    # Set DB env vars
    os.environ['DB_HOST'] = str(db_cfg['host'])
    os.environ['DB_PORT'] = str(db_cfg['port'])
    os.environ['DB_NAME'] = str(db_cfg['name'])
    os.environ['DB_USER'] = str(db_cfg['user'])
    os.environ['DB_PASSWORD'] = str(db_cfg['password'])

    import psycopg2

    # Connect as admin to create extensions and schema
    conn = psycopg2.connect(
        host=db_cfg['host'],
        port=db_cfg['port'],
        dbname=db_cfg['name'],
        user=db_cfg['user'],
        password=db_cfg['password'],
    )
    conn.autocommit = True
    cur = conn.cursor()

    # 0. Create cogmem_registry schema (idempotent)
    print("[0/5] Creating cogmem_registry schema...")
    try:
        create_registry_schema(conn)
        print("  cogmem_registry: OK")
    except Exception as e:
        print(f"  cogmem_registry: WARNING — {e}")

    # 1. Create extensions
    print("[1/5] Creating extensions...")
    for ext in ['vector', 'uuid-ossp']:
        try:
            cur.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')
            print(f"  {ext}: OK")
        except psycopg2.Error as e:
            print(f"  {ext}: {e.pgerror.strip() if e.pgerror else e}")

    # 2. Read and template schema.sql
    print("[2/5] Templating schema...")
    schema_path = _ROOT / "database" / "schema.sql"
    schema_sql = schema_path.read_text(encoding='utf-8')

    # Replace hardcoded halfvec dimension
    schema_sql = schema_sql.replace('halfvec(2560)', f'halfvec({embed_dims})')

    # 3. Create agent schema
    print(f"[3/5] Creating schema '{agent_name}'...")
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {agent_name}")

    # Run create_agent_schema function (defined in schema.sql)
    try:
        cur.execute(schema_sql)
        cur.execute(f"SELECT create_agent_schema('{agent_name}')")
        print(f"  Schema '{agent_name}': OK")
    except psycopg2.Error as e:
        if 'already exists' in str(e):
            print(f"  Schema '{agent_name}': already exists (OK)")
        else:
            print(f"  Error: {e}")

    # 4. Create shared schema (essential tables only)
    print("[4/5] Creating shared tables...")
    cur.execute("CREATE SCHEMA IF NOT EXISTS shared")
    shared_tables = [
        """CREATE TABLE IF NOT EXISTS shared.agent_registry (
            agent_name TEXT PRIMARY KEY,
            schema_name TEXT NOT NULL,
            registered_at TIMESTAMPTZ DEFAULT NOW(),
            last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'
        )""",
        """CREATE TABLE IF NOT EXISTS shared.key_value_store (
            key TEXT PRIMARY KEY,
            value JSONB,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS shared.procedural_chunks (
            id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            chunk JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )""",
    ]
    for sql in shared_tables:
        cur.execute(sql)
    print("  agent_registry, key_value_store, procedural_chunks: OK")

    if args.swarm:
        print("  Creating swarm tables...")
        swarm_tables_path = _ROOT / "database" / "schema_swarm_v2.sql"
        if swarm_tables_path.exists():
            cur.execute(swarm_tables_path.read_text(encoding='utf-8'))
            print("  Swarm tables: OK")
        else:
            print("  Swarm schema file not found, skipping")

    # Register agent
    cur.execute("""
        INSERT INTO shared.agent_registry (agent_name, schema_name)
        VALUES (%s, %s)
        ON CONFLICT (agent_name) DO UPDATE SET last_heartbeat = NOW()
    """, (config['agent']['name'], agent_name))

    # 5. Verify
    print("[5/5] Verifying...")
    cur.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{agent_name}'")
    table_count = cur.fetchone()[0]
    print(f"  Tables in '{agent_name}': {table_count}")

    # Check embedding service
    embed_cfg = config['models']['embeddings']
    if embed_cfg['provider'] == 'openai':
        api_key = os.environ.get(embed_cfg.get('api_key_env', 'OPENAI_API_KEY'), '')
        if api_key:
            print(f"  Embeddings: OpenAI ({embed_cfg['model']}) -- API key found")
        else:
            print(f"  Embeddings: WARNING -- {embed_cfg.get('api_key_env', 'OPENAI_API_KEY')} not set")
    elif embed_cfg['provider'] == 'local':
        endpoint = embed_cfg.get('endpoint', 'http://localhost:8080')
        print(f"  Embeddings: local ({endpoint}) -- verify service is running")

    cur.close()
    conn.close()

    print()
    print("Done! Run 'cogmem health' or 'python -m memory.toolkit health' to verify.")


if __name__ == '__main__':
    main()
