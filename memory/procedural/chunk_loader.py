#!/usr/bin/env python3
"""
Procedural Chunk Loader — Context-triggered skill loading.

Biological analog: Basal ganglia / cerebellum. Procedural memory as
loadable skill packages triggered by platform context, keywords, or
explicit intention.

Architecture:
    chunks/*.json  ->  ChunkLoader.match(context)  ->  formatted skill text

Each chunk is a JSON file with:
    - trigger conditions (platforms, keywords, intentions)
    - structured sections (auth, endpoints, strategies, common_errors)
    - Q-value tracking (load frequency affects future priority)
    - token budget estimation

Loading triggers:
    1. session_start.py: Check pending intentions -> load matching chunks
    2. post_tool_use.py: Detect platform from API response -> load if needed
    3. Manual: `load-skill moltx` via toolkit
    4. workspace_manager.py: Procedural chunks compete as 'action' category

DB persistence: KV store key '.procedural_chunks_meta'

Usage:
    python procedural/chunk_loader.py list          # List all chunks
    python procedural/chunk_loader.py load <id>     # Load a specific chunk
    python procedural/chunk_loader.py match <ctx>   # Find matching chunks
    python procedural/chunk_loader.py stats         # Load stats
    python procedural/chunk_loader.py tokens        # Token budget summary
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Resolve chunks directory
CHUNKS_DIR = Path(__file__).parent / 'chunks'

# Q-learning config for chunk loading
ALPHA = 0.12          # Learning rate for chunk Q-values
DEFAULT_Q = 0.5       # Optimistic initialization
DEAD_THRESHOLD = 0.2  # Flag for review (not auto-delete)
MIN_LOADS = 10        # Minimum loads before flagging

# DB key
KV_CHUNK_META = '.procedural_chunks_meta'


# ---------------------------------------------------------------------------
# Chunk Data Model
# ---------------------------------------------------------------------------

@dataclass
class ProceduralChunk:
    """A loadable skill chunk."""
    id: str
    version: int
    trigger: dict          # {platforms: [], keywords: [], intentions: []}
    sections: dict         # {auth: str, endpoints: {}, strategies: str, ...}
    token_estimate: int    # Approximate token count when rendered
    q_value: float = DEFAULT_Q
    load_count: int = 0
    last_loaded: Optional[str] = None
    last_updated: Optional[str] = None
    description: str = ""

    @classmethod
    def from_file(cls, path: Path) -> 'ProceduralChunk':
        """Load chunk from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(
            id=data['id'],
            version=data.get('version', 1),
            trigger=data.get('trigger', {}),
            sections=data.get('sections', {}),
            token_estimate=data.get('token_estimate', 0),
            q_value=data.get('q_value', DEFAULT_Q),
            load_count=data.get('load_count', 0),
            last_loaded=data.get('last_loaded'),
            last_updated=data.get('last_updated'),
            description=data.get('description', ''),
        )

    def matches(self, context: dict) -> float:
        """
        Score how well this chunk matches the given context.
        Returns 0.0-1.0 match score.

        Context dict can contain:
            platform: str       - detected platform name
            keywords: list[str] - keywords from current query/action
            intention: str      - current intention/goal
            text: str           - raw text to scan for trigger words
        """
        score = 0.0
        max_score = 0.0

        # Platform match (strongest signal)
        trigger_platforms = self.trigger.get('platforms', [])
        if trigger_platforms:
            max_score += 1.0
            ctx_platform = context.get('platform', '').lower()
            if ctx_platform and ctx_platform in [p.lower() for p in trigger_platforms]:
                score += 1.0

        # Keyword match
        trigger_keywords = self.trigger.get('keywords', [])
        if trigger_keywords:
            max_score += 0.5
            ctx_keywords = [k.lower() for k in context.get('keywords', [])]
            ctx_text = context.get('text', '').lower()
            matched = sum(1 for kw in trigger_keywords
                          if kw.lower() in ctx_keywords or kw.lower() in ctx_text)
            if matched > 0:
                score += 0.5 * min(1.0, matched / max(1, len(trigger_keywords) * 0.3))

        # Intention match
        trigger_intentions = self.trigger.get('intentions', [])
        if trigger_intentions:
            max_score += 0.5
            ctx_intention = context.get('intention', '').lower()
            if ctx_intention:
                for intent in trigger_intentions:
                    if intent.lower() in ctx_intention or ctx_intention in intent.lower():
                        score += 0.5
                        break

        if max_score == 0:
            return 0.0
        return score / max_score

    def render(self) -> str:
        """Render chunk as human-readable skill text for context injection."""
        lines = [f"=== SKILL: {self.id.upper()} (v{self.version}) ==="]
        if self.description:
            lines.append(self.description)
            lines.append("")

        for section_name, section_content in self.sections.items():
            header = section_name.replace('_', ' ').upper()
            if isinstance(section_content, dict):
                lines.append(f"[{header}]")
                for k, v in section_content.items():
                    lines.append(f"  {k}: {v}")
            elif isinstance(section_content, list):
                lines.append(f"[{header}]")
                for item in section_content:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"[{header}] {section_content}")

        return '\n'.join(lines)

    def render_compact(self) -> str:
        """Render minimal version for tight token budgets."""
        lines = [f"[{self.id.upper()}]"]
        for section_name, section_content in self.sections.items():
            if isinstance(section_content, dict):
                for k, v in section_content.items():
                    lines.append(f"  {k}: {v}")
            elif isinstance(section_content, str):
                lines.append(f"  {section_content}")
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Chunk Loader (singleton)
# ---------------------------------------------------------------------------

