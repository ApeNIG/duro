#!/usr/bin/env python3
"""
Skill: duro_bash_ops
Description: Run Duro operations via direct Python, bypassing MCP hooks

This skill provides a way to run common Duro operations without going through
the MCP tool call flow, which can hang due to hookify PreToolUse hook issues.

Usage:
    python duro_bash_ops.py crash-drill         # Run crash drill verification
    python duro_bash_ops.py crash-drill --full  # Full crash drill (100 artifacts)
    python duro_bash_ops.py health              # Health check
    python duro_bash_ops.py reembed [N]         # Reembed N artifacts (default: 10)
    python duro_bash_ops.py prune               # Prune orphan embeddings
    python duro_bash_ops.py status              # Show status
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

# Add duro-mcp to path for imports
DURO_MCP_PATH = Path.home() / "duro-mcp"
sys.path.insert(0, str(DURO_MCP_PATH))

# Memory paths
MEMORY_DIR = Path.home() / ".agent" / "memory"
DB_PATH = MEMORY_DIR / "index.db"


def cmd_crash_drill(full: bool = False):
    """Run the crash drill verification."""
    # Import the existing skill
    skill_path = Path(__file__).parent / "crash_drill_verify.py"
    if skill_path.exists():
        import subprocess
        args = [sys.executable, str(skill_path)]
        if full:
            args.append("--full")
        result = subprocess.run(args, capture_output=False)
        return result.returncode == 0
    else:
        print("[ERROR] crash_drill_verify.py not found")
        return False


def cmd_health():
    """Run health check."""
    try:
        from artifacts import ArtifactStore
        from index import ArtifactIndex

        store = ArtifactStore(MEMORY_DIR, DB_PATH)

        print("=" * 50)
        print("DURO HEALTH CHECK (Bash Bypass)")
        print("=" * 50)
        print(f"Time: {datetime.now().isoformat()}")
        print("-" * 50)

        # SQLite integrity
        with store.index._connect() as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        print(f"[{'OK' if result == 'ok' else 'FAIL'}] SQLite Integrity: {result}")

        # Artifact count
        count = store.index.count()
        print(f"[OK] Artifacts: {count}")

        # Search capabilities
        caps = store.index.get_search_capabilities()
        print(f"[OK] FTS: {caps.get('fts_available', False)}")
        print(f"[OK] Vector: {caps.get('vector_available', False)}")
        print(f"[OK] Embeddings: {caps.get('embedding_count', 0)}")

        # WAL mode
        with store.index._connect() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        print(f"[OK] Journal Mode: {mode}")

        print("=" * 50)
        return True

    except Exception as e:
        print(f"[FAIL] Health check failed: {e}")
        return False


def cmd_reembed(limit: int = 10):
    """Reembed artifacts."""
    try:
        from artifacts import ArtifactStore
        from embeddings import embed_artifact, compute_content_hash, EMBEDDING_CONFIG, is_embedding_available

        if not is_embedding_available():
            print("[ERROR] Embedding not available - fastembed not installed")
            return False

        store = ArtifactStore(MEMORY_DIR, DB_PATH)

        print(f"Reembedding up to {limit} artifacts...")

        # Get facts to embed
        facts = store.query(artifact_type="fact", limit=limit)
        if not facts:
            print("[WARN] No facts found to embed")
            return True

        embedded = 0
        failed = 0
        start = time.time()

        for i, fact in enumerate(facts):
            artifact = store.get_artifact(fact["id"])
            if artifact:
                emb = embed_artifact(artifact)
                if emb:
                    content_hash = compute_content_hash(artifact)
                    model_name = EMBEDDING_CONFIG["model_name"]
                    success = store.index.upsert_embedding(
                        artifact_id=fact["id"],
                        embedding=emb,
                        content_hash=content_hash,
                        model_name=model_name
                    )
                    if success:
                        embedded += 1
                        print(f"  [{i+1}/{len(facts)}] Embedded {fact['id'][:12]}...")
                    else:
                        failed += 1
                else:
                    failed += 1

        elapsed = time.time() - start
        print(f"\nDone: {embedded}/{len(facts)} embedded in {elapsed:.1f}s")
        return embedded > 0

    except Exception as e:
        print(f"[FAIL] Reembed failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def cmd_prune(dry_run: bool = True):
    """Prune orphan embeddings."""
    try:
        from artifacts import ArtifactStore

        store = ArtifactStore(MEMORY_DIR, DB_PATH)

        print("Checking for orphan embeddings...")

        with store.index._connect() as conn:
            # Find orphans
            cursor = conn.execute("""
                SELECT e.artifact_id
                FROM embeddings e
                LEFT JOIN artifacts a ON e.artifact_id = a.id
                WHERE a.id IS NULL
            """)
            orphans = [row[0] for row in cursor.fetchall()]

        if not orphans:
            print("[OK] No orphan embeddings found")
            return True

        print(f"Found {len(orphans)} orphan(s)")

        if dry_run:
            print("[DRY RUN] Would delete:")
            for oid in orphans[:10]:
                print(f"  - {oid}")
            if len(orphans) > 10:
                print(f"  ... and {len(orphans) - 10} more")
        else:
            with store.index._connect() as conn:
                for oid in orphans:
                    conn.execute("DELETE FROM embeddings WHERE artifact_id = ?", (oid,))
                conn.commit()
            print(f"[OK] Deleted {len(orphans)} orphan(s)")

        return True

    except Exception as e:
        print(f"[FAIL] Prune failed: {e}")
        return False


def cmd_status():
    """Show Duro status."""
    try:
        from artifacts import ArtifactStore

        store = ArtifactStore(MEMORY_DIR, DB_PATH)

        print("=" * 50)
        print("DURO STATUS")
        print("=" * 50)

        # Counts by type
        with store.index._connect() as conn:
            cursor = conn.execute("""
                SELECT type, COUNT(*) as cnt
                FROM artifacts
                GROUP BY type
                ORDER BY cnt DESC
            """)
            rows = cursor.fetchall()

        print("\nArtifacts by type:")
        total = 0
        for row in rows:
            print(f"  {row[0]}: {row[1]}")
            total += row[1]
        print(f"  TOTAL: {total}")

        # Recent activity
        with store.index._connect() as conn:
            cursor = conn.execute("""
                SELECT type, title, created_at
                FROM artifacts
                ORDER BY created_at DESC
                LIMIT 5
            """)
            recent = cursor.fetchall()

        print("\nRecent artifacts:")
        for r in recent:
            print(f"  [{r[0]}] {r[1][:40]}...")

        print("=" * 50)
        return True

    except Exception as e:
        print(f"[FAIL] Status failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Duro operations via bash (bypasses MCP hooks)")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # crash-drill
    drill = subparsers.add_parser("crash-drill", help="Run crash drill verification")
    drill.add_argument("--full", action="store_true", help="Full drill (100 artifacts)")

    # health
    subparsers.add_parser("health", help="Health check")

    # reembed
    reembed = subparsers.add_parser("reembed", help="Reembed artifacts")
    reembed.add_argument("limit", type=int, nargs="?", default=10, help="Number to reembed")

    # prune
    prune = subparsers.add_parser("prune", help="Prune orphan embeddings")
    prune.add_argument("--apply", action="store_true", help="Actually delete (default is dry-run)")

    # status
    subparsers.add_parser("status", help="Show status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "crash-drill":
        success = cmd_crash_drill(full=args.full)
    elif args.command == "health":
        success = cmd_health()
    elif args.command == "reembed":
        success = cmd_reembed(limit=args.limit)
    elif args.command == "prune":
        success = cmd_prune(dry_run=not args.apply)
    elif args.command == "status":
        success = cmd_status()
    else:
        parser.print_help()
        return 1

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
