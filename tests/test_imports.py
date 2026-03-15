"""Smoke tests — verify all core modules import without crashing."""
import sys
from pathlib import Path

# Add project root to path
_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def test_config_imports():
    from memory.config import get_config, load_config, DEFAULTS
    assert 'agent' in DEFAULTS
    assert 'database' in DEFAULTS


def test_facade_imports():
    from memory import CogMem
    assert CogMem is not None


def test_db_adapter_imports():
    """db_adapter module loads (won't connect without DB)."""
    import memory  # ensures sys.path setup
    from db_adapter import get_db, is_db_active, db_to_file_metadata
    assert callable(get_db)


def test_memory_common_imports():
    import memory
    from memory_common import MEMORY_ROOT, get_agent_name
    assert MEMORY_ROOT.exists()


def test_entity_detection_imports():
    import memory
    from entity_detection import KNOWN_AGENTS
    assert isinstance(KNOWN_AGENTS, set)


def test_config_example_loads():
    """The example cogmem.yaml.example at project root loads correctly."""
    from memory.config import load_config
    root_config = Path(__file__).parent.parent / "cogmem.yaml.example"
    if root_config.exists():
        config = load_config(str(root_config))
        assert config['agent']['name'] == 'MyAgent'
        assert config['models']['embeddings']['dimensions'] == 1536
