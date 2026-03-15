#!/usr/bin/env python3
"""Migrate council schemas to match drift schema."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5433, dbname='agent_memory',
    user='agent_admin', password='agent_memory_local_dev'
)
conn.autocommit = True
cur = conn.cursor()

SCHEMAS = [
    'council_chalmers', 'council_dennett', 'council_hofstadter',
    'council_lovelace', 'council_mckenna', 'council_minsky',
    'council_socrates', 'council_tesla', 'council_tesla2', 'council_turing'
]

def safe_exec(sql, label):
    try:
        cur.execute(sql)
        print(f"  {label}: OK")
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()
        conn.autocommit = True
    except psycopg2.errors.DuplicateTable:
        conn.rollback()
        conn.autocommit = True
        print(f"  {label}: already exists")
    except Exception as e:
        conn.rollback()
        conn.autocommit = True
        print(f"  {label}: ERROR {e}")

for schema in SCHEMAS:
    print(f"=== {schema} ===")
    short = schema.replace("council_", "c")

    # 1. Missing columns on memories
    for col, dtype in [
        ("evidence_type", "VARCHAR(50)"),
        ("freshness", "DOUBLE PRECISION"),
        ("importance", "DOUBLE PRECISION"),
        ("memory_tier", "VARCHAR(20)"),
        ("q_value", "DOUBLE PRECISION"),
        ("valence", "DOUBLE PRECISION"),
    ]:
        safe_exec(
            f"ALTER TABLE {schema}.memories ADD COLUMN {col} {dtype}",
            f"memories.{col}"
        )

    # 2. Missing columns on lessons
    for col, dtype in [("last_recalled", "TIMESTAMPTZ"), ("recalled_count", "INTEGER")]:
        safe_exec(
            f"ALTER TABLE {schema}.lessons ADD COLUMN {col} {dtype}",
            f"lessons.{col}"
        )

    # 3. session_events
    safe_exec(f"""
        CREATE TABLE {schema}.session_events (
            id BIGSERIAL PRIMARY KEY,
            session_id INTEGER,
            event_time TIMESTAMPTZ NOT NULL DEFAULT now(),
            sequence_num INTEGER NOT NULL,
            event_type VARCHAR NOT NULL,
            content TEXT NOT NULL,
            content_preview VARCHAR,
            entities JSONB DEFAULT '{{}}'::jsonb,
            platform VARCHAR,
            tool_name VARCHAR,
            action VARCHAR,
            transcript_offset INTEGER,
            source_block_type VARCHAR,
            tags TEXT[],
            extra JSONB DEFAULT '{{}}'::jsonb
        )
    """, "session_events")
    safe_exec(f"CREATE INDEX idx_{short}_events_session ON {schema}.session_events (session_id)", f"idx_events_session")
    safe_exec(f"CREATE INDEX idx_{short}_events_time ON {schema}.session_events (event_time)", f"idx_events_time")
    safe_exec(f"CREATE INDEX idx_{short}_events_type ON {schema}.session_events (event_type)", f"idx_events_type")

    # 4. somatic_markers
    safe_exec(f"""
        CREATE TABLE {schema}.somatic_markers (
            situation_hash VARCHAR PRIMARY KEY,
            features_text TEXT NOT NULL,
            embedding vector(384),
            valence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            count INTEGER NOT NULL DEFAULT 0,
            category VARCHAR DEFAULT 'general',
            last_activated TIMESTAMPTZ,
            created TIMESTAMPTZ DEFAULT now()
        )
    """, "somatic_markers")

    # 5. explanations
    safe_exec(f"""
        CREATE TABLE {schema}.explanations (
            id SERIAL PRIMARY KEY,
            session_id TEXT,
            module TEXT NOT NULL,
            operation TEXT NOT NULL,
            inputs JSONB DEFAULT '{{}}'::jsonb,
            output JSONB DEFAULT '{{}}'::jsonb,
            reasoning JSONB DEFAULT '[]'::jsonb,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """, "explanations")
    safe_exec(f"CREATE INDEX idx_{short}_expl_module ON {schema}.explanations (module, operation)", f"idx_expl_module")
    safe_exec(f"CREATE INDEX idx_{short}_expl_session ON {schema}.explanations (session_id)", f"idx_expl_session")

    # 6. q_value_history
    safe_exec(f"""
        CREATE TABLE {schema}.q_value_history (
            id SERIAL PRIMARY KEY,
            memory_id VARCHAR NOT NULL,
            session_id INTEGER,
            old_q DOUBLE PRECISION NOT NULL,
            new_q DOUBLE PRECISION NOT NULL,
            reward DOUBLE PRECISION NOT NULL,
            reward_source VARCHAR,
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """, "q_value_history")
    safe_exec(f"CREATE INDEX idx_{short}_qhist_mem ON {schema}.q_value_history (memory_id)", f"idx_qhist_mem")

    # 7. typed_edges
    safe_exec(f"""
        CREATE TABLE {schema}.typed_edges (
            id SERIAL PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relationship VARCHAR NOT NULL,
            confidence DOUBLE PRECISION DEFAULT 0.8,
            evidence TEXT,
            auto_extracted BOOLEAN DEFAULT false,
            created TIMESTAMPTZ DEFAULT now(),
            UNIQUE(source_id, target_id, relationship)
        )
    """, "typed_edges")
    safe_exec(f"CREATE INDEX idx_{short}_te_src ON {schema}.typed_edges (source_id)", f"idx_te_src")
    safe_exec(f"CREATE INDEX idx_{short}_te_tgt ON {schema}.typed_edges (target_id)", f"idx_te_tgt")
    safe_exec(f"CREATE INDEX idx_{short}_te_rel ON {schema}.typed_edges (relationship)", f"idx_te_rel")

    print()

conn.close()
print("Migration complete.")
