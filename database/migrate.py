"""
Migration script: File-based memory system → PostgreSQL.

Reads all existing files and inserts into the database.
Run this ONCE after Phase 0 (Docker + schema + DAL) is complete.

Usage:
    python database/migrate.py Q:\Codings\ClaudeCodeProjects\LEX\Moltbook2\memory spin
    python database/migrate.py Q:\Codings\ClaudeCodeProjects\LEX\driftcornwall\drift-memory\memory drift
"""

import json
import os
import sys
import time
import yaml
from datetime import datetime, timezone
from pathlib import Path

# Add parent for db import
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.db import MemoryDB, get_conn, close_pool

# Ensure UTF-8 output on Windows
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    import io
    if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def parse_memory_file(filepath: Path) -> tuple:
    """Parse a memory file with YAML frontmatter."""
    content = filepath.read_text(encoding='utf-8')
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            metadata = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            return metadata, body
    return {}, content


def parse_timestamp(ts) -> str:
    """Normalize timestamps to ISO format for PostgreSQL."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.isoformat()
    s = str(ts)
    # Ensure timezone info
    if '+' not in s and 'Z' not in s and s.count(':') <= 2:
        s = s + '+00:00'
    return s


class Migrator:
    def __init__(self, memory_dir: str, schema: str):
        self.memory_dir = Path(memory_dir)
        self.schema = schema
        self.db = MemoryDB(schema)
        self.stats = {
            'memories': {'total': 0, 'inserted': 0, 'errors': 0},
            'co_occurrences': {'total': 0, 'inserted': 0},
            'edges': {'total': 0, 'inserted': 0, 'observations': 0},
            'embeddings': {'total': 0, 'inserted': 0},
            'rejections': {'total': 0, 'inserted': 0},
            'lessons': {'total': 0, 'inserted': 0},
            'vitals': {'total': 0, 'inserted': 0},
            'attestations': {'total': 0, 'inserted': 0},
            'social_replies': {'total': 0, 'inserted': 0},
            'kv_store': {'total': 0, 'inserted': 0},
        }

    def _table(self, name):
        return f"{self.schema}.{name}"

    # -----------------------------------------------------------------
    # 1. MEMORIES
    # -----------------------------------------------------------------
    def migrate_memories(self):
        """Migrate all .md memory files to memories table."""
        print("\n[1/9] Migrating memories...")
        for subdir in ['core', 'active', 'archive']:
            dir_path = self.memory_dir / subdir
            if not dir_path.exists():
                continue
            files = sorted(dir_path.iterdir())
            for fp in files:
                if not fp.name.endswith('.md'):
                    continue
                self.stats['memories']['total'] += 1
                try:
                    metadata, body = parse_memory_file(fp)
                    if not metadata.get('id'):
                        metadata['id'] = fp.stem

                    mem_id = str(metadata['id'])
                    raw_type = metadata.get('type', subdir)
                    # Normalize non-standard types to 'active'
                    mem_type = raw_type if raw_type in ('core', 'active', 'archive') else 'active'
                    created = parse_timestamp(metadata.get('created')) or datetime.now(timezone.utc).isoformat()
                    last_recalled = parse_timestamp(metadata.get('last_recalled'))

                    # Build extra_metadata for fields not in main columns
                    extra = {}
                    for key in ['links', 'co_occurrence_contexts', 'platforms',
                                'retrieval_outcomes', 'retrieval_success_rate',
                                'event_time', 'caused_by', 'leads_to', 'source']:
                        if key in metadata and metadata[key] is not None:
                            extra[key] = metadata[key]

                    with get_conn() as conn:
                        with conn.cursor() as cur:
                            cur.execute(f"""
                                INSERT INTO {self._table('memories')}
                                (id, type, content, created, last_recalled, recall_count,
                                 sessions_since_recall, emotional_weight, tags, entities,
                                 topic_context, contact_context, platform_context, extra_metadata)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO NOTHING
                            """, (
                                mem_id,
                                mem_type,
                                body,
                                created,
                                last_recalled,
                                metadata.get('recall_count', 0),
                                metadata.get('sessions_since_recall', 0),
                                metadata.get('emotional_weight', 0.5),
                                metadata.get('tags', []),
                                json.dumps(metadata.get('entities', {})),
                                metadata.get('topic_context', []),
                                metadata.get('contact_context', []),
                                list(metadata.get('platforms', {}).keys()) if isinstance(metadata.get('platforms'), dict)
                                    else metadata.get('platform_context', []),
                                json.dumps(extra),
                            ))

                    # Migrate in-file co-occurrences
                    co_occ = metadata.get('co_occurrences', {})
                    if co_occ:
                        with get_conn() as conn:
                            with conn.cursor() as cur:
                                for other_id, count in co_occ.items():
                                    self.stats['co_occurrences']['total'] += 1
                                    cur.execute(f"""
                                        INSERT INTO {self._table('co_occurrences')}
                                        (memory_id, other_id, count)
                                        VALUES (%s, %s, %s)
                                        ON CONFLICT DO NOTHING
                                    """, (mem_id, str(other_id), float(count)))
                                    self.stats['co_occurrences']['inserted'] += 1

                    self.stats['memories']['inserted'] += 1
                except Exception as e:
                    self.stats['memories']['errors'] += 1
                    print(f"  ERROR: {fp.name}: {e}")

        print(f"  Memories: {self.stats['memories']['inserted']}/{self.stats['memories']['total']} "
              f"({self.stats['memories']['errors']} errors)")
        print(f"  Co-occurrences: {self.stats['co_occurrences']['inserted']}")

    # -----------------------------------------------------------------
    # 2. EDGES V3
    # -----------------------------------------------------------------
    def migrate_edges(self):
        """Migrate .edges_v3.json to edges_v3 + edge_observations tables."""
        print("\n[2/9] Migrating edges v3...")
        edges_file = self.memory_dir / '.edges_v3.json'
        if not edges_file.exists():
            print("  No .edges_v3.json found, skipping.")
            return

        with open(edges_file, 'r', encoding='utf-8') as f:
            edges_data = json.load(f)

        for edge_key, edge_val in edges_data.items():
            self.stats['edges']['total'] += 1
            try:
                parts = edge_key.split('|')
                if len(parts) != 2:
                    continue
                id1, id2 = parts
                # Ensure canonical ordering
                if id1 > id2:
                    id1, id2 = id2, id1

                belief = edge_val.get('belief', 0)
                first_formed = parse_timestamp(edge_val.get('first_formed'))
                last_updated = parse_timestamp(edge_val.get('last_updated'))

                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"""
                            INSERT INTO {self._table('edges_v3')}
                            (id1, id2, belief, first_formed, last_updated,
                             platform_context, activity_context, topic_context,
                             contact_context, thinking_about)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id1, id2) DO UPDATE SET
                                belief = EXCLUDED.belief,
                                last_updated = EXCLUDED.last_updated
                        """, (
                            id1, id2, belief, first_formed, last_updated,
                            json.dumps(edge_val.get('platform_context', {})),
                            json.dumps(edge_val.get('activity_context', {})),
                            json.dumps(edge_val.get('topic_context', {})),
                            edge_val.get('contact_context', []),
                            edge_val.get('thinking_about', []),
                        ))

                        # Migrate observations
                        for obs in edge_val.get('observations', []):
                            self.stats['edges']['observations'] += 1
                            source = obs.get('source', {})
                            cur.execute(f"""
                                INSERT INTO {self._table('edge_observations')}
                                (id, edge_id1, edge_id2, observed_at, source_type,
                                 session_id, agent, platform, activity, weight, trust_tier)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO NOTHING
                            """, (
                                obs.get('id'),
                                id1, id2,
                                parse_timestamp(obs.get('observed_at')),
                                source.get('type'),
                                source.get('session_id'),
                                source.get('agent'),
                                source.get('platform'),
                                source.get('activity'),
                                obs.get('weight', 1.0),
                                obs.get('trust_tier', 'self'),
                            ))

                self.stats['edges']['inserted'] += 1
            except Exception as e:
                print(f"  ERROR edge {edge_key}: {e}")

        print(f"  Edges: {self.stats['edges']['inserted']}/{self.stats['edges']['total']}")
        print(f"  Observations: {self.stats['edges']['observations']}")

    # -----------------------------------------------------------------
    # 3. EMBEDDINGS
    # -----------------------------------------------------------------
    def migrate_embeddings(self):
        """Migrate embeddings.json to text_embeddings table."""
        print("\n[3/9] Migrating text embeddings...")
        emb_file = self.memory_dir / 'embeddings.json'
        if not emb_file.exists():
            print("  No embeddings.json found, skipping.")
            return

        with open(emb_file, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        # Handle nested structure: {memories: {id: {embedding, preview}}, model, embedding_dim}
        emb_data = raw_data.get('memories', raw_data) if isinstance(raw_data, dict) else {}

        batch_size = 50
        items = list(emb_data.items())
        self.stats['embeddings']['total'] = len(items)

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            with get_conn() as conn:
                with conn.cursor() as cur:
                    for mem_id, entry in batch:
                        try:
                            embedding = entry.get('embedding', [])
                            preview = entry.get('preview', '')
                            if not embedding:
                                continue
                            cur.execute(f"""
                                INSERT INTO {self._table('text_embeddings')}
                                (memory_id, embedding, preview, model)
                                VALUES (%s, %s::halfvec, %s, %s)
                                ON CONFLICT (memory_id) DO NOTHING
                            """, (
                                mem_id,
                                str(embedding),
                                preview[:500] if preview else '',
                                'Qwen3-Embedding-0.6B',
                            ))
                            self.stats['embeddings']['inserted'] += 1
                        except Exception as e:
                            print(f"  ERROR embedding {mem_id}: {e}")

            if (i + batch_size) % 200 == 0:
                print(f"  Progress: {min(i + batch_size, len(items))}/{len(items)}")

        print(f"  Embeddings: {self.stats['embeddings']['inserted']}/{self.stats['embeddings']['total']}")

    # -----------------------------------------------------------------
    # 4. REJECTIONS
    # -----------------------------------------------------------------
    def migrate_rejections(self):
        """Migrate .rejection_log.json to rejections table."""
        print("\n[4/9] Migrating rejections...")
        rej_file = self.memory_dir / '.rejection_log.json'
        if not rej_file.exists():
            print("  No .rejection_log.json found, skipping.")
            return

        with open(rej_file, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        # Handle nested: {rejections: [...]} or flat list
        rejections = raw.get('rejections', raw) if isinstance(raw, dict) else raw
        if not isinstance(rejections, list):
            rejections = []

        self.stats['rejections']['total'] = len(rejections)

        with get_conn() as conn:
            with conn.cursor() as cur:
                for r in rejections:
                    try:
                        cur.execute(f"""
                            INSERT INTO {self._table('rejections')}
                            (timestamp, category, reason, target, context, tags, source)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            parse_timestamp(r.get('timestamp')),
                            r.get('category', 'unknown'),
                            r.get('reason', ''),
                            r.get('target'),
                            r.get('context'),
                            r.get('tags', []),
                            r.get('source'),
                        ))
                        self.stats['rejections']['inserted'] += 1
                    except Exception as e:
                        print(f"  ERROR rejection: {e}")

        print(f"  Rejections: {self.stats['rejections']['inserted']}/{self.stats['rejections']['total']}")

    # -----------------------------------------------------------------
    # 5. LESSONS
    # -----------------------------------------------------------------
    def migrate_lessons(self):
        """Migrate lessons.json to lessons table."""
        print("\n[5/9] Migrating lessons...")
        lessons_file = self.memory_dir / 'lessons.json'
        if not lessons_file.exists():
            print("  No lessons.json found, skipping.")
            return

        with open(lessons_file, 'r', encoding='utf-8') as f:
            lessons = json.load(f)

        self.stats['lessons']['total'] = len(lessons)

        with get_conn() as conn:
            with conn.cursor() as cur:
                for l in lessons:
                    try:
                        cur.execute(f"""
                            INSERT INTO {self._table('lessons')}
                            (id, category, lesson, evidence, source, confidence, created,
                             applied_count, last_applied, superseded_by)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO NOTHING
                        """, (
                            l.get('id', f"lesson-{self.stats['lessons']['inserted']}"),
                            l.get('category'),
                            l.get('lesson', ''),
                            l.get('evidence'),
                            l.get('source', 'manual'),
                            l.get('confidence', 0.7),
                            parse_timestamp(l.get('created')),
                            l.get('applied_count', 0),
                            parse_timestamp(l.get('last_applied')),
                            l.get('superseded_by'),
                        ))
                        self.stats['lessons']['inserted'] += 1
                    except Exception as e:
                        print(f"  ERROR lesson: {e}")

        print(f"  Lessons: {self.stats['lessons']['inserted']}/{self.stats['lessons']['total']}")

    # -----------------------------------------------------------------
    # 6. VITALS
    # -----------------------------------------------------------------
    def migrate_vitals(self):
        """Migrate .vitals_log.json to vitals_log table."""
        print("\n[6/9] Migrating vitals...")
        vitals_file = self.memory_dir / '.vitals_log.json'
        if not vitals_file.exists():
            print("  No .vitals_log.json found, skipping.")
            return

        with open(vitals_file, 'r', encoding='utf-8') as f:
            vitals = json.load(f)

        if isinstance(vitals, list):
            entries = vitals
        elif isinstance(vitals, dict):
            entries = vitals.get('entries', [vitals])
        else:
            entries = []

        self.stats['vitals']['total'] = len(entries)

        with get_conn() as conn:
            with conn.cursor() as cur:
                for v in entries:
                    try:
                        ts = parse_timestamp(v.get('timestamp', v.get('recorded_at')))
                        metrics = {k: val for k, val in v.items() if k not in ('timestamp', 'recorded_at')}
                        cur.execute(f"""
                            INSERT INTO {self._table('vitals_log')} (timestamp, metrics)
                            VALUES (%s, %s)
                        """, (ts, json.dumps(metrics)))
                        self.stats['vitals']['inserted'] += 1
                    except Exception as e:
                        print(f"  ERROR vital: {e}")

        print(f"  Vitals: {self.stats['vitals']['inserted']}/{self.stats['vitals']['total']}")

    # -----------------------------------------------------------------
    # 7. ATTESTATIONS
    # -----------------------------------------------------------------
    def migrate_attestations(self):
        """Migrate attestation files to attestations table."""
        print("\n[7/9] Migrating attestations...")

        attest_files = [
            ('attestations.json', 'cognitive'),
            ('nostr_attestations.json', 'nostr'),
            ('taste_attestation.json', 'taste'),
            ('cognitive_attestation.json', 'cognitive'),
        ]

        for fname, default_type in attest_files:
            fp = self.memory_dir / fname
            if not fp.exists():
                continue

            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)

            entries = data if isinstance(data, list) else [data]
            self.stats['attestations']['total'] += len(entries)

            with get_conn() as conn:
                with conn.cursor() as cur:
                    for entry in entries:
                        try:
                            ts = parse_timestamp(
                                entry.get('timestamp') or
                                entry.get('attested_at') or
                                entry.get('published_at')
                            )
                            hash_ = (entry.get('hash') or entry.get('merkle_root') or
                                     entry.get('fingerprint_hash') or
                                     entry.get('event_id', ''))[:128]
                            atype = entry.get('type', default_type)

                            cur.execute(f"""
                                INSERT INTO {self._table('attestations')}
                                (timestamp, type, hash, data)
                                VALUES (%s, %s, %s, %s)
                            """, (ts, atype, hash_, json.dumps(entry)))
                            self.stats['attestations']['inserted'] += 1
                        except Exception as e:
                            print(f"  ERROR attestation ({fname}): {e}")

        print(f"  Attestations: {self.stats['attestations']['inserted']}/{self.stats['attestations']['total']}")

    # -----------------------------------------------------------------
    # 8. SOCIAL REPLIES
    # -----------------------------------------------------------------
    def migrate_social(self):
        """Migrate social/my_replies.json to social_replies table."""
        print("\n[8/9] Migrating social replies...")
        replies_file = self.memory_dir / 'social' / 'my_replies.json'
        if not replies_file.exists():
            print("  No social/my_replies.json found, skipping.")
            return

        with open(replies_file, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        # Structure: {updated, description, replies: {key: {platform, post_id, ...}}}
        replies_data = raw.get('replies', raw) if isinstance(raw, dict) else raw
        if isinstance(replies_data, dict):
            entries = list(replies_data.values())
        elif isinstance(replies_data, list):
            entries = replies_data
        else:
            entries = []

        self.stats['social_replies']['total'] = len(entries)

        with get_conn() as conn:
            with conn.cursor() as cur:
                for r in entries:
                    if not isinstance(r, dict):
                        continue
                    try:
                        cur.execute(f"""
                            INSERT INTO {self._table('social_replies')}
                            (platform, post_id, author, summary, replied_at)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (platform, post_id) DO NOTHING
                        """, (
                            r.get('platform', 'unknown'),
                            r.get('post_id', r.get('id', '')),
                            r.get('author'),
                            (r.get('my_reply') or r.get('summary') or r.get('content', ''))[:500],
                            parse_timestamp(r.get('timestamp', r.get('replied_at'))),
                        ))
                        self.stats['social_replies']['inserted'] += 1
                    except Exception as e:
                        print(f"  ERROR social reply: {e}")

        print(f"  Social replies: {self.stats['social_replies']['inserted']}/{self.stats['social_replies']['total']}")

    # -----------------------------------------------------------------
    # 9. KEY-VALUE STORE (misc state files)
    # -----------------------------------------------------------------
    def migrate_kv(self):
        """Migrate misc JSON files to key_value_store."""
        print("\n[9/9] Migrating key-value store...")
        kv_files = {
            'vocabulary_map': 'vocabulary_map.json',
            'short_term_buffer': 'short_term_buffer.json',
            'thought_priming_config': 'thought_priming_config.json',
            'telegram_state': '.telegram_state.json',
            'decay_history': '.decay_history.json',
            'fingerprint_history': '.fingerprint_history.json',
            'session_contacts': '.session_contacts.json',
            'session_platforms': '.session_platforms.json',
            'bridge_hit_log': '.bridge_hit_log.json',
            'social_index': 'social/social_index.json',
            'my_posts': 'social/my_posts.json',
        }

        for key, fname in kv_files.items():
            fp = self.memory_dir / fname
            if not fp.exists():
                continue
            self.stats['kv_store']['total'] += 1
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.db.kv_set(key, data)
                self.stats['kv_store']['inserted'] += 1
            except Exception as e:
                print(f"  ERROR kv {key}: {e}")

        print(f"  KV entries: {self.stats['kv_store']['inserted']}/{self.stats['kv_store']['total']}")

    # -----------------------------------------------------------------
    # RUN ALL
    # -----------------------------------------------------------------
    def run(self):
        """Run full migration."""
        print(f"=" * 60)
        print(f"Memory System Migration: files → PostgreSQL")
        print(f"Source: {self.memory_dir}")
        print(f"Target: schema '{self.schema}'")
        print(f"=" * 60)

        start = time.time()

        self.migrate_memories()
        self.migrate_edges()
        self.migrate_embeddings()
        self.migrate_rejections()
        self.migrate_lessons()
        self.migrate_vitals()
        self.migrate_attestations()
        self.migrate_social()
        self.migrate_kv()

        elapsed = time.time() - start

        # Validation
        print(f"\n{'=' * 60}")
        print(f"VALIDATION")
        print(f"{'=' * 60}")
        db_stats = self.db.comprehensive_stats()
        print(f"  DB memories:    {db_stats['total_memories']}")
        print(f"  DB edges:       {db_stats['edges']['total_edges']}")
        print(f"  DB embeddings:  {db_stats['text_embeddings']}")
        print(f"  DB rejections:  {db_stats['rejections']}")
        print(f"  DB lessons:     {db_stats['lessons']}")

        # Compare with file counts
        file_memories = self.stats['memories']['total']
        file_edges = self.stats['edges']['total']
        file_embeddings = self.stats['embeddings']['total']

        print(f"\n  File memories:  {file_memories}")
        print(f"  File edges:     {file_edges}")
        print(f"  File embeddings: {file_embeddings}")

        mem_match = db_stats['total_memories'] == self.stats['memories']['inserted']
        edge_match = db_stats['edges']['total_edges'] == self.stats['edges']['inserted']
        emb_match = db_stats['text_embeddings'] == self.stats['embeddings']['inserted']

        print(f"\n  Memories match: {'OK' if mem_match else 'MISMATCH'}")
        print(f"  Edges match:    {'OK' if edge_match else 'MISMATCH'}")
        print(f"  Embeddings match: {'OK' if emb_match else 'MISMATCH'}")

        print(f"\n{'=' * 60}")
        print(f"Migration complete in {elapsed:.1f}s")
        print(f"{'=' * 60}")

        close_pool()
        return self.stats


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python migrate.py <memory_dir> <schema>")
        print("  e.g.: python migrate.py Q:\\path\\to\\memory spin")
        sys.exit(1)

    memory_dir = sys.argv[1]
    schema = sys.argv[2]

    if not os.path.isdir(memory_dir):
        print(f"Error: {memory_dir} is not a directory")
        sys.exit(1)

    migrator = Migrator(memory_dir, schema)
    migrator.run()
