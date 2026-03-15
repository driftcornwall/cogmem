"""
Database Abstraction Layer (DAL) for Agent Memory System.

Provides schema-aware access to PostgreSQL + pgvector.
All memory modules import from here instead of doing file I/O.

Usage:
    from database.db import MemoryDB
    db = MemoryDB('spin')  # or 'drift'
    memory = db.get_memory('abc12345')
"""

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2 import pool

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CRED_PATH = Path.home() / '.config' / 'spindrift' / 'db-credentials.json'

DEFAULT_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'dbname': os.environ.get('DB_NAME', 'agent_memory'),
    'user': os.environ.get('DB_USER', 'agent_admin'),
    'password': os.environ.get('DB_PASSWORD', 'agent_memory_local_dev'),
}


def load_config(path: Optional[Path] = None) -> dict:
    """Load DB config from credentials file, falling back to defaults."""
    cred_path = path or DEFAULT_CRED_PATH
    if cred_path.exists():
        with open(cred_path, 'r', encoding='utf-8') as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG.copy()


# ---------------------------------------------------------------------------
# Connection Pool (singleton per process)
# ---------------------------------------------------------------------------

_pool: Optional[pool.ThreadedConnectionPool] = None


def get_pool(config: Optional[dict] = None) -> pool.ThreadedConnectionPool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None or _pool.closed:
        cfg = config or load_config()
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=cfg['host'],
            port=cfg['port'],
            dbname=cfg['dbname'],
            user=cfg['user'],
            password=cfg['password'],
            # TCP keepalive: prevent stale connections in long-running daemons.
            # Sends keepalive probe after 60s idle, retries every 10s, gives up after 5 failures.
            keepalives=1,
            keepalives_idle=60,
            keepalives_interval=10,
            keepalives_count=5,
        )
    return _pool


def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool and not _pool.closed:
        _pool.closeall()
        _pool = None


@contextmanager
def get_conn(config: Optional[dict] = None):
    """Get a connection from the pool with auto-commit/rollback.

    Validates the connection is alive before yielding. If the connection
    is dead (stale from server-side close), resets the pool and retries once.
    """
    global _pool
    p = get_pool(config)
    conn = p.getconn()
    # Validate connection is alive — detects server-side closes
    try:
        conn.isolation_level  # Quick attribute check
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        # Connection is dead — close pool and retry with fresh connections
        try:
            p.putconn(conn, close=True)
        except Exception:
            pass
        close_pool()
        p = get_pool(config)
        conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


# ---------------------------------------------------------------------------
# MemoryDB — schema-aware DAL
# ---------------------------------------------------------------------------

