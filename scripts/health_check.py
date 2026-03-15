#!/usr/bin/env python3
"""
CogMem Health Check — Verifies all services and configuration.

Usage:
    python -m scripts.health_check
    python -m scripts.health_check --config /path/to/cogmem.yaml
"""

import sys
import os
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "memory"))
sys.path.insert(0, str(_ROOT))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CogMem health check")
    parser.add_argument('--config', type=str, default=None)
    args = parser.parse_args()

    from config import load_config
    config = load_config(args.config)

    print("CogMem Health Check")
    print("=" * 40)
    ok = True

    # 1. Database
    db_cfg = config['database']
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=db_cfg['host'], port=db_cfg['port'],
            dbname=db_cfg['name'], user=db_cfg['user'],
            password=db_cfg['password'],
        )
        cur = conn.cursor()
        schema = config['agent']['schema']
        cur.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{schema}'")
        tables = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {schema}.memories")
        memories = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"  Database:    OK ({tables} tables, {memories} memories)")
    except Exception as e:
        print(f"  Database:    FAIL ({e})")
        ok = False

    # 2. Embeddings
    embed_cfg = config['models']['embeddings']
    if embed_cfg['provider'] == 'openai':
        api_key = os.environ.get(embed_cfg.get('api_key_env', 'OPENAI_API_KEY'), '')
        if api_key:
            print(f"  Embeddings:  OK (OpenAI {embed_cfg['model']})")
        else:
            print(f"  Embeddings:  WARN (API key not set)")
    elif embed_cfg['provider'] == 'local':
        try:
            import urllib.request
            endpoint = embed_cfg.get('endpoint', 'http://localhost:8080')
            urllib.request.urlopen(f"{endpoint}/health", timeout=3)
            print(f"  Embeddings:  OK (local {endpoint})")
        except Exception:
            print(f"  Embeddings:  FAIL (local service not reachable)")
            ok = False

    # 3. LLM
    llm_cfg = config['models']['llm']
    if llm_cfg['provider'] == 'openai':
        api_key = os.environ.get(llm_cfg.get('api_key_env', 'OPENAI_API_KEY'), '')
        status = "OK" if api_key else "WARN (API key not set)"
        print(f"  LLM:         {status} (OpenAI {llm_cfg['model']})")
    elif llm_cfg['provider'] == 'ollama':
        try:
            import urllib.request
            endpoint = llm_cfg.get('endpoint', 'http://localhost:11434')
            urllib.request.urlopen(f"{endpoint}/api/tags", timeout=3)
            print(f"  LLM:         OK (Ollama)")
        except Exception:
            print(f"  LLM:         WARN (Ollama not reachable, will fall back)")

    # 4. NLI
    nli_cfg = config['models']['nli']
    if nli_cfg['provider'] == 'skip':
        print(f"  NLI:         SKIP (disabled in config)")
    else:
        try:
            import urllib.request
            endpoint = nli_cfg.get('endpoint', 'http://localhost:8082')
            urllib.request.urlopen(f"{endpoint}/health", timeout=3)
            print(f"  NLI:         OK ({endpoint})")
        except Exception:
            print(f"  NLI:         WARN (not reachable)")

    # 5. Config
    print(f"  Agent:       {config['agent']['name']} (schema: {config['agent']['schema']})")
    print(f"  Embed dims:  {embed_cfg['dimensions']}")

    print("=" * 40)
    print("Status: " + ("ALL OK" if ok else "ISSUES FOUND"))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
