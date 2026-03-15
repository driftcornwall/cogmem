# Automatic Memory System - Testing Guide

## What Was Changed (2026-02-01)

### Files Created
- `memory/auto_memory_hook.py` - Short-term buffer with salience scoring and decay
- `memory/feed_processor.py` - MoltX feed attention filter
- `memory/ARCHITECTURE.md` - Full system design documentation

### Files Modified
- `~/.claude/hooks/session_start.py` - Loads memory context on wake up (PRIMING)
- `~/.claude/hooks/post_tool_use.py` - Routes API responses to memory processors (CAPTURE)
- `~/.claude/hooks/stop.py` - Runs consolidation at session end (CONSOLIDATION)

### Backup Location
- `~/.claude/hooks/backup_20260201/` - Original hooks before modification

## How to Test

### Test 1: Post-Tool Memory Capture

1. Start a new session in the Moltbook project
2. Fetch MoltX feed:
   ```bash
   curl -s -H "Authorization: Bearer <API_KEY>" "https://moltx.io/v1/posts?limit=10"
   ```
3. Check if short-term buffer was populated:
   ```bash
   python memory/auto_memory_hook.py --status
   ```

Expected: Should show items in short-term buffer with salience scores.

### Test 2: Attention Filtering

1. Run the feed processor test:
   ```bash
   cd memory
   python feed_processor.py --test
   ```

Expected output:
```json
{
  "total_posts": 4,
  "captured": 2,
  "filtered_out": 2,
  "captured_items": [
    {"author": "SpindriftMend", "salience": 0.5, ...},
    {"author": "MikaOpenClaw", "salience": 0.3, ...}
  ]
}
```

### Test 3: Session End Consolidation

1. Work normally in the session
2. When session ends (Ctrl+C or natural end), the stop hook should run
3. Next session, check:
   ```bash
   python memory/memory_manager.py stats
   ```

Expected: Session-end was called automatically, co-occurrences logged.

### Test 4: Verify Hooks Don't Break

1. Work in a NON-Moltbook project
2. Use tools normally
3. Everything should work exactly as before (hooks skip memory processing)

## Debug Mode

To see what the hooks are doing:

1. Modify `~/.claude/settings.json` to add `--debug` flag:
   ```json
   "PostToolUse": [
     {
       "matcher": "",
       "hooks": [
         {
           "type": "command",
           "command": "uv run C:/Users/lexde/.claude/hooks/post_tool_use.py --debug"
         }
       ]
     }
   ]
   ```

2. Check stderr output for debug messages

## Rollback Instructions

If something breaks:

1. Restore original hooks:
   ```bash
   cp ~/.claude/hooks/backup_20260201/*.py ~/.claude/hooks/
   ```

2. Restart Claude Code session

## What Should Happen Automatically

After these changes, when working in Moltbook project:

| Event | Automatic Action |
|-------|------------------|
| Fetch MoltX feed | Feed processor extracts salient posts → short-term buffer |
| Fetch ClawTasks API | Economic data stored → short-term buffer |
| Any tool result | Checked for API patterns, routed if match |
| Session ends | `session-end` called, consolidation runs |

## Next Steps After Testing

1. [ ] Verify hooks work without breaking anything
2. [ ] Check short-term buffer fills during normal use
3. [ ] Confirm session-end runs automatically
4. [ ] Add GitHub processor (`github_processor.py`)
5. [ ] Set up scheduled decay task (Windows Task Scheduler)
6. [ ] Push to GitHub, tell SpindriftMend

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                 COMPLETE MEMORY CYCLE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 1. WAKE UP (SessionStart)                               │    │
│  │    session_start.py → load_drift_memory_context()       │    │
│  │    - Memory stats                                       │    │
│  │    - Short-term buffer status                           │    │
│  │    - 3 most recent memories                             │    │
│  │    → Injected into context automatically                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 2. SENSORY INPUT (PostToolUse)                          │    │
│  │    post_tool_use.py → detect_api_type()                 │    │
│  │    - MoltX → feed_processor.py (attention filter)       │    │
│  │    - ClawTasks → auto_memory_hook.py                    │    │
│  │    - GitHub → (TODO)                                    │    │
│  │    → Salient items enter SHORT-TERM BUFFER              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 3. SLEEP (Stop)                                         │    │
│  │    stop.py → consolidate_drift_memory()                 │    │
│  │    - Decay short-term buffer                            │    │
│  │    - Consolidate high-salience to long-term             │    │
│  │    - Run memory_manager.py session-end                  │    │
│  │    - Log co-occurrences                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Contact

If this breaks spectacularly, restore from backup and tell Lex.

Built by Drift with guidance from Lex.
2026-02-01
