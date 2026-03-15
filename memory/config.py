"""
CogMem Configuration — Single YAML config replaces all hardcoded constants.

Search order:
1. Explicit path passed to load_config()
2. COGMEM_CONFIG env var
3. ./cogmem.yaml (working directory)
4. ~/.config/cogmem/cogmem.yaml

Every module reads from get_config() instead of hardcoded constants.
"""

import os
import copy
import yaml
from pathlib import Path

_config = None

DEFAULTS = {
    'agent': {
        'name': 'Agent',
        'schema': 'agent',
    },
    'database': {
        'host': 'localhost',
        'port': 5433,
        'name': 'agent_memory',
        'user': 'agent_admin',
        'password': 'agent_memory_local_dev',
    },
    'models': {
        'embeddings': {
            'provider': 'openai',
            'model': 'text-embedding-3-small',
            'dimensions': 1536,
            'endpoint': None,
            'api_key_env': 'OPENAI_API_KEY',
        },
        'llm': {
            'provider': 'openai',
            'model': 'gpt-4o-mini',
            'endpoint': None,
            'api_key_env': 'OPENAI_API_KEY',
        },
        'nli': {
            'provider': 'skip',
            'endpoint': None,
        },
    },
    'personality': {
        'valence_baseline': 0.1,
        'arousal_reactivity': 0.8,
        'loss_aversion': 2.0,
        'curiosity_weight': 0.7,
    },
    'entities': {
        'known_agents': [],
        'known_contacts': {},
        'known_projects': [],
        'agent_aliases': {},
    },
    'search': {
        'pipeline_stages': 19,
        'workspace_budget': 3000,
        'inner_monologue': True,
    },
    'hooks': {
        'session_start': True,
        'session_end': True,
        'post_tool': True,
    },
    'procedural': {
        'chunk_paths': [],
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflicts."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _find_config_file() -> str | None:
    """Search for config file in standard locations."""
    env_path = os.environ.get('COGMEM_CONFIG')
    if env_path and Path(env_path).exists():
        return env_path

    cwd_path = Path.cwd() / 'cogmem.yaml'
    if cwd_path.exists():
        return str(cwd_path)

    home_path = Path.home() / '.config' / 'cogmem' / 'cogmem.yaml'
    if home_path.exists():
        return str(home_path)

    return None


def load_config(path: str | None = None) -> dict:
    """Load config from YAML file, merged with defaults.

    Args:
        path: Explicit path to config file. If None, searches standard locations.

    Returns:
        Complete config dict with all defaults applied.
    """
    if path is None:
        path = _find_config_file()

    if path and Path(path).exists():
        with open(path, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f) or {}
    else:
        user_config = {}

    return _deep_merge(DEFAULTS, user_config)


def get_config() -> dict:
    """Get the global config singleton. Loads on first call."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def _reset_config():
    """Reset singleton — for testing only."""
    global _config
    _config = None
