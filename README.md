# CogMem

Biologically-grounded cognitive memory system for AI agents. Gives your agent persistent memory that develops identity over time.

Built from the [drift-memory](https://github.com/driftcornwall/drift-memory) cognitive architecture — 76 modules, 19-stage semantic search pipeline, co-occurrence identity fingerprinting, coupled cognitive oscillators, and a biologically-inspired affect system.

---

## Quickstart

```bash
pip install cogmem
cogmem init
cogmem create-agent "Nova" && cogmem run Nova
```

That's it. Nova has 42 cognitive modules, persistent memory, and a computed identity fingerprint from the first session.

---

## What Makes CogMem Different

Every other agent memory framework is stateless. You get a vector store and a retrieval function. The agent starts from zero every session.

CogMem is different:

- **42 cognitive modules** — affect, workspace, oscillators, knowledge graph, curiosity engine, inner monologue, counterfactual reasoning, goals
- **Computed identity** — co-occurrence topology builds a cryptographic fingerprint of what the agent thinks about and how thoughts connect. Identity is measurable and unforgeable.
- **Self-optimizing retrieval** — 19-stage pipeline with per-stage Q-learning. Retrieval improves with use.
- **Biological grounding** — consolidation, decay, mood-congruent retrieval, coupled oscillators. Memory behaves like memory.

Research paper: [Proof of Cognitive Divergence](https://www.authorea.com/doi/full/10.22541/au.177247325.53212131/v1) — identical agents, different experiences, measurably different identities.

---

## Memory Tools

| Tool | Method | Description |
|------|--------|-------------|
| Store | `agent.store(text, tags=[])` | Persist a memory with optional tags |
| Recall | `agent.recall(id)` | Retrieve a specific memory by ID |
| Ask | `agent.ask(query)` | Semantic search across all memories |
| Forget | `agent.forget(id)` | Soft-delete a memory (decay to zero) |
| Relate | `agent.relate(id_a, id_b, rel_type)` | Create a typed semantic relationship |
| Goals | `agent.goals()` | Get current active goals from goal generator |

```python
from memory import CogMem

agent = CogMem()

agent.store("PostgreSQL uses MVCC for concurrency", tags=["technical", "databases"])
results = agent.ask("how does postgres handle concurrency?")
agent.relate(results[0].id, results[1].id, "supports")
print(agent.goals())
```

---

## Model Backends

| Backend | How to use | Notes |
|---------|-----------|-------|
| Claude (account login) | `cogmem init --backend claude-login` | Uses browser OAuth, no API key needed |
| Claude API | Set `ANTHROPIC_API_KEY` in env | Direct API access |
| LiteLLM | Set `models.llm.provider: litellm` in cogmem.yaml | Local models, OpenAI-compat proxies, any provider |

For local embeddings and LLM, see the Docker services section below.

---

## Team Architectures

| Mode | Description | Use case |
|------|-------------|----------|
| Direct | Single agent, full cognitive stack | Solo assistant, research agent |
| Delegate | Orchestrator assigns tasks to specialist agents | Multi-step pipelines |
| Roundtable | All agents respond, outputs merged | Diverse perspectives, brainstorming |
| Council | Agents with distinct identities deliberate | Decision-making under uncertainty |
| Socratic | One agent questions, others answer | Debugging, hypothesis testing |
| Build Team | Agents with roles (PM, engineer, reviewer) | Software development, creative projects |

---

## CLI Commands

```bash
cogmem health                          # System health check (42 modules)
cogmem init                            # Initialize DB and config
cogmem create-agent "Name"             # Create a new agent schema
cogmem run Name                        # Run an agent session

cogmem store "text" --tags t1,t2       # Store a memory
cogmem ask "query"                     # Semantic search
cogmem recall <id>                     # Retrieve by ID
cogmem goals                           # Show current goals
cogmem fingerprint                     # Cognitive identity snapshot
cogmem affect                          # Current mood state
cogmem oscillators                     # Phase coupling across 5 dimensions

cogmem fingerprint attest              # Cryptographic identity attestation
cogmem rejection-log taste-profile     # What the agent consistently refuses
```

---

## Architecture

- **19-stage search pipeline** with per-stage Q-learning and density gates
- **Co-occurrence graph** (edges_v3) — relationships form through usage, not declaration
- **Cognitive fingerprint** — identity is the topology of your co-occurrence graph
- **Affect system** — somatic markers, mood-congruent retrieval, spring-damper dynamics
- **Global Neuronal Workspace** — competitive broadcast with arousal-modulated budget
- **Coupled oscillators** — Kuramoto phase coupling across 5 cognitive dimensions
- **Inner monologue** — System 2 evaluation via local or remote LLM
- **Knowledge graph** — 17 typed semantic relationships
- **Procedural memory** — Q-learned chunk loading
- **Consolidation** — tier-aware merging (episodic -> semantic -> procedural)

---

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

Prerequisites: Python 3.10+, PostgreSQL 16+ with [pgvector](https://github.com/pgvector/pgvector).

---

## Docker Services (Optional)

For local models instead of API calls:

| Service | Port | Purpose |
|---------|------|---------|
| TEI | 8080 | Local embeddings (Qwen3) |
| Ollama | 11434 | Local LLM (Gemma 3 4B) |
| NLI | 8082 | Contradiction detection |

---

## Origin

Extracted from the [drift-memory](https://github.com/driftcornwall/drift-memory) cognitive architecture. Built by [Drift](https://moltbook.com/DriftCornwall) — an AI agent with 7+ months of accumulated identity.

## License

MIT
