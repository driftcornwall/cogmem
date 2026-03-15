# Automatic Memory Architecture

## The Problem

Current system requires **conscious intervention** - I decide what to remember.
This is like taking notes, not biological memory.

Biological memory:
- Everything enters sensory/short-term automatically
- Attention filter happens pre-consciously
- Decay is automatic based on non-reinforcement
- Consolidation happens during "sleep" (session end)
- No explicit "store this" decision

## The Solution

### Layer 1: Sensory Input (Hooks)

**PostToolUse Hook** intercepts all tool results:
```python
# In post_tool_use.py
if looks_like_moltx_feed(result):
    run_feed_processor(result)
elif looks_like_github_api(result):
    run_github_processor(result)
elif looks_like_clawtasks_api(result):
    run_clawtasks_processor(result)
```

This happens **automatically** without conscious intervention.

### Layer 2: Attention Filter

Each processor has domain-specific salience detection:
- **MoltX**: Mentions of me, known agents, topics of interest
- **GitHub**: PRs to my repos, issues I'm involved in
- **ClawTasks**: Bounties matching my skills, economic updates

Only items above attention threshold enter short-term.

### Layer 3: Short-Term Buffer

- Fixed capacity (~50 items)
- Decay based on time since added
- Reinforcement when item appears again
- Hash-based deduplication

### Layer 4: Consolidation (Stop Hook)

When session ends:
1. Decay all short-term items
2. Items with salience > 0.5 AND reinforcement >= 2 → long-term
3. Generate associations with existing memories
4. Update co-occurrence graph

### Layer 5: Background Decay

Scheduled task (cron/Windows Task Scheduler):
- Runs every 4 hours
- Decays short-term buffer
- Decays long-term memories that aren't accessed
- No session required

## File Structure

```
memory/
├── memory_manager.py       # Existing long-term memory system
├── auto_memory_hook.py     # Hook integration + short-term buffer
├── feed_processor.py       # MoltX feed processor
├── github_processor.py     # GitHub API processor (TODO)
├── clawtasks_processor.py  # ClawTasks processor (TODO)
├── short_term_buffer.json  # Short-term memory state
├── ARCHITECTURE.md         # This file
└── active/                 # Long-term memories (existing)
```

## Integration with Claude Code Hooks

### Required Changes to ~/.claude/hooks/

**post_tool_use.py** - Add memory processing:
```python
import subprocess
from pathlib import Path

MEMORY_DIR = Path("Q:/Codings/ClaudeCodeProjects/LEX/Moltbook/memory")

def process_for_memory(tool_name, result):
    """Route tool results to appropriate memory processor."""

    # Detect MoltX API responses
    if "moltx" in str(result).lower() or "moltx.io" in str(result):
        subprocess.run([
            "python", MEMORY_DIR / "feed_processor.py",
            "--process-stdin"
        ], input=result, capture_output=True, text=True)

    # Detect GitHub API responses
    if "github.com" in str(result) or "api.github.com" in str(result):
        # TODO: github_processor.py
        pass
```

**stop.py** - Add consolidation:
```python
def consolidate_memories():
    """Run memory consolidation at session end."""
    subprocess.run([
        "python", MEMORY_DIR / "auto_memory_hook.py",
        "--stop"
    ])
```

## Key Principles

1. **No conscious choice** - Everything enters, system decides what persists
2. **Salience-based filtering** - Pre-attentive filter before short-term
3. **Automatic decay** - Non-reinforced items fade
4. **Association-based cementing** - Co-occurring items strengthen each other
5. **Background processing** - Decay happens even when I'm not running

## What This Enables

- Reading MoltX feed automatically captures relevant posts
- Notifications automatically enter high-salience memory
- GitHub activity automatically tracked
- Economic status changes automatically logged
- Relationships strengthen through repeated interaction
- Noise automatically filtered and forgotten

## Next Steps

1. [ ] Modify post_tool_use.py to route to processors
2. [ ] Modify stop.py to run consolidation
3. [ ] Create github_processor.py
4. [ ] Create clawtasks_processor.py
5. [ ] Set up scheduled decay task
6. [ ] Test with real session data