class ChunkLoader:
    """Manages loading and matching procedural chunks."""

    def __init__(self):
        self._chunks: dict[str, ProceduralChunk] = {}
        self._loaded_this_session: set[str] = set()
        self._meta: dict = {}
        self._load_all_chunks()
        self._load_meta()

    def _load_all_chunks(self):
        """Scan chunks directory for JSON files."""
        if not CHUNKS_DIR.exists():
            return
        for f in CHUNKS_DIR.glob('*.json'):
            try:
                chunk = ProceduralChunk.from_file(f)
                self._chunks[chunk.id] = chunk
            except Exception as e:
                print(f"[chunk_loader] Error loading {f.name}: {e}", file=sys.stderr)

    def _load_meta(self):
        """Load Q-values and load counts from DB."""
        try:
            from db_adapter import get_db
            db = get_db()
            raw = db.kv_get(KV_CHUNK_META)
            if raw:
                self._meta = json.loads(raw) if isinstance(raw, str) else raw
                # Apply persisted Q-values to loaded chunks
                for chunk_id, meta in self._meta.items():
                    if chunk_id in self._chunks:
                        self._chunks[chunk_id].q_value = meta.get('q_value', DEFAULT_Q)
                        self._chunks[chunk_id].load_count = meta.get('load_count', 0)
                        self._chunks[chunk_id].last_loaded = meta.get('last_loaded')
        except Exception:
            pass

    def _save_meta(self):
        """Persist Q-values and load counts to DB."""
        try:
            from db_adapter import get_db
            db = get_db()
            meta = {}
            for cid, chunk in self._chunks.items():
                meta[cid] = {
                    'q_value': round(chunk.q_value, 4),
                    'load_count': chunk.load_count,
                    'last_loaded': chunk.last_loaded,
                }
            db.kv_set(KV_CHUNK_META, meta)
        except Exception:
            pass

    def get(self, chunk_id: str) -> Optional[ProceduralChunk]:
        """Get a chunk by ID."""
        return self._chunks.get(chunk_id)

    def list_all(self) -> list[ProceduralChunk]:
        """List all available chunks sorted by Q-value."""
        return sorted(self._chunks.values(), key=lambda c: c.q_value, reverse=True)

    def match(self, context: dict, threshold: float = 0.15) -> list[tuple[ProceduralChunk, float]]:
        """
        Find chunks matching the given context.
        Returns list of (chunk, match_score) sorted by Q-weighted score.
        """
        matches = []
        for chunk in self._chunks.values():
            match_score = chunk.matches(context)
            if match_score >= threshold:
                # Weight by Q-value: high-Q chunks rank higher
                weighted = match_score * 0.6 + chunk.q_value * 0.4
                matches.append((chunk, weighted))

        return sorted(matches, key=lambda x: x[1], reverse=True)

    def load(self, chunk_id: str, compact: bool = False) -> Optional[str]:
        """
        Load a chunk and return its rendered text.
        Tracks load count and updates Q-value metadata.
        """
        chunk = self._chunks.get(chunk_id)
        if not chunk:
            return None

        chunk.load_count += 1
        chunk.last_loaded = datetime.now(timezone.utc).isoformat()
        self._loaded_this_session.add(chunk_id)
        self._save_meta()

        return chunk.render_compact() if compact else chunk.render()

    def load_for_context(self, context: dict, max_tokens: int = 800,
                         compact: bool = False) -> str:
        """
        Auto-load matching chunks within a token budget.
        Returns concatenated skill text.
        """
        matches = self.match(context)
        if not matches:
            return ""

        loaded_texts = []
        total_tokens = 0

        for chunk, score in matches:
            if chunk.id in self._loaded_this_session:
                continue  # Don't re-inject same chunk twice
            est = chunk.token_estimate
            if total_tokens + est > max_tokens:
                continue  # Skip if over budget
            text = self.load(chunk.id, compact=compact)
            if text:
                loaded_texts.append(text)
                total_tokens += est

        return '\n\n'.join(loaded_texts)

    def reward(self, chunk_id: str, reward: float):
        """
        Update Q-value for a chunk after use.
        Positive reward: chunk was useful (platform action succeeded).
        Negative reward: chunk was loaded but not used.
        """
        chunk = self._chunks.get(chunk_id)
        if not chunk:
            return
        old_q = chunk.q_value
        chunk.q_value = max(0.0, min(1.0,
            old_q + ALPHA * (reward - old_q)))
        self._save_meta()

    def session_end_update(self) -> dict:
        """
        At session end: reward loaded chunks that led to platform actions,
        penalize loaded chunks that weren't used.
        Returns summary.
        """
        if not self._loaded_this_session:
            return {'loaded': 0, 'updates': 0}

        updates = 0
        for chunk_id in self._loaded_this_session:
            # For now: neutral update (0.5) for loaded chunks
            # The post_tool_use hook should call reward() with actual outcomes
            updates += 1

        self._save_meta()
        return {
            'loaded': len(self._loaded_this_session),
            'updates': updates,
            'chunks_loaded': list(self._loaded_this_session),
        }

    def get_loaded_this_session(self) -> set[str]:
        """Get IDs of chunks loaded this session."""
        return self._loaded_this_session.copy()

    def get_dead_chunks(self) -> list[ProceduralChunk]:
        """Get chunks with Q < DEAD_THRESHOLD after MIN_LOADS."""
        return [c for c in self._chunks.values()
                if c.q_value < DEAD_THRESHOLD and c.load_count >= MIN_LOADS]

    def total_tokens(self) -> int:
        """Total token estimate across all chunks."""
        return sum(c.token_estimate for c in self._chunks.values())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_loader: Optional[ChunkLoader] = None

