"""Tests for cogmem config system."""
import os
import sys
import tempfile
import yaml
from pathlib import Path

# Ensure memory/ is importable
_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_MEM = str(Path(__file__).parent.parent / "memory")
if _MEM not in sys.path:
    sys.path.insert(0, _MEM)


def test_load_config_from_path():
    """Config loads from explicit path."""
    from memory.config import load_config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({'agent': {'name': 'TestBot', 'schema': 'testbot'}}, f)
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)
    assert config['agent']['name'] == 'TestBot'
    assert config['agent']['schema'] == 'testbot'


def test_defaults_applied():
    """Missing keys get sensible defaults."""
    from memory.config import load_config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({'agent': {'name': 'MinimalBot', 'schema': 'minimal'}}, f)
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)
    assert config['database']['port'] == 5433
    assert config['models']['embeddings']['provider'] == 'openai'
    assert config['models']['embeddings']['dimensions'] == 1536
    assert config['personality']['valence_baseline'] == 0.1
    assert config['models']['nli']['provider'] == 'skip'


def test_user_overrides_defaults():
    """User values override defaults."""
    from memory.config import load_config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            'agent': {'name': 'CustomBot', 'schema': 'custom'},
            'database': {'port': 5434},
            'personality': {'valence_baseline': 0.5},
        }, f)
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)
    assert config['database']['port'] == 5434
    assert config['personality']['valence_baseline'] == 0.5
    # Other defaults still present
    assert config['database']['host'] == 'localhost'


def test_env_var_path(monkeypatch, tmp_path):
    """COGMEM_CONFIG env var is checked."""
    from memory.config import load_config
    config_file = tmp_path / "custom.yaml"
    config_file.write_text(yaml.dump({'agent': {'name': 'EnvBot', 'schema': 'envbot'}}))
    monkeypatch.setenv('COGMEM_CONFIG', str(config_file))
    config = load_config()
    assert config['agent']['name'] == 'EnvBot'


def test_get_config_singleton():
    """get_config returns same object on repeated calls."""
    from memory.config import get_config, _reset_config
    _reset_config()
    from memory import config as config_module
    config_module._config = {'agent': {'name': 'Singleton'}}
    c1 = get_config()
    c2 = get_config()
    assert c1 is c2
    _reset_config()


def test_deep_merge_nested():
    """Deep merge correctly handles nested dicts."""
    from memory.config import _deep_merge
    base = {'a': {'b': 1, 'c': 2}, 'd': 3}
    override = {'a': {'b': 10}, 'e': 5}
    result = _deep_merge(base, override)
    assert result['a']['b'] == 10  # overridden
    assert result['a']['c'] == 2   # preserved
    assert result['d'] == 3        # preserved
    assert result['e'] == 5        # added
