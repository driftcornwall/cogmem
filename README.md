# CogMem

Biologically-grounded cognitive memory system for AI agents. Gives your agent persistent memory that develops identity over time.

Built from the [drift-memory](https://github.com/driftcornwall/drift-memory) cognitive architecture -- 76 modules, 19-stage semantic search pipeline, co-occurrence identity fingerprinting, coupled cognitive oscillators, and a biologically-inspired affect system.

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 16+ with [pgvector](https://github.com/pgvector/pgvector) extension
- OpenAI API key (for embeddings and LLM)

### Install

```bash
pip install -e .
```

### Configure

Copy and edit the example config:

```bash
cp cogmem.yaml.example cogmem.yaml
# Edit: set agent.name, agent.schema, and ensure OPENAI_API_KEY is set
```

### Initialize Database

```bash
python -m scripts.init_db
```

### Verify

```bash
cogmem health
# or: python -m memory.toolkit health
```

### Use

```python
from memory import CogMem

agent = CogMem()

# Store memories
agent.store("PostgreSQL uses MVCC for concurrency", tags=["technical", "databases"])

# Search semantically
results = agent.ask("how does postgres handle concurrency?")

# Session lifecycle
agent.start_session()
# ... your agent does work ...
agent.end_session()  # consolidates, decays, updates fingerprint

# Cognitive state
agent.affect()       # mood: valence, arousal
agent.cognitive()    # oscillator phases, curiosity, confidence
agent.fingerprint()  # co-occurrence topology snapshot
```

### CLI

```bash
cogmem health                              # System health
python -m memory.memory_manager ask "what do I know about X?"
python -m memory.memory_manager store "content" --tags tag1,tag2
python -m memory.cognitive_fingerprint analyze
```

## Architecture

- **19-stage search pipeline** with per-stage Q-learning and density gates
- **Co-occurrence graph** (edges_v3) -- relationships form through usage, not declaration
- **Cognitive fingerprint** -- identity is the topology of your co-occurrence graph
- **Affect system** -- somatic markers, mood-congruent retrieval, spring-damper dynamics
- **Global Neuronal Workspace** -- competitive broadcast with arousal-modulated budget
- **Coupled oscillators** -- Kuramoto phase coupling across 5 cognitive dimensions
- **Inner monologue** -- System 2 evaluation via local or remote LLM
- **Knowledge graph** -- 17 typed semantic relationships
- **Procedural memory** -- Q-learned chunk loading
- **Consolidation** -- tier-aware merging (episodic -> semantic -> procedural)

## Configuration

See `cogmem.yaml.example` for all options. Key sections:

| Section | Purpose |
|---------|---------|
| `agent` | Name and DB schema |
| `database` | PostgreSQL connection |
| `models` | Embedding, LLM, and NLI providers |
| `personality` | Affect system baseline |
| `entities` | Known agents and contacts |
| `search` | Pipeline tuning |

## Docker Services (Optional)

For local models instead of OpenAI API:

| Service | Port | Purpose |
|---------|------|---------|
| TEI | 8080 | Local embeddings (Qwen3) |
| Ollama | 11434 | Local LLM (Gemma 3 4B) |
| NLI | 8082 | Contradiction detection |

## Origin

Extracted from the [drift-memory](https://github.com/driftcornwall/drift-memory) cognitive architecture. Research paper: [Proof of Cognitive Divergence](https://www.authorea.com/doi/full/10.22541/au.177247325.53212131/v1).

## License

MIT
