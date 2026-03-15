"""
CogMem — Biologically-grounded cognitive memory for AI agents.

Usage:
    from memory import CogMem
    agent = CogMem("./cogmem.yaml")
    agent.store("Learned something", tags=["technical"])
    results = agent.ask("what do I know about X?")
"""
import sys
from pathlib import Path

# Add this directory to sys.path so sibling imports work
# (e.g., `from db_adapter import get_db` inside modules)
_MEMORY_DIR = str(Path(__file__).parent)
if _MEMORY_DIR not in sys.path:
    sys.path.insert(0, _MEMORY_DIR)


class CogMem:
    """Facade for the cognitive memory system. Thin wrapper over existing modules."""

    def __init__(self, config_path: str | None = None):
        """Initialize CogMem from a config file.

        Args:
            config_path: Path to cogmem.yaml. If None, searches standard locations.
        """
        from config import load_config, _reset_config
        _reset_config()  # Ensure fresh config load
        import config as config_module
        config_module._config = load_config(config_path)
        self._config = config_module._config

    def store(self, content: str, tags: list[str] | None = None, **kwargs) -> str:
        """Store a memory. Returns the memory ID."""
        from memory_store import store_memory
        return store_memory(content, tags=tags or [], **kwargs)

    def ask(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search across memories."""
        from semantic_search import search_memories
        return search_memories(query, limit=top_k)

    def recall(self, memory_id: str) -> dict | None:
        """Recall a specific memory by ID."""
        from db_adapter import get_db
        db = get_db()
        return db.get_memory(memory_id)

    def start_session(self) -> int:
        """Start a new session. Returns session ID."""
        from db_adapter import get_db
        db = get_db()
        return db.start_session()

    def end_session(self):
        """End the current session. Runs consolidation if configured."""
        from db_adapter import get_db
        db = get_db()
        session = db.get_active_session()
        if session:
            db.end_session(session)
        # Run consolidation if hooks enabled
        if self._config.get('hooks', {}).get('session_end', True):
            try:
                from consolidation import find_consolidation_candidates
                candidates = find_consolidation_candidates()
                if candidates:
                    from consolidation import consolidate_memories
                    for c in candidates[:5]:
                        consolidate_memories(c['id1'], c['id2'])
            except Exception:
                pass

    def affect(self) -> dict:
        """Get current affective state (valence, arousal, emotions)."""
        try:
            from affect_system import get_mood
            mood = get_mood()
            if mood:
                return {
                    'valence': mood.valence,
                    'arousal': mood.arousal,
                    'dominant_emotion': getattr(mood, 'dominant_emotion', None),
                }
        except Exception:
            pass
        return {}

    def workspace(self) -> dict:
        """Get workspace status — what's currently broadcast."""
        try:
            from workspace_manager import compete
            return {'available': True}
        except Exception:
            return {'available': False}

    def cognitive(self) -> dict:
        """Get cognitive state (oscillators, dimensions)."""
        try:
            from cognitive_state import get_oscillator_summary
            return get_oscillator_summary()
        except Exception:
            return {}

    def fingerprint(self) -> dict:
        """Generate cognitive fingerprint from co-occurrence topology."""
        from cognitive_fingerprint import generate_full_analysis
        return generate_full_analysis()

    def drift_score(self) -> float:
        """Get identity drift score (0.0 = stable, 1.0 = major change)."""
        from cognitive_fingerprint import generate_full_analysis, compute_drift_score
        analysis = generate_full_analysis()
        result = compute_drift_score(analysis)
        if result and isinstance(result, dict):
            return result.get('drift_score', 0.0)
        return 0.0

    def health(self) -> dict:
        """Run health check and return status dict."""
        try:
            from system_vitals import collect_vitals
            return collect_vitals()
        except Exception as e:
            return {'error': str(e)}
