"""
Skill: crash_drill_verify
Description: Run crash drill verification for Duro MCP server resilience testing

This skill automates the verification portion of the crash drill protocol:
1. Run a mini reembed (5 artifacts) to test embedding pipeline
2. Verify repair log was created
3. Run health check
4. Test semantic search
5. Check for stuck repairs
6. Report pass/fail status

Manual steps required (not automated):
- Kill server mid-operation for true crash testing
- Restart server after crash

Usage:
    python crash_drill_verify.py [--full]

    --full: Run full drill with 100 artifacts instead of 5
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

# Config path
CONFIG_PATH = DURO_MCP_PATH / "config.json"

# Memory paths (hardcoded to avoid config loading issues)
MEMORY_DIR = Path.home() / ".agent" / "memory"
DB_PATH = MEMORY_DIR / "index.db"

# Results tracking
RESULTS = {
    "timestamp": None,
    "steps": [],
    "passed": 0,
    "failed": 0,
    "warnings": 0,
    "overall": "UNKNOWN"
}


def log_step(name: str, status: str, message: str = "", details: dict = None):
    """Log a drill step result."""
    step = {
        "name": name,
        "status": status,  # PASS, FAIL, WARN, SKIP
        "message": message,
        "details": details or {}
    }
    RESULTS["steps"].append(step)

    if status == "PASS":
        RESULTS["passed"] += 1
        icon = "[OK]"
    elif status == "FAIL":
        RESULTS["failed"] += 1
        icon = "[FAIL]"
    elif status == "WARN":
        RESULTS["warnings"] += 1
        icon = "[WARN]"
    else:
        icon = "[SKIP]"

    print(f"{icon} {name}: {message}")
    if details:
        for k, v in details.items():
            print(f"     {k}: {v}")


def step_1_check_imports():
    """Verify all required modules can be imported."""
    try:
        from artifacts import ArtifactStore
        from index import ArtifactIndex
        from embeddings import embed_artifact, is_embedding_available, get_embedding_status
        log_step("Import Check", "PASS", "All modules imported successfully")
        return True
    except ImportError as e:
        log_step("Import Check", "FAIL", f"Import failed: {e}")
        return False


def step_2_check_embedding_available():
    """Check if embedding system is available."""
    try:
        from embeddings import is_embedding_available, get_embedding_status

        available = is_embedding_available()
        status = get_embedding_status()

        if available:
            log_step("Embedding Available", "PASS",
                    f"Model: {status.get('model_name', 'unknown')}",
                    {"loaded": status.get("model_loaded", False)})
            return True
        else:
            log_step("Embedding Available", "WARN",
                    "Embedding not available - fastembed not installed")
            return False
    except Exception as e:
        log_step("Embedding Available", "FAIL", str(e))
        return False


def step_3_run_mini_reembed(limit: int = 5):
    """Run a small reembed to test the pipeline."""
    try:
        from artifacts import ArtifactStore
        from embeddings import embed_artifact, compute_content_hash, EMBEDDING_CONFIG

        # Get config
        store = ArtifactStore(MEMORY_DIR, DB_PATH)

        # Get some facts to embed
        facts = store.query(artifact_type="fact", limit=limit)
        if not facts:
            log_step("Mini Reembed", "WARN", "No facts found to embed")
            return True

        embedded = 0
        failed = 0
        start = time.time()

        for fact in facts:
            artifact = store.get_artifact(fact["id"])
            if artifact:
                emb = embed_artifact(artifact)
                if emb:
                    # Store embedding
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
                    else:
                        failed += 1
                else:
                    failed += 1

        elapsed = time.time() - start

        if embedded > 0:
            log_step("Mini Reembed", "PASS",
                    f"Embedded {embedded}/{len(facts)} artifacts in {elapsed:.1f}s",
                    {"embedded": embedded, "failed": failed})
            return True
        else:
            log_step("Mini Reembed", "FAIL", "No artifacts embedded")
            return False

    except Exception as e:
        log_step("Mini Reembed", "FAIL", str(e))
        return False


def step_4_check_repair_log():
    """Verify repair logging is working."""
    try:
        from artifacts import ArtifactStore

        store = ArtifactStore(MEMORY_DIR, DB_PATH)

        # Query repairs table directly
        with store.index._connect() as conn:
            cursor = conn.execute(
                "SELECT id, repair_type, result FROM repairs ORDER BY started_at DESC LIMIT 5"
            )
            repairs = cursor.fetchall()

        if repairs:
            latest = repairs[0]
            log_step("Repair Log", "PASS",
                    f"Found {len(repairs)} repair(s), latest: {latest[1]}",
                    {"latest_id": latest[0], "result": latest[2]})
            return True
        else:
            log_step("Repair Log", "WARN", "No repair logs found (may be first run)")
            return True  # Not a failure, just no history

    except Exception as e:
        log_step("Repair Log", "FAIL", str(e))
        return False


def step_5_check_stuck_repairs():
    """Check for any stuck repairs (indicates previous crash)."""
    try:
        from artifacts import ArtifactStore

        store = ArtifactStore(MEMORY_DIR, DB_PATH)

        # Query for in_progress repairs
        with store.index._connect() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM repairs WHERE result = 'pending'"
            )
            stuck_count = cursor.fetchone()[0]

        if stuck_count == 0:
            log_step("Stuck Repairs", "PASS", "No stuck repairs found")
            return True
        else:
            log_step("Stuck Repairs", "WARN",
                    f"Found {stuck_count} stuck repair(s) - may indicate previous crash",
                    {"stuck_count": stuck_count})
            return True  # Warning, not failure

    except Exception as e:
        log_step("Stuck Repairs", "FAIL", str(e))
        return False


def step_6_health_check():
    """Run basic health check."""
    try:
        from artifacts import ArtifactStore

        store = ArtifactStore(MEMORY_DIR, DB_PATH)

        # Check SQLite integrity
        with store.index._connect() as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]

        if result == "ok":
            log_step("SQLite Integrity", "PASS", "Database integrity OK")
        else:
            log_step("SQLite Integrity", "FAIL", f"Integrity check failed: {result}")
            return False

        # Check artifact count
        count = store.index.count()
        caps = store.index.get_search_capabilities()

        log_step("Index Health", "PASS",
                f"Indexed {count} artifacts",
                {
                    "fts_available": caps.get("fts_available", False),
                    "vec_available": caps.get("vec_available", False),
                    "embedding_count": caps.get("embedding_count", 0)
                })
        return True

    except Exception as e:
        log_step("Health Check", "FAIL", str(e))
        return False


def step_7_semantic_search_test():
    """Test semantic search functionality."""
    try:
        from artifacts import ArtifactStore

        store = ArtifactStore(MEMORY_DIR, DB_PATH)

        # Try a simple search
        results = store.index.hybrid_search("test query", limit=3)

        log_step("Semantic Search", "PASS",
                f"Search returned {len(results)} results",
                {"mode": "hybrid" if results else "degraded"})
        return True

    except Exception as e:
        log_step("Semantic Search", "FAIL", str(e))
        return False


def run_crash_drill(full: bool = False):
    """Run the complete crash drill verification."""
    RESULTS["timestamp"] = datetime.now().isoformat()

    print("=" * 50)
    print("DURO CRASH DRILL VERIFICATION")
    print("=" * 50)
    print(f"Time: {RESULTS['timestamp']}")
    print(f"Mode: {'FULL' if full else 'QUICK'}")
    print("-" * 50)

    # Run all steps
    step_1_check_imports()
    step_2_check_embedding_available()
    step_3_run_mini_reembed(limit=100 if full else 5)
    step_4_check_repair_log()
    step_5_check_stuck_repairs()
    step_6_health_check()
    step_7_semantic_search_test()

    # Summary
    print("-" * 50)
    print("SUMMARY")
    print("-" * 50)

    if RESULTS["failed"] == 0:
        RESULTS["overall"] = "PASS"
        print(f"[PASS] All {RESULTS['passed']} checks passed")
    else:
        RESULTS["overall"] = "FAIL"
        print(f"[FAIL] {RESULTS['failed']} check(s) failed, {RESULTS['passed']} passed")

    if RESULTS["warnings"] > 0:
        print(f"[WARN] {RESULTS['warnings']} warning(s)")

    print("=" * 50)

    # Output JSON for programmatic use
    print("\n--- JSON OUTPUT ---")
    print(json.dumps(RESULTS, indent=2))

    return RESULTS["overall"] == "PASS"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Duro crash drill verification")
    parser.add_argument("--full", action="store_true",
                       help="Run full drill with 100 artifacts")
    args = parser.parse_args()

    success = run_crash_drill(full=args.full)
    sys.exit(0 if success else 1)