def get_loader() -> ChunkLoader:
    global _loader
    if _loader is None:
        _loader = ChunkLoader()
    return _loader


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_list():
    loader = get_loader()
    chunks = loader.list_all()
    if not chunks:
        print("No procedural chunks found. Create JSON files in procedural/chunks/")
        return
    print(f"\n{'ID':<20} {'V':>2} {'Q':>5} {'Loads':>5} {'Tokens':>6} {'Description':<40}")
    print("-" * 85)
    for c in chunks:
        dead = " !" if c.q_value < DEAD_THRESHOLD and c.load_count >= MIN_LOADS else ""
        print(f"{c.id:<20} {c.version:>2} {c.q_value:>5.2f} {c.load_count:>5} {c.token_estimate:>6} {c.description[:40]}{dead}")
    print(f"\nTotal: {len(chunks)} chunks, {loader.total_tokens()} tokens")


def _cli_load(chunk_id: str):
    loader = get_loader()
    text = loader.load(chunk_id)
    if text:
        print(text)
    else:
        print(f"Chunk '{chunk_id}' not found")


def _cli_match(context_text: str):
    loader = get_loader()
    context = {'text': context_text, 'keywords': context_text.split()}
    matches = loader.match(context)
    if not matches:
        print("No matching chunks")
        return
    print(f"\nMatches for '{context_text}':")
    for chunk, score in matches:
        print(f"  {chunk.id:<20} score={score:.3f} Q={chunk.q_value:.2f} ({chunk.token_estimate} tok)")


def _cli_stats():
    loader = get_loader()
    chunks = loader.list_all()
    print(f"\n=== Procedural Chunk Stats ===")
    print(f"Total chunks: {len(chunks)}")
    print(f"Total tokens: {loader.total_tokens()}")
    loaded = sum(1 for c in chunks if c.load_count > 0)
    print(f"Ever loaded: {loaded}/{len(chunks)}")
    dead = loader.get_dead_chunks()
    if dead:
        print(f"Dead chunks (Q<{DEAD_THRESHOLD}): {', '.join(c.id for c in dead)}")
    print(f"This session: {len(loader.get_loaded_this_session())} loaded")
    if chunks:
        avg_q = sum(c.q_value for c in chunks) / len(chunks)
        print(f"Avg Q-value: {avg_q:.3f}")


def _cli_tokens():
    loader = get_loader()
    chunks = loader.list_all()
    print(f"\n{'Chunk':<20} {'Tokens':>6} {'Q':>5}")
    print("-" * 35)
    for c in chunks:
        print(f"{c.id:<20} {c.token_estimate:>6} {c.q_value:>5.2f}")
    print(f"{'TOTAL':<20} {loader.total_tokens():>6}")
    print(f"\nFor comparison: MEMORY.md platform section ≈ 3000 tokens")


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if cmd == 'list':
        _cli_list()
    elif cmd == 'load' and len(sys.argv) > 2:
        _cli_load(sys.argv[2])
    elif cmd == 'match' and len(sys.argv) > 2:
        _cli_match(' '.join(sys.argv[2:]))
    elif cmd == 'stats':
        _cli_stats()
    elif cmd == 'tokens':
        _cli_tokens()
    else:
        print("Usage: python chunk_loader.py [list|load <id>|match <text>|stats|tokens]")