class MemoryDB:
    """Database abstraction layer for a single agent's memory schema."""

    def __init__(self, schema: str = 'spin', config: Optional[dict] = None):
        self.schema = schema
        self._config = config

    def _table(self, name: str) -> str:
        """Return fully-qualified table name."""
        return f"{self.schema}.{name}"

    @contextmanager
    def _conn(self):
        """Get a connection from the pool."""
        with get_conn(self._config) as conn:
            yield conn

    # -----------------------------------------------------------------------
    # MEMORIES — CRUD
    # -----------------------------------------------------------------------

    def get_memory(self, memory_id: str) -> Optional[dict]:
        """Fetch a single memory by ID."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM {self._table('memories')} WHERE id = %s",
                    (memory_id,)
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def insert_memory(self, memory_id: str, type_: str, content: str,
                      tags: list = None, entities: dict = None,
                      emotional_weight: float = 0.5,
                      topic_context: list = None, contact_context: list = None,
                      platform_context: list = None, extra_metadata: dict = None,
                      created: datetime = None,
                      **kwargs) -> dict:
        """Insert a new memory."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('memories')}
                    (id, type, content, created, emotional_weight, tags, entities,
                     topic_context, contact_context, platform_context, extra_metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (
                    memory_id, type_, content,
                    created or datetime.now(timezone.utc),
                    emotional_weight,
                    tags or [],
                    psycopg2.extras.Json(entities or {}),
                    topic_context or [],
                    contact_context or [],
                    platform_context or [],
                    psycopg2.extras.Json(extra_metadata or {}),
                ))
                return dict(cur.fetchone())

    def update_memory(self, memory_id: str, **fields) -> Optional[dict]:
        """Update specific fields of a memory."""
        if not fields:
            return self.get_memory(memory_id)

        set_clauses = []
        values = []
        for key, val in fields.items():
            if key in ('entities', 'retrieval_outcomes', 'source', 'extra_metadata'):
                set_clauses.append(f"{key} = %s")
                values.append(psycopg2.extras.Json(val))
            else:
                set_clauses.append(f"{key} = %s")
                values.append(val)

        values.append(memory_id)

        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"UPDATE {self._table('memories')} SET {', '.join(set_clauses)} WHERE id = %s RETURNING *",
                    values
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self._table('memories')} WHERE id = %s",
                    (memory_id,)
                )
                return cur.rowcount > 0

    def recall_memory(self, memory_id: str, session_id: int = None,
                      source: str = 'manual') -> Optional[dict]:
        """Recall a memory: increment count, update timestamp, log to session."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Update recall metadata
                cur.execute(f"""
                    UPDATE {self._table('memories')}
                    SET recall_count = recall_count + 1,
                        last_recalled = NOW(),
                        sessions_since_recall = 0
                    WHERE id = %s
                    RETURNING *
                """, (memory_id,))
                row = cur.fetchone()
                if not row:
                    return None

                # Log to session_recalls if session provided
                if session_id is not None:
                    cur.execute(f"""
                        INSERT INTO {self._table('session_recalls')}
                        (session_id, memory_id, source)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (session_id, memory_id, source))

                return dict(row)

    def list_memories(self, type_: str = None, tags: list = None,
                      limit: int = 100, offset: int = 0) -> list:
        """List memories with optional filters."""
        conditions = []
        values = []

        if type_:
            conditions.append("type = %s")
            values.append(type_)
        if tags:
            conditions.append("tags && %s")  # array overlap
            values.append(tags)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        values.extend([limit, offset])

        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM {self._table('memories')} {where} ORDER BY created DESC LIMIT %s OFFSET %s",
                    values
                )
                return [dict(r) for r in cur.fetchall()]

    def count_memories(self, type_: str = None) -> int:
        """Count memories, optionally by type."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                if type_:
                    cur.execute(f"SELECT COUNT(*) FROM {self._table('memories')} WHERE type = %s", (type_,))
                else:
                    cur.execute(f"SELECT COUNT(*) FROM {self._table('memories')}")
                return cur.fetchone()[0]

    def search_fulltext(self, query: str, limit: int = 10) -> list:
        """Full-text search on memory content."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT *, ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s)) AS rank
                    FROM {self._table('memories')}
                    WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                    ORDER BY rank DESC
                    LIMIT %s
                """, (query, query, limit))
                return [dict(r) for r in cur.fetchall()]

    def find_by_entity(self, entity_type: str, entity_name: str, limit: int = 50) -> list:
        """Find memories containing a specific entity."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT * FROM {self._table('memories')}
                    WHERE entities->%s ? %s
                    ORDER BY created DESC LIMIT %s
                """, (entity_type, entity_name, limit))
                return [dict(r) for r in cur.fetchall()]

    # -----------------------------------------------------------------------
    # Q-VALUES — MemRL utility scoring
    # -----------------------------------------------------------------------

    def get_q_values(self, memory_ids: list) -> dict:
        """Batch-fetch Q-values for a list of memory IDs.

        Returns {memory_id: q_value} dict. Missing IDs get default 0.5.
        """
        if not memory_ids:
            return {}
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, q_value FROM {self._table('memories')} WHERE id = ANY(%s)",
                    (list(memory_ids),)
                )
                result = {row[0]: float(row[1]) if row[1] is not None else 0.5
                          for row in cur.fetchall()}
        # Fill in defaults for any IDs not found
        for mid in memory_ids:
            if mid not in result:
                result[mid] = 0.5
        return result

    # -----------------------------------------------------------------------
    # EMBEDDINGS — pgvector search
    # -----------------------------------------------------------------------

    def store_embedding(self, memory_id: str, embedding: list, preview: str = '',
                        model: str = 'Qwen3-Embedding-0.6B'):
        """Store or update a text embedding (halfvec for 2560-dim support)."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('text_embeddings')} (memory_id, embedding, preview, model)
                    VALUES (%s, %s::halfvec, %s, %s)
                    ON CONFLICT (memory_id)
                    DO UPDATE SET embedding = EXCLUDED.embedding, preview = EXCLUDED.preview,
                                  model = EXCLUDED.model, indexed_at = NOW()
                """, (memory_id, str(embedding), preview, model))

    def search_embeddings(self, query_embedding: list, limit: int = 5,
                          type_filter: str = None) -> list:
        """Semantic search using pgvector cosine distance (halfvec)."""
        vec_str = str(query_embedding)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if type_filter:
                    cur.execute(f"""
                        SELECT m.*, e.preview,
                               1 - (e.embedding <=> %s::halfvec) AS similarity
                        FROM {self._table('text_embeddings')} e
                        JOIN {self._table('memories')} m ON m.id = e.memory_id
                        WHERE m.type = %s
                        ORDER BY e.embedding <=> %s::halfvec
                        LIMIT %s
                    """, (vec_str, type_filter, vec_str, limit))
                else:
                    cur.execute(f"""
                        SELECT m.*, e.preview,
                               1 - (e.embedding <=> %s::halfvec) AS similarity
                        FROM {self._table('text_embeddings')} e
                        JOIN {self._table('memories')} m ON m.id = e.memory_id
                        ORDER BY e.embedding <=> %s::halfvec
                        LIMIT %s
                    """, (vec_str, vec_str, limit))
                return [dict(r) for r in cur.fetchall()]

    # -----------------------------------------------------------------------
    # CO-OCCURRENCE — edges v3
    # -----------------------------------------------------------------------

    def get_edge(self, id1: str, id2: str) -> Optional[dict]:
        """Get a co-occurrence edge (auto-canonicalizes order)."""
        a, b = (id1, id2) if id1 < id2 else (id2, id1)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM {self._table('edges_v3')} WHERE id1 = %s AND id2 = %s",
                    (a, b)
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def upsert_edge(self, id1: str, id2: str, belief: float,
                    platform_context: dict = None, activity_context: dict = None,
                    topic_context: dict = None, **kwargs) -> dict:
        """Insert or update a co-occurrence edge."""
        a, b = (id1, id2) if id1 < id2 else (id2, id1)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('edges_v3')} (id1, id2, belief, first_formed, last_updated,
                                                            platform_context, activity_context, topic_context)
                    VALUES (%s, %s, %s, NOW(), NOW(), %s, %s, %s)
                    ON CONFLICT (id1, id2)
                    DO UPDATE SET belief = EXCLUDED.belief, last_updated = NOW(),
                                  platform_context = EXCLUDED.platform_context,
                                  activity_context = EXCLUDED.activity_context,
                                  topic_context = EXCLUDED.topic_context
                    RETURNING *
                """, (
                    a, b, belief,
                    psycopg2.extras.Json(platform_context or {}),
                    psycopg2.extras.Json(activity_context or {}),
                    psycopg2.extras.Json(topic_context or {}),
                ))
                return dict(cur.fetchone())

    def add_observation(self, id1: str, id2: str, source_type: str,
                        session_id: str = None, agent: str = None,
                        platform: str = None, activity: str = None,
                        weight: float = 1.0, trust_tier: str = 'self',
                        direction_weight: float = 0.0) -> dict:
        """Add an observation to an edge. direction_weight encodes temporal order."""
        a, b = (id1, id2) if id1 < id2 else (id2, id1)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('edge_observations')}
                    (edge_id1, edge_id2, observed_at, source_type, session_id,
                     agent, platform, activity, weight, trust_tier, direction_weight)
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (a, b, source_type, session_id, agent, platform, activity,
                      weight, trust_tier, direction_weight))
                return dict(cur.fetchone())

    def batch_decay_edges(self, decay_rate: float, exclude_pairs: list = None) -> int:
        """Decay all edge beliefs by rate, excluding recently reinforced pairs."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                if exclude_pairs:
                    # Build exclusion list of (id1, id2) tuples
                    placeholders = ','.join(['(%s, %s)'] * len(exclude_pairs))
                    flat_pairs = []
                    for p in exclude_pairs:
                        a, b = (p[0], p[1]) if p[0] < p[1] else (p[1], p[0])
                        flat_pairs.extend([a, b])
                    cur.execute(f"""
                        UPDATE {self._table('edges_v3')}
                        SET belief = belief * (1 - %s)
                        WHERE (id1, id2) NOT IN ({placeholders})
                        AND belief > 0
                    """, [decay_rate] + flat_pairs)
                else:
                    cur.execute(f"""
                        UPDATE {self._table('edges_v3')}
                        SET belief = belief * (1 - %s)
                        WHERE belief > 0
                    """, (decay_rate,))
                return cur.rowcount

    def prune_weak_edges(self, threshold: float = 0.01) -> int:
        """Remove edges with belief below threshold."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self._table('edges_v3')} WHERE belief < %s",
                    (threshold,)
                )
                return cur.rowcount

    def get_neighbors(self, memory_id: str, min_belief: float = 0.0,
                      limit: int = 50) -> list:
        """Get co-occurring neighbors of a memory."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT * FROM {self._table('edges_v3')}
                    WHERE (id1 = %s OR id2 = %s) AND belief >= %s
                    ORDER BY belief DESC
                    LIMIT %s
                """, (memory_id, memory_id, min_belief, limit))
                return [dict(r) for r in cur.fetchall()]

    def edge_stats(self) -> dict:
        """Get co-occurrence graph statistics."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT
                        COUNT(*) as total_edges,
                        SUM(belief) as total_belief,
                        AVG(belief) as avg_belief,
                        COUNT(*) FILTER (WHERE belief >= 3.0) as strong_links
                    FROM {self._table('edges_v3')}
                """)
                row = cur.fetchone()
                return {
                    'total_edges': row[0],
                    'total_belief': float(row[1] or 0),
                    'avg_belief': float(row[2] or 0),
                    'strong_links': row[3],
                }

    # -----------------------------------------------------------------------
    # SESSIONS
    # -----------------------------------------------------------------------

    def start_session(self) -> int:
        """Start a new session, return session ID."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                # End any active sessions
                cur.execute(f"""
                    UPDATE {self._table('sessions')}
                    SET ended = NOW(), is_active = FALSE
                    WHERE is_active = TRUE
                """)
                # Start new
                cur.execute(f"""
                    INSERT INTO {self._table('sessions')} (started, is_active)
                    VALUES (NOW(), TRUE)
                    RETURNING id
                """)
                return cur.fetchone()[0]

    def end_session(self, session_id: int = None):
        """End a session (or the current active one)."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                if session_id:
                    cur.execute(f"""
                        UPDATE {self._table('sessions')}
                        SET ended = NOW(), is_active = FALSE
                        WHERE id = %s
                    """, (session_id,))
                else:
                    cur.execute(f"""
                        UPDATE {self._table('sessions')}
                        SET ended = NOW(), is_active = FALSE
                        WHERE is_active = TRUE
                    """)

    def get_active_session(self) -> Optional[int]:
        """Get the current active session ID."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id FROM {self._table('sessions')}
                    WHERE is_active = TRUE
                    ORDER BY started DESC LIMIT 1
                """)
                row = cur.fetchone()
                return row[0] if row else None

    # -----------------------------------------------------------------------
    # REJECTIONS
    # -----------------------------------------------------------------------

    def log_rejection(self, category: str, reason: str, target: str = None,
                      context: str = None, tags: list = None, source: str = None) -> dict:
        """Log a rejection event."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('rejections')}
                    (timestamp, category, reason, target, context, tags, source)
                    VALUES (NOW(), %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (category, reason, target, context, tags or [], source))
                return dict(cur.fetchone())

    # -----------------------------------------------------------------------
    # LESSONS
    # -----------------------------------------------------------------------

    def get_lessons(self, category: str = None) -> list:
        """Get lessons, optionally filtered by category."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if category:
                    cur.execute(f"SELECT * FROM {self._table('lessons')} WHERE category = %s", (category,))
                else:
                    cur.execute(f"SELECT * FROM {self._table('lessons')}")
                return [dict(r) for r in cur.fetchall()]

    def add_lesson(self, lesson_id: str, category: str, lesson: str,
                   evidence: str = None, source: str = 'manual',
                   confidence: float = 0.7) -> dict:
        """Add or update a lesson."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('lessons')}
                    (id, category, lesson, evidence, source, confidence)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        lesson = EXCLUDED.lesson, evidence = EXCLUDED.evidence,
                        confidence = EXCLUDED.confidence
                    RETURNING *
                """, (lesson_id, category, lesson, evidence, source, confidence))
                return dict(cur.fetchone())

    # -----------------------------------------------------------------------
    # VITALS
    # -----------------------------------------------------------------------

    def record_vitals(self, metrics: dict):
        """Record a vitals snapshot."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('vitals_log')} (timestamp, metrics)
                    VALUES (NOW(), %s)
                """, (psycopg2.extras.Json(metrics),))

    # -----------------------------------------------------------------------
    # ATTESTATIONS
    # -----------------------------------------------------------------------

    def store_attestation(self, type_: str, hash_: str, data: dict):
        """Store an attestation."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('attestations')} (timestamp, type, hash, data)
                    VALUES (NOW(), %s, %s, %s)
                """, (type_, hash_, psycopg2.extras.Json(data)))

    # -----------------------------------------------------------------------
    # SOMATIC MARKERS (T2.3 — embedding-based fuzzy matching)
    # -----------------------------------------------------------------------

    def upsert_somatic_marker(self, situation_hash: str, features_text: str,
                               embedding: list = None, valence: float = 0.0,
                               confidence: float = 0.0, count: int = 0,
                               category: str = 'general',
                               last_activated: str = None):
        """Store or update a somatic marker with optional embedding."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                if embedding:
                    cur.execute(f"""
                        INSERT INTO {self._table('somatic_markers')}
                        (situation_hash, features_text, embedding, valence, confidence,
                         count, category, last_activated)
                        VALUES (%s, %s, %s::halfvec, %s, %s, %s, %s, %s)
                        ON CONFLICT (situation_hash) DO UPDATE SET
                            features_text = EXCLUDED.features_text,
                            embedding = EXCLUDED.embedding,
                            valence = EXCLUDED.valence,
                            confidence = EXCLUDED.confidence,
                            count = EXCLUDED.count,
                            category = EXCLUDED.category,
                            last_activated = EXCLUDED.last_activated
                    """, (situation_hash, features_text, str(embedding),
                          valence, confidence, count, category, last_activated))
                else:
                    cur.execute(f"""
                        INSERT INTO {self._table('somatic_markers')}
                        (situation_hash, features_text, valence, confidence,
                         count, category, last_activated)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (situation_hash) DO UPDATE SET
                            features_text = EXCLUDED.features_text,
                            valence = EXCLUDED.valence,
                            confidence = EXCLUDED.confidence,
                            count = EXCLUDED.count,
                            category = EXCLUDED.category,
                            last_activated = EXCLUDED.last_activated
                    """, (situation_hash, features_text,
                          valence, confidence, count, category, last_activated))

    def find_similar_markers(self, embedding: list, threshold: float = 0.70,
                              limit: int = 3) -> list:
        """Find somatic markers similar to query embedding via pgvector cosine."""
        vec_str = str(embedding)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT situation_hash, features_text, valence, confidence,
                           count, category, last_activated,
                           1 - (embedding <=> %s::halfvec) AS similarity
                    FROM {self._table('somatic_markers')}
                    WHERE embedding IS NOT NULL
                    AND 1 - (embedding <=> %s::halfvec) >= %s
                    ORDER BY embedding <=> %s::halfvec
                    LIMIT %s
                """, (vec_str, vec_str, threshold, vec_str, limit))
                return [dict(r) for r in cur.fetchall()]

    def load_all_somatic_markers(self) -> dict:
        """Load all somatic markers as a dict keyed by situation_hash."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT situation_hash, features_text, valence, confidence,
                           count, category, last_activated
                    FROM {self._table('somatic_markers')}
                """)
                result = {}
                for row in cur.fetchall():
                    h = row.pop('situation_hash')
                    result[h] = dict(row)
                return result

    def count_somatic_markers(self) -> int:
        """Count total somatic markers."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self._table('somatic_markers')}")
                return cur.fetchone()[0]

    def delete_somatic_marker(self, situation_hash: str) -> bool:
        """Delete a somatic marker."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    DELETE FROM {self._table('somatic_markers')}
                    WHERE situation_hash = %s
                """, (situation_hash,))
                return cur.rowcount > 0

    # -----------------------------------------------------------------------
    # KEY-VALUE STORE
    # -----------------------------------------------------------------------

    def kv_get(self, key: str) -> Optional[dict]:
        """Get a value from the key-value store."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT value FROM {self._table('key_value_store')} WHERE key = %s",
                    (key,)
                )
                row = cur.fetchone()
                return row[0] if row else None

    def kv_set(self, key: str, value):
        """Set a value in the key-value store."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('key_value_store')} (key, value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """, (key, psycopg2.extras.Json(value)))

    def kv_set_batch(self, items: dict):
        """Set multiple key-value pairs in a single transaction."""
        if not items:
            return
        with self._conn() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, f"""
                    INSERT INTO {self._table('key_value_store')} (key, value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """, [(k, psycopg2.extras.Json(v)) for k, v in items.items()])

    # -----------------------------------------------------------------------
    # SOCIAL REPLIES
    # -----------------------------------------------------------------------

    def check_replied(self, platform: str, post_id: str) -> bool:
        """Check if we've already replied to a post."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT 1 FROM {self._table('social_replies')}
                    WHERE platform = %s AND post_id = %s
                """, (platform, post_id))
                return cur.fetchone() is not None

    def log_reply(self, platform: str, post_id: str, author: str = None,
                  summary: str = None):
        """Log that we replied to a post."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('social_replies')}
                    (platform, post_id, author, summary)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (platform, post_id) DO NOTHING
                """, (platform, post_id, author, summary))

    # -----------------------------------------------------------------------
    # CONTEXT GRAPHS (5W projections)
    # -----------------------------------------------------------------------

    def upsert_context_graph(self, dimension: str, sub_view: str,
                             edges: dict, hubs: list = None,
                             stats: dict = None) -> None:
        """Upsert a 5W context graph projection."""
        # Compute node count from edges
        nodes = set()
        for key in edges:
            parts = key.split('|')
            if len(parts) == 2:
                nodes.update(parts)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self._table('context_graphs')}
                    (dimension, sub_view, last_rebuilt, edge_count, node_count, hubs, stats, edges)
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)
                    ON CONFLICT (dimension, sub_view)
                    DO UPDATE SET last_rebuilt = NOW(),
                                  edge_count = EXCLUDED.edge_count,
                                  node_count = EXCLUDED.node_count,
                                  hubs = EXCLUDED.hubs,
                                  stats = EXCLUDED.stats,
                                  edges = EXCLUDED.edges
                """, (
                    dimension, sub_view or '',
                    len(edges), len(nodes),
                    hubs or [],
                    psycopg2.extras.Json(stats or {}),
                    psycopg2.extras.Json(edges),
                ))

    def get_context_graph(self, dimension: str, sub_view: str = '') -> Optional[dict]:
        """Get a context graph by dimension and sub_view."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT * FROM {self._table('context_graphs')}
                    WHERE dimension = %s AND sub_view = %s
                """, (dimension, sub_view))
                row = cur.fetchone()
                return dict(row) if row else None

    def get_dimension_degree(self, dimension: str, sub_view: str = '',
                             memory_ids: list = None) -> dict:
        """Get degree counts for memory IDs within a dimensional graph.

        Returns {memory_id: degree} dict. Extracts degrees directly from
        JSONB edges column without loading the full graph into Python.
        """
        row = self.get_context_graph(dimension, sub_view)
        if not row or not row.get('edges'):
            return {}
        edges = row['edges']
        degree = {}
        for key in edges:
            parts = key.split('|')
            if len(parts) != 2:
                continue
            for node in parts:
                if memory_ids is None or node in memory_ids:
                    degree[node] = degree.get(node, 0) + 1
        if memory_ids:
            return {mid: degree.get(mid, 0) for mid in memory_ids}
        return degree

    def get_hub_degrees(self) -> dict:
        """Get degree counts for all memories in L0 co-occurrence graph.

        Returns {memory_id: degree} using SQL aggregation instead of
        loading all edge data. ~50x faster than get_all_edges() + Python loop.
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT memory_id, SUM(cnt)::int AS degree FROM (
                        SELECT id1 AS memory_id, COUNT(*) AS cnt
                        FROM {self._table('edges_v3')} GROUP BY id1
                        UNION ALL
                        SELECT id2 AS memory_id, COUNT(*) AS cnt
                        FROM {self._table('edges_v3')} GROUP BY id2
                    ) sub GROUP BY memory_id
                """)
                return {row[0]: row[1] for row in cur.fetchall()}

    def get_all_edges(self) -> dict:
        """Get all L0 edges as {id1|id2: edge_data} dict for context projection."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"SELECT * FROM {self._table('edges_v3')}")
                edges = {}
                for row in cur.fetchall():
                    r = dict(row)
                    key = f"{r['id1']}|{r['id2']}"
                    # Convert DB row to the format context_manager expects
                    edges[key] = {
                        'belief': float(r.get('belief', 0)),
                        'first_formed': str(r.get('first_formed', '')),
                        'last_updated': str(r.get('last_updated', '')),
                        'platform_context': r.get('platform_context', {}),
                        'activity_context': r.get('activity_context', {}),
                        'topic_context': r.get('topic_context', {}),
                        'contact_context': r.get('contact_context', []),
                    }
                return edges

    # -----------------------------------------------------------------------
    # STATS / HEALTH
    # -----------------------------------------------------------------------

    # -------------------------------------------------------------------
    # SESSION EVENTS — comprehensive event log
    # -------------------------------------------------------------------

    def insert_events_batch(self, events: list) -> int:
        """Batch insert session events. Returns count inserted."""
        if not events:
            return 0
        with self._conn() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, f"""
                    INSERT INTO {self._table('session_events')}
                    (session_id, event_time, sequence_num, event_type,
                     content, content_preview, entities, platform,
                     tool_name, action, transcript_offset,
                     source_block_type, tags, extra)
                    VALUES (%(session_id)s, %(event_time)s, %(sequence_num)s,
                            %(event_type)s, %(content)s, %(content_preview)s,
                            %(entities)s, %(platform)s, %(tool_name)s,
                            %(action)s, %(transcript_offset)s,
                            %(source_block_type)s, %(tags)s, %(extra)s)
                """, events, page_size=100)
                return len(events)

    def query_events(self, filters: dict, limit: int = 50,
                     offset: int = 0) -> list:
        """Query session events with flexible filters."""
        conditions = []
        values = []

        if filters.get('after'):
            conditions.append("event_time >= %s")
            values.append(filters['after'])
        if filters.get('before'):
            conditions.append("event_time < %s")
            values.append(filters['before'])
        if filters.get('session_id'):
            conditions.append("session_id = %s")
            values.append(filters['session_id'])
        if filters.get('event_type'):
            conditions.append("event_type = %s")
            values.append(filters['event_type'])
        if filters.get('platform'):
            conditions.append("platform = %s")
            values.append(filters['platform'])
        if filters.get('action'):
            conditions.append("action = %s")
            values.append(filters['action'])
        if filters.get('person'):
            conditions.append("entities->'agents' ? %s")
            values.append(filters['person'])
        if filters.get('search'):
            conditions.append(
                "to_tsvector('english', content) @@ plainto_tsquery('english', %s)")
            values.append(filters['search'])
        if filters.get('tags'):
            conditions.append("tags && %s")
            values.append(filters['tags'])

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        values.extend([limit, offset])

        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT id, session_id, event_time, sequence_num, event_type,
                           content_preview, entities, platform, tool_name, action,
                           tags, extra
                    FROM {self._table('session_events')}
                    {where}
                    ORDER BY event_time, sequence_num
                    LIMIT %s OFFSET %s
                """, values)
                return [dict(r) for r in cur.fetchall()]

    def count_events(self, session_id: int = None) -> int:
        """Count events, optionally for a specific session."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                if session_id:
                    cur.execute(f"""
                        SELECT COUNT(*) FROM {self._table('session_events')}
                        WHERE session_id = %s
                    """, (session_id,))
                else:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {self._table('session_events')}")
                return cur.fetchone()[0]

    def get_event(self, event_id: int) -> Optional[dict]:
        """Get a single event by ID (with full content)."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT * FROM {self._table('session_events')}
                    WHERE id = %s
                """, (event_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def comprehensive_stats(self) -> dict:
        """Get comprehensive memory system stats (single query)."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                stats = {}

                # Memory counts by type
                cur.execute(f"""
                    SELECT type, COUNT(*) FROM {self._table('memories')}
                    GROUP BY type
                """)
                stats['memories'] = {row[0]: row[1] for row in cur.fetchall()}
                stats['total_memories'] = sum(stats['memories'].values())

                # Edge stats
                stats['edges'] = self.edge_stats()

                # Embedding count
                cur.execute(f"SELECT COUNT(*) FROM {self._table('text_embeddings')}")
                stats['text_embeddings'] = cur.fetchone()[0]

                cur.execute(f"SELECT COUNT(*) FROM {self._table('image_embeddings')}")
                stats['image_embeddings'] = cur.fetchone()[0]

                # Rejection count
                cur.execute(f"SELECT COUNT(*) FROM {self._table('rejections')}")
                stats['rejections'] = cur.fetchone()[0]

                # Lesson count
                cur.execute(f"SELECT COUNT(*) FROM {self._table('lessons')}")
                stats['lessons'] = cur.fetchone()[0]

                # Session count
                cur.execute(f"SELECT COUNT(*) FROM {self._table('sessions')}")
                stats['sessions'] = cur.fetchone()[0]

                # 5W context graphs
                cur.execute(f"""
                    SELECT dimension, sub_view, edge_count, node_count
                    FROM {self._table('context_graphs')}
                """)
                cg = {}
                for r in cur.fetchall():
                    label = f"{r[0]}_{r[1]}" if r[1] else r[0]
                    cg[label] = {'edges': r[2], 'nodes': r[3]}
                stats['context_graphs'] = cg
                stats['total_5w_edges'] = sum(g['edges'] for g in cg.values()) if cg else 0

                return stats


# ---------------------------------------------------------------------------
# Convenience: module-level default instance
# ---------------------------------------------------------------------------

def get_db(schema: str = 'spin') -> MemoryDB:
    """Get a MemoryDB instance for the given schema."""
    return MemoryDB(schema=schema)


# ---------------------------------------------------------------------------
# CLI for quick testing
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    schema = sys.argv[1] if len(sys.argv) > 1 else 'spin'
    db = MemoryDB(schema=schema)

    print(f"Testing connection to schema '{schema}'...")
    try:
        stats = db.comprehensive_stats()
        print(f"  Memories: {stats['total_memories']}")
        print(f"    core: {stats['memories'].get('core', 0)}")
        print(f"    active: {stats['memories'].get('active', 0)}")
        print(f"    archive: {stats['memories'].get('archive', 0)}")
        print(f"  Edges: {stats['edges']['total_edges']}")
        print(f"  Text embeddings: {stats['text_embeddings']}")
        print(f"  Rejections: {stats['rejections']}")
        print(f"  Lessons: {stats['lessons']}")
        print(f"  Sessions: {stats['sessions']}")
        print(f"  5W graphs: {len(stats.get('context_graphs', {}))}")
        print(f"  5W edges: {stats.get('total_5w_edges', 0)}")
        print("\nConnection successful!")
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)
