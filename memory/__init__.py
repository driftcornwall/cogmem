"""
Drift Memory System — 83 modules, importable as a package.

When imported from outside (e.g., TEAC SDK wrapper), modules use
sibling imports internally (e.g., `from memory_common import ...`).
We add this directory to sys.path so those imports resolve correctly.
"""
import sys
from pathlib import Path

_MEMORY_DIR = str(Path(__file__).parent)
if _MEMORY_DIR not in sys.path:
    sys.path.insert(0, _MEMORY_DIR)
