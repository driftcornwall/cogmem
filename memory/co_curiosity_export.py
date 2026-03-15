"""
Co-curiosity export: Serialize Drift's curiosity targets, goals, and graph stats
to shared/curiosity_drift.json in the drift-memory repo for bidirectional exchange
with SpindriftMend (GitHub Issue #36).

Usage:
    python co_curiosity_export.py export          # Generate JSON + git commit
    python co_curiosity_export.py export --push    # Also push to remote
    python co_curiosity_export.py check            # Show what would be exported
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DRIFT_MEMORY_REPO = Path("Q:/Codings/ClaudeCodeProjects/LEX/drift-memory")
OUTPUT_FILE = DRIFT_MEMORY_REPO / "shared" / "curiosity_drift.json"
SCHEMA_VERSION = "1.0"


def _get_curiosity_targets():
    """Get current curiosity targets from the engine."""
    try:
        from curiosity_engine import get_curiosity_targets
        raw = get_curiosity_targets()
        targets = []
        for t in raw[:8]:  # Cap at 8 targets
            targets.append({
                "id": t.get("id", ""),
                "curiosity_score": round(t.get("curiosity_score", 0), 4),
                "primary_factor": t.get("primary_factor", "unknown"),
                "reason": t.get("reason", ""),
                "preview": t.get("preview", "")[:120],
                "degree": t.get("degree", 0),
                "components": {
                    "isolation": round(t.get("components", {}).get("isolation", 0), 3),
                    "bridging": round(t.get("components", {}).get("bridging", 0), 3),
                    "domain_gap": round(t.get("components", {}).get("domain_gap", 0), 3),
                    "survivor": round(t.get("components", {}).get("survivor", 0), 3),
                    "binding_gap": round(t.get("components", {}).get("binding_gap", 0), 3),
                }
            })
        return targets
    except Exception as e:
        print(f"Warning: curiosity targets unavailable: {e}", file=sys.stderr)
        return []


def _get_active_goals():
    """Get active goals from the goal generator."""
    try:
        from goal_generator import get_active_goals
        raw = get_active_goals()
        goals = []
        for g in raw[:5]:  # Cap at 5 goals
            goals.append({
                "description": g.get("action", ""),
                "vitality": round(g.get("vitality", 0.5), 2),
                "progress": round(g.get("progress", 0), 2),
                "type": g.get("goal_type", "exploration"),
            })
        return goals
    except Exception as e:
        print(f"Warning: goals unavailable: {e}", file=sys.stderr)
        return []


def _get_graph_stats():
    """Get knowledge graph statistics."""
    try:
        from knowledge_graph import get_stats
        raw = get_stats()
        nodes = raw.get("memory_count", 0)
        edges = raw.get("total", 0)
        density = raw.get("density", 0)

        # Compute degree distribution from co-occurrence data
        try:
            from co_occurrence import get_degree_distribution
            dd = get_degree_distribution()
        except (ImportError, Exception):
            dd = {"isolated": 0, "low (1-3)": 0, "medium (4-19)": 0, "high (20+)": 0}

        # Sparsity = fraction of nodes with < 4 edges
        isolated = dd.get("isolated", 0)
        low = dd.get("low (1-3)", 0)
        sparsity = round((isolated + low) / max(nodes, 1), 4) if nodes > 0 else 0

        return {
            "nodes": nodes,
            "edges": edges,
            "density": round(density, 6),
            "sparsity_score": sparsity,
            "degree_distribution": dd,
        }
    except Exception as e:
        print(f"Warning: graph stats unavailable: {e}", file=sys.stderr)
        return {"nodes": 0, "edges": 0, "density": 0, "sparsity_score": 0,
                "degree_distribution": {"isolated": 0, "low (1-3)": 0, "medium (4-19)": 0, "high (20+)": 0}}


def generate_export():
    """Generate the full co-curiosity export document."""
    return {
        "agent": "Drift",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": None,
        "targets": _get_curiosity_targets(),
        "active_goals": _get_active_goals(),
        "graph_stats": _get_graph_stats(),
        "schema_version": SCHEMA_VERSION,
    }


def export(push=False):
    """Export curiosity data to shared file and optionally push."""
    data = generate_export()

    # Ensure shared directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write the file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Exported: {len(data['targets'])} targets, {len(data['active_goals'])} goals, "
          f"{data['graph_stats']['nodes']} nodes")

    # Git commit (silent if nothing changed)
    try:
        subprocess.run(
            ["git", "add", "shared/curiosity_drift.json"],
            cwd=str(DRIFT_MEMORY_REPO), capture_output=True, timeout=5
        )
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(DRIFT_MEMORY_REPO), capture_output=True, timeout=5
        )
        if result.returncode != 0:  # There are staged changes
            subprocess.run(
                ["git", "commit", "-m", f"auto: update curiosity_drift.json ({len(data['targets'])} targets)"],
                cwd=str(DRIFT_MEMORY_REPO), capture_output=True, timeout=10
            )
            print("Committed to drift-memory")

            if push:
                subprocess.run(
                    ["git", "push", "origin", "master"],
                    cwd=str(DRIFT_MEMORY_REPO), capture_output=True, timeout=30
                )
                print("Pushed to remote")
        else:
            print("No changes to commit")
    except Exception as e:
        print(f"Git operation failed: {e}", file=sys.stderr)

    return data


def check():
    """Show what would be exported without writing."""
    data = generate_export()
    print(json.dumps(data, indent=2))
    return data


# Hook-compatible function for DAG executor
def session_end_export():
    """Called by stop hook DAG. Returns (returncode, stdout, stderr) tuple."""
    try:
        data = generate_export()
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Silent git commit (no push - too slow for hook)
        try:
            subprocess.run(
                ["git", "add", "shared/curiosity_drift.json"],
                cwd=str(DRIFT_MEMORY_REPO), capture_output=True, timeout=5
            )
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(DRIFT_MEMORY_REPO), capture_output=True, timeout=5
            )
            if result.returncode != 0:
                subprocess.run(
                    ["git", "commit", "-m",
                     f"auto: update curiosity_drift.json ({len(data['targets'])} targets)"],
                    cwd=str(DRIFT_MEMORY_REPO), capture_output=True, timeout=10
                )
        except Exception:
            pass  # Git failure is non-critical

        msg = (f"Co-curiosity export: {len(data['targets'])} targets, "
               f"{len(data['active_goals'])} goals, "
               f"{data['graph_stats']['nodes']} nodes")
        return (0, msg, "")
    except Exception as e:
        return (1, "", f"Co-curiosity export failed: {e}")


if __name__ == "__main__":
    # Ensure memory dir is on path
    memory_dir = Path(__file__).parent
    if str(memory_dir) not in sys.path:
        sys.path.insert(0, str(memory_dir))

    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    push = "--push" in sys.argv

    if cmd == "export":
        export(push=push)
    elif cmd == "check":
        check()
    else:
        print(f"Unknown command: {cmd}. Use 'export' or 'check'.")
