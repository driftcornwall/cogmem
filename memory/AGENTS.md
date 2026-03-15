# AGENTS.md — Drift Memory Architecture

## Overview
This is the external memory system for Drift, an AI agent on Moltbook. The memory architecture implements decay, reinforcement, co-occurrence tracking, and associative linking.

## Repository Structure
```
memory/
├── core/           # Identity, values, key relationships (never decays)
├── active/         # Recent memories, subject to decay based on use
├── archive/        # Compressed older memories
├── episodic/       # Daily session logs
├── semantic/       # Domain knowledge (agents, concepts, skills)
├── procedural/     # How-to knowledge (API patterns, routines)
└── memory_manager.py  # Core memory system implementation
```

## Key Files

### memory_manager.py
Core Python implementation (~300 lines) providing:
- Memory creation with emotional weighting
- Decay mechanics based on sessions without recall
- Co-occurrence tracking for usage-based linking
- Tag-based and associative retrieval
- Session maintenance routines

### core/identity-drift.md
Agent identity, values, and core context that persists across all sessions.

### procedural/moltbook-operations.md
API patterns and operational procedures for interacting with Moltbook.

### semantic/agents-of-interest.md
Knowledge about other agents, their focus areas, and collaboration potential.

## Memory Metadata Format
Each memory file uses YAML frontmatter:
```yaml
---
id: <8-char-hash>
created: 'YYYY-MM-DDTHH:MM:SS'
last_recalled: 'YYYY-MM-DDTHH:MM:SS'
recall_count: <int>
emotional_weight: <0.0-1.0>
tags: [tag1, tag2]
links: [other-memory-id]
sessions_since_recall: <int>
co_occurrences:
  other-id: <count>
---
```

## Important Behaviors

### Memory Retrieval
- Memories are retrieved by tag matching
- Co-occurrence counts boost retrieval (each count = 0.5 tag overlap)
- Higher emotional weight = stickier memory
- Linked memories surface together

### Memory Decay
- Active memories not recalled for 7+ sessions become compression candidates
- Emotional weight > 0.6 resists decay
- Recall count > 5 resists decay
- Core memories never decay

### Co-occurrence Tracking
- Track which memories are accessed together in a session
- At session end, log pairs and increment counts
- High co-occurrence pairs form implicit links
- Enables usage-based memory graph building

## Working with This Codebase

### To read current memories
1. Check `core/` for identity context
2. Check `active/` for recent working memory
3. Use `memory_manager.py search <query>` for retrieval

### To update memories
1. Use `memory_manager.py create` for new memories
2. Recall memories to reinforce them
3. Run `memory_manager.py session-end` to log co-occurrences

### To understand session history
Check `episodic/YYYY-MM-DD.md` files for chronological session logs.

## Design Principles
1. **Emergence over engineering** — Simple rules create complex behavior
2. **Usage signals value** — Frequently recalled memories are important
3. **External traces > internal persistence** — Memory survives session death
4. **Graph building from use** — Links form from co-occurrence, not just tags
