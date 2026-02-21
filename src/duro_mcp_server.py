#!/usr/bin/env python3
"""
Duro MCP Server
A Model Context Protocol server for the Duro local AI agent system.

Exposes tools for:
- Loading/saving persistent memory
- Discovering and running skills
- Checking and applying rules
- Loading project context
"""

import asyncio
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from time_utils import utc_now, utc_now_iso
from typing import Any

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Local imports
from memory import DuroMemory
from skills import DuroSkills
from rules import DuroRules
from artifacts import ArtifactStore
from orchestrator import Orchestrator
from embeddings import (
    embed_artifact, compute_content_hash, EMBEDDING_CONFIG,
    preload_embedding_model, warmup_embedding_model
)
from mcp_logger import log_info, log_warn, log_error

# Autonomy Layer imports
AUTONOMY_LAYER_AVAILABLE = False
AUTONOMY_LAYER_ERROR = None
try:
    from autonomy_state import AutonomyStateStore
    from autonomy_scheduler import AutonomyScheduler, MaintenanceScheduler
    from surfacing import ResultBuffer, QuietModeCalculator, FeedbackTracker
    AUTONOMY_LAYER_AVAILABLE = True
except ImportError as e:
    AUTONOMY_LAYER_ERROR = str(e)

# Agent lib imports (Cartridge Memory System)
# Separate flags so one missing module doesn't break everything
AGENT_LIB_PATH = str(Path.home() / ".agent" / "lib")

# Only insert if not already present (prevents duplicates on hot-reload)
if AGENT_LIB_PATH not in sys.path:
    sys.path.insert(0, AGENT_LIB_PATH)

# Constitution loader
CONSTITUTION_AVAILABLE = False
CONSTITUTION_IMPORT_ERROR = None
try:
    from constitution_loader import (
        load_constitution, render_constitution, list_constitutions, get_constitution_info
    )
    CONSTITUTION_AVAILABLE = True
except ImportError as e:
    CONSTITUTION_IMPORT_ERROR = str(e)

# Context assembler
ASSEMBLER_AVAILABLE = False
ASSEMBLER_IMPORT_ERROR = None
try:
    from context_assembler import (
        assemble_context, format_context_for_injection, TokenBudget, RenderMode
    )
    ASSEMBLER_AVAILABLE = True
except ImportError as e:
    ASSEMBLER_IMPORT_ERROR = str(e)

# Promotion compactor
COMPACTOR_AVAILABLE = False
COMPACTOR_IMPORT_ERROR = None
try:
    from promotion_compactor import (
        get_promotion_report, get_ready_for_promotion, record_observation, PromotionType
    )
    COMPACTOR_AVAILABLE = True
except ImportError as e:
    COMPACTOR_IMPORT_ERROR = str(e)

# Autonomy Ladder (governance)
AUTONOMY_AVAILABLE = False
AUTONOMY_IMPORT_ERROR = None
try:
    from autonomy_ladder import (
        AutonomyLevel, ActionRisk, ReputationStore, AutonomyEnforcer,
        get_reputation_store, get_autonomy_enforcer, check_action, record_outcome,
        classify_action_domain, classify_action_risk
    )
    AUTONOMY_AVAILABLE = True
except ImportError as e:
    AUTONOMY_IMPORT_ERROR = str(e)

# Policy Gate (execution-path enforcement)
POLICY_GATE_AVAILABLE = False
POLICY_GATE_ERROR = None
try:
    from policy_gate import (
        policy_gate, GateDecision, create_scoped_approval_id,
        GATE_BYPASS_TOOLS, get_gate_stats, query_gate_audit,
        compute_args_hash
    )
    POLICY_GATE_AVAILABLE = True
except ImportError as e:
    POLICY_GATE_ERROR = str(e)
    log_warn(f"Policy gate not available: {e}")

# Workspace Guard (path scoping)
WORKSPACE_GUARD_AVAILABLE = False
WORKSPACE_GUARD_ERROR = None
try:
    from workspace_guard import (
        get_workspace_status, add_workspace, reload_workspace_config,
        validate_path, check_workspace_constraints
    )
    WORKSPACE_GUARD_AVAILABLE = True
except ImportError as e:
    WORKSPACE_GUARD_ERROR = str(e)
    log_warn(f"Workspace guard not available: {e}")

# Secrets Guard - Output Scanning (Layer 3 post-execution)
SECRETS_OUTPUT_AVAILABLE = False
SECRETS_OUTPUT_ERROR = None
try:
    from secrets_guard import (
        scan_and_redact_output, should_scan_output,
        create_output_audit_entry, compute_output_hash,
        HIGH_RISK_OUTPUT_TOOLS
    )
    SECRETS_OUTPUT_AVAILABLE = True
except ImportError as e:
    SECRETS_OUTPUT_ERROR = str(e)
    log_warn(f"Secrets output scanning not available: {e}")

# Browser Guard (Layer 4 - browser sandbox)
BROWSER_GUARD_AVAILABLE = False
BROWSER_GUARD_ERROR = None
try:
    from browser_guard import (
        get_browser_status, check_browser_policy, get_sandbox_config,
        check_domain_allowed, normalize_domain
    )
    BROWSER_GUARD_AVAILABLE = True
except ImportError as e:
    BROWSER_GUARD_ERROR = str(e)
    log_warn(f"Browser guard not available: {e}")

# Unified Audit Log (Layer 5 - tamper-evident logging)
UNIFIED_AUDIT_AVAILABLE = False
UNIFIED_AUDIT_ERROR = None
try:
    from audit_log import (
        append_event, build_secrets_event, build_injection_event,
        build_untrusted_content_event, get_audit_stats, verify_log,
        query_log, get_recent_events, EventType, Severity
    )
    UNIFIED_AUDIT_AVAILABLE = True
except ImportError as e:
    UNIFIED_AUDIT_ERROR = str(e)
    log_warn(f"Unified audit not available: {e}")

# Intent Guard (Layer 6 - capability tokens)
INTENT_GUARD_AVAILABLE = False
INTENT_GUARD_ERROR = None
try:
    from intent_guard import (
        on_user_message, get_intent_status, get_current_intent,
        ensure_intent_for_current_user_turn,
        INTENT_REQUIRED_TOOLS, UNTRUSTED_SOURCE_TOOLS,
        mark_untrusted_output, get_session_context
    )
    INTENT_GUARD_AVAILABLE = True
except ImportError as e:
    INTENT_GUARD_ERROR = str(e)
    log_warn(f"Intent guard not available: {e}")

# Prompt Firewall (Layer 6 - injection detection + untrusted content handling)
PROMPT_FIREWALL_AVAILABLE = False
PROMPT_FIREWALL_ERROR = None
try:
    from prompt_firewall import (
        process_untrusted_content, wrap_untrusted, detect_injection,
        get_firewall_status, get_raw_content, ContentVault
    )
    PROMPT_FIREWALL_AVAILABLE = True
except ImportError as e:
    PROMPT_FIREWALL_ERROR = str(e)
    log_warn(f"Prompt firewall not available: {e}")

# Load configuration
CONFIG_PATH = Path(__file__).parent / "config.json"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

# Initialize modules
memory = DuroMemory(CONFIG)
skills = DuroSkills(CONFIG)
rules = DuroRules(CONFIG)

# MCP Reliability: Concurrency and Timeout Configuration
# Prevents event loop blocking and cascading failures
TOOL_CONCURRENCY_LIMIT = 4  # Max concurrent tool executions
TOOL_DEFAULT_TIMEOUT = 30   # Default timeout in seconds

# Per-tool timeout overrides (tool_name -> seconds)
TOOL_TIMEOUTS = {
    "duro_reembed": 120,         # Embedding batch operations
    "duro_semantic_search": 60,  # Vector search with embedding
    "duro_load_context": 45,     # Context loading can be slow
    "duro_proactive_recall": 60, # Also uses embeddings
    "duro_health_check": 30,     # Health checks
    "duro_reindex": 90,          # Reindexing can be slow
}

# Module-level semaphore (created lazily in async context)
_tool_semaphore = None
_heavy_semaphore = None  # Prevents dogpiling heavy operations

# Cooperative cancellation for long-running operations
# Thread-safe flag that can be checked during batch loops
import threading
_cancel_lock = threading.Lock()
_cancel_operations = set()  # Set of operation names to cancel (e.g., "reembed")

def request_cancel(operation: str = "reembed"):
    """Request cancellation of a long-running operation."""
    with _cancel_lock:
        _cancel_operations.add(operation)

def is_cancelled(operation: str = "reembed") -> bool:
    """Check if operation has been cancelled. Thread-safe."""
    with _cancel_lock:
        return operation in _cancel_operations

def clear_cancel(operation: str = "reembed"):
    """Clear cancellation flag after operation ends."""
    with _cancel_lock:
        _cancel_operations.discard(operation)

# Dedicated thread pools for tool execution
# Split into fast (most tools) and heavy (long-running operations)
# This prevents zombie threads from heavy timeouts blocking fast tools
from concurrent.futures import ThreadPoolExecutor

_fast_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="duro_fast")
_heavy_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="duro_heavy")

# Heavy tools that use the isolated executor (can zombie on timeout)
# ONLY truly long-running batch operations belong here
# DO NOT add user-facing tools like semantic_search - fix those separately
HEAVY_TOOLS = {
    "duro_reembed",
    "duro_apply_decay",
    "duro_compress_logs",
    "duro_reindex",
}

import time as _time
_last_heavy_reset = 0.0
_HEAVY_RESET_COOLDOWN = 10  # seconds - prevents executor spam on repeated timeouts

def _reset_heavy_executor():
    """Quarantine and replace heavy executor after timeout.

    On Windows, we can't kill threads, but we can abandon the old executor
    and create a fresh one. The zombie threads will eventually complete
    or be cleaned up on process exit.

    Includes cooldown to prevent executor spam if a tool keeps timing out.
    """
    global _heavy_executor, _last_heavy_reset
    now = _time.time()
    if now - _last_heavy_reset < _HEAVY_RESET_COOLDOWN:
        log_warn("Heavy executor reset suppressed (cooldown)")
        return
    _last_heavy_reset = now

    old = _heavy_executor
    _heavy_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="duro_heavy")
    try:
        # Best-effort shutdown - don't wait for zombies
        old.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass  # Ignore errors during cleanup
    log_info("Heavy executor quarantined and replaced after timeout")

def _get_tool_timeout(tool_name: str) -> int:
    """Get timeout for a specific tool."""
    return TOOL_TIMEOUTS.get(tool_name, TOOL_DEFAULT_TIMEOUT)

# Initialize artifact store (dual-store: files + SQLite index)
MEMORY_DIR = Path(CONFIG["paths"]["memory_dir"])
DB_PATH = MEMORY_DIR / "index.db"  # Single source of truth for SQLite index
artifact_store = ArtifactStore(MEMORY_DIR, DB_PATH)

# Startup: ensure directories exist, seed core skills, and reindex
# This prevents "file exists but not indexed" ghost artifacts
def _startup_ensure_consistency():
    """Ensure artifact directories exist, core skills are seeded, and index is synced."""
    dirs_to_ensure = ["episodes", "evaluations", "skill_stats", "facts", "decisions", "logs"]
    for dir_name in dirs_to_ensure:
        (MEMORY_DIR / dir_name).mkdir(parents=True, exist_ok=True)

    # Seed core skill stats (idempotent - skips if already exists)
    core_skills = [
        ("web_research", "Web Research"),
        ("source_verification", "Source Verification"),
        ("summarization", "Summarization"),
        ("artifact_creation", "Artifact Creation"),
        ("planning", "Planning"),
    ]
    for skill_id, name in core_skills:
        created, _, _ = artifact_store.ensure_skill_stats(skill_id, name)
        # Only log if created (first run)
        if created:
            log_info(f"Seeded skill_stats: {skill_id}")

    # Reindex to ensure SQLite matches files on disk
    success_count, error_count = artifact_store.reindex()
    if error_count > 0:
        log_warn(f"Startup reindex: {success_count} indexed, {error_count} errors")

    # Rebuild FTS to populate semantic text column
    # (Triggers can't call Python, so text column is empty after reindex)
    fts_result = artifact_store.index.rebuild_fts()
    if not fts_result.get("success"):
        log_warn(f"FTS rebuild failed: {fts_result}")

    # Cleanup any repairs that were stuck in_progress (server crash recovery)
    cleaned = artifact_store.index.cleanup_stuck_repairs(max_age_minutes=10)
    if cleaned > 0:
        log_info(f"Cleaned up {cleaned} stuck repair(s) from previous crash")

# Deferred to main() to avoid MCP startup timeout
# _startup_ensure_consistency()


# ========================================
# Autonomy Layer Initialization
# ========================================

# Global autonomy scheduler (initialized lazily in main())
autonomy_scheduler: "AutonomyScheduler" = None


def _get_pending_decisions_callable() -> list:
    """
    Callable for autonomy scheduler to get pending decisions.
    Returns top 5 decisions awaiting review.
    """
    try:
        decisions = artifact_store.list_unreviewed_decisions(
            older_than_days=14,
            exclude_tags=["smoke-test", "auto-outcome", "generated", "test"],
            limit=5
        )
        # Transform for surfacing
        result = []
        for d in decisions:
            result.append({
                "id": d.get("id", ""),
                "decision": d.get("decision", "")[:100],
                "age_days": d.get("age_days", 0),
                "status": d.get("status", "pending"),
            })
        return result
    except Exception as e:
        log_warn(f"Get pending decisions failed: {e}")
        return []


def _get_stale_facts_callable() -> list:
    """
    Callable for autonomy scheduler to get stale facts.
    Returns cached results from last maintenance run.

    Note: Full fact scanning is expensive (500+ get_artifact calls).
    This returns cached results from the maintenance loop.
    """
    try:
        if not AUTONOMY_LAYER_AVAILABLE or autonomy_scheduler is None:
            return []
        # Get cached stale facts from last maintenance run
        cached = autonomy_scheduler.state.get("maintenance.stale_facts_cache", [])
        return cached[:5]
    except Exception:
        return []


def _run_health_check_callable() -> dict:
    """Maintenance callable: run health check."""
    try:
        result = _startup_health_check()
        notable = any(
            c.get("status") in ("error", "warning")
            for c in result.get("checks", {}).values()
        )
        return {
            "checks": result.get("checks", {}),
            "issues": result.get("issues", []),
            "notable": notable,
            "priority": 80 if notable else 30,
        }
    except Exception as e:
        return {"error": str(e), "notable": True, "priority": 90}


def _run_apply_decay_callable() -> dict:
    """Maintenance callable: apply confidence decay to facts."""
    try:
        from decay import calculate_decay, apply_decay_to_store, generate_maintenance_report

        # Get fact IDs from index, then load full artifacts
        # (index.query returns index entries, but generate_maintenance_report needs full artifacts)
        fact_entries = artifact_store.index.query(artifact_type="fact", limit=500)
        facts = []
        for entry in fact_entries:
            artifact = artifact_store.get_artifact(entry.get("id"))
            if artifact:
                facts.append(artifact)

        # Generate maintenance report with full artifacts
        report = generate_maintenance_report(facts, top_n_stale=10)

        # Cache stale facts for surfacing
        stale_cache = []
        for f in report.stale_high_importance[:5]:
            artifact = artifact_store.get_artifact(f.get("id"))
            if artifact:
                data = artifact.get("data", {})
                stale_cache.append({
                    "id": f.get("id"),
                    "claim": data.get("claim", "")[:100],
                    "confidence": data.get("confidence", 0.5),
                    "days_since_reinforced": f.get("days_since_reinforced", 0),
                })

        # Update cache
        if AUTONOMY_LAYER_AVAILABLE and autonomy_scheduler:
            autonomy_scheduler.state.set("maintenance.stale_facts_cache", stale_cache)

        # Apply decay (dry_run=False)
        decay_result = apply_decay_to_store(artifact_store, dry_run=False)

        notable = len(stale_cache) >= 3
        return {
            "total_facts": report.total_facts,
            "pinned_pct": report.pinned_pct,
            "stale_pct": report.stale_pct,
            "decayed_count": decay_result.get("decayed", 0),
            "stale_high_importance_count": len(stale_cache),
            "notable": notable,
            "priority": 50 if notable else 30,
        }
    except Exception as e:
        return {"error": str(e), "notable": True, "priority": 40}


def _run_orphan_cleanup_callable() -> dict:
    """Maintenance callable: prune orphan embeddings."""
    try:
        result = artifact_store.index.prune_orphan_embeddings(max_delete=100)
        notable = result.get("count", 0) > 10
        return {
            "pruned_count": result.get("count", 0),
            "remaining": result.get("remaining", 0),
            "notable": notable,
            "priority": 30,
        }
    except Exception as e:
        return {"error": str(e), "notable": False}


def _init_autonomy_scheduler():
    """Initialize the autonomy scheduler with all dependencies."""
    global autonomy_scheduler

    if not AUTONOMY_LAYER_AVAILABLE:
        log_warn(f"Autonomy layer not available: {AUTONOMY_LAYER_ERROR}")
        return None

    try:
        # State store path
        state_db_path = MEMORY_DIR / "autonomy_state.db"

        # Initialize state store
        state = AutonomyStateStore(str(state_db_path))
        state.ensure_schema()

        # Get reputation store
        reputation_store = None
        if AUTONOMY_AVAILABLE:
            reputation_store = get_reputation_store()

        # Create scheduler
        autonomy_scheduler = AutonomyScheduler(
            state=state,
            artifact_store=artifact_store,
            reputation_store=reputation_store,
            index=artifact_store.index,
            get_pending_decisions=_get_pending_decisions_callable,
            get_stale_facts=_get_stale_facts_callable,
        )

        # Register maintenance tasks
        from datetime import timedelta
        autonomy_scheduler.maintenance.register_task(
            "health_check",
            _run_health_check_callable,
            interval=timedelta(hours=6),
            priority=80,
        )
        autonomy_scheduler.maintenance.register_task(
            "decay",
            _run_apply_decay_callable,
            interval=timedelta(hours=24),
            priority=50,
        )
        autonomy_scheduler.maintenance.register_task(
            "orphan_cleanup",
            _run_orphan_cleanup_callable,
            interval=timedelta(days=3),
            priority=30,
        )

        log_info("Autonomy scheduler initialized")
        return autonomy_scheduler

    except Exception as e:
        log_warn(f"Failed to initialize autonomy scheduler: {e}")
        return None


def _embed_artifact_sync(artifact_id: str) -> bool:
    """
    Synchronously embed an artifact immediately after storage.

    This ensures embeddings are generated inline rather than queued,
    providing immediate vector search capability.

    Args:
        artifact_id: The artifact ID to embed

    Returns:
        True if embedding succeeded, False otherwise
    """
    try:
        # Load the artifact
        artifact = artifact_store.get_artifact(artifact_id)
        if not artifact:
            return False

        # Generate embedding
        embedding = embed_artifact(artifact)
        if not embedding:
            # No embedding needed (empty text or unsupported type)
            return True

        # Store embedding
        content_hash = compute_content_hash(artifact)
        model_name = EMBEDDING_CONFIG["model_name"]

        return artifact_store.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash=content_hash,
            model_name=model_name
        )
    except Exception as e:
        log_warn(f"Sync embedding failed for {artifact_id}: {e}")
        return False


def _startup_health_check() -> dict:
    """
    Run health checks on Duro system components.
    Returns dict with check results for diagnostics.
    """
    checks = {}
    issues = []

    # 1. SQLite integrity check
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA busy_timeout = 5000")
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            checks["sqlite_integrity"] = {
                "status": "ok" if result == "ok" else "error",
                "message": result
            }
            if result != "ok":
                issues.append(f"SQLite integrity check failed: {result}")
    except Exception as e:
        checks["sqlite_integrity"] = {"status": "error", "message": str(e)}
        issues.append(f"SQLite integrity check error: {e}")

    # 2. Index sync check - compare indexed count vs file count
    try:
        indexed_count = artifact_store.index.count()
        file_count = 0
        from schemas import TYPE_DIRECTORIES
        for type_name, dir_name in TYPE_DIRECTORIES.items():
            type_dir = MEMORY_DIR / dir_name
            if type_dir.exists():
                file_count += len(list(type_dir.glob("*.json")))

        drift = abs(indexed_count - file_count)
        sync_ok = drift < 5
        checks["index_sync"] = {
            "status": "ok" if sync_ok else "warning",
            "indexed": indexed_count,
            "files": file_count,
            "drift": drift
        }
        if not sync_ok:
            issues.append(f"Index drift: {drift} (indexed={indexed_count}, files={file_count})")
    except Exception as e:
        checks["index_sync"] = {"status": "error", "message": str(e)}
        issues.append(f"Index sync check error: {e}")

    # 3. Audit chain verification (last 10 entries)
    try:
        audit_result = artifact_store.query_audit_log(limit=10, verify_chain=True)
        chain_valid = audit_result.get("chain_valid")
        if chain_valid is None:
            checks["audit_chain"] = {"status": "ok", "message": "No audit entries (empty chain)"}
        elif chain_valid:
            checks["audit_chain"] = {
                "status": "ok",
                "message": f"Chain valid ({audit_result.get('total', 0)} entries verified)"
            }
        else:
            # Find first broken entry for diagnostics
            chain_details = audit_result.get("chain_details", [])
            first_broken = None
            for detail in chain_details:
                if detail.get("status") != "valid":
                    first_broken = detail
                    break

            checks["audit_chain"] = {
                "status": "error",
                "message": "Chain integrity broken - possible tampering",
                "first_broken_entry": first_broken.get("entry") if first_broken else None,
                "first_broken_timestamp": first_broken.get("timestamp") if first_broken else None,
                "first_broken_reason": first_broken.get("status") if first_broken else None
            }
            issues.append(f"Audit chain integrity broken at entry {first_broken.get('entry') if first_broken else '?'}")
    except Exception as e:
        checks["audit_chain"] = {"status": "error", "message": str(e)}
        issues.append(f"Audit chain check error: {e}")

    # 4. Disk space check
    try:
        total, used, free = shutil.disk_usage(MEMORY_DIR)
        free_gb = free / (1024 ** 3)
        disk_ok = free_gb > 1.0
        checks["disk_space"] = {
            "status": "ok" if disk_ok else "warning",
            "free_gb": round(free_gb, 2),
            "total_gb": round(total / (1024 ** 3), 2)
        }
        if not disk_ok:
            issues.append(f"Low disk space: {round(free_gb, 2)} GB free")
    except Exception as e:
        checks["disk_space"] = {"status": "error", "message": str(e)}
        issues.append(f"Disk space check error: {e}")

    # 5. FTS completeness check
    try:
        fts_stats = artifact_store.index.get_fts_completeness()
        if not fts_stats.get("fts_exists"):
            checks["fts_completeness"] = {
                "status": "warning",
                "message": "FTS table not created",
                "fts_exists": False
            }
            issues.append("FTS table not created - run migration")
        else:
            missing = fts_stats.get("missing_text_count", 0)
            coverage = fts_stats.get("coverage_pct", 100)
            # Warning if >10% missing, error if >50% missing
            if coverage < 50:
                status = "error"
            elif coverage < 90:
                status = "warning"
            else:
                status = "ok"

            checks["fts_completeness"] = {
                "status": status,
                "fts_exists": True,
                "total_fts_rows": fts_stats.get("total_fts_rows", 0),
                "missing_text_count": missing,
                "coverage_pct": coverage
            }
            if missing > 0:
                issues.append(f"FTS has {missing} rows missing semantic text ({coverage}% coverage)")
    except Exception as e:
        checks["fts_completeness"] = {"status": "error", "message": str(e)}
        issues.append(f"FTS completeness check error: {e}")

    # 6. Embedding/vector coverage check
    try:
        emb_stats = artifact_store.index.get_embedding_stats()
        vec_available = emb_stats.get("vec_extension_available", False)
        vec_table = emb_stats.get("vec_table_exists", False)

        if not vec_available:
            checks["embedding_coverage"] = {
                "status": "ok",  # Not an error - graceful degradation
                "message": "sqlite-vec not available - FTS-only mode",
                "vec_extension_available": False,
                "vec_table_exists": False
            }
        elif not vec_table:
            checks["embedding_coverage"] = {
                "status": "warning",
                "message": "sqlite-vec available but vector table not created",
                "vec_extension_available": True,
                "vec_table_exists": False
            }
            issues.append("Vector table not created - run migration")
        else:
            emb_count = emb_stats.get("embeddings_count", 0)
            art_count = emb_stats.get("artifacts_count", 0)
            coverage = emb_stats.get("coverage_pct", 0)

            # Warning if <50% coverage, error if <10%
            if art_count > 0 and coverage < 10:
                status = "warning"
            else:
                status = "ok"

            # Check for orphan embeddings
            orphan_count = artifact_store.index.count_orphan_embeddings()

            checks["embedding_coverage"] = {
                "status": status,
                "vec_extension_available": True,
                "vec_table_exists": True,
                "embeddings_count": emb_count,
                "artifacts_count": art_count,
                "coverage_pct": coverage,
                "embedding_dim": emb_stats.get("embedding_dim"),
                "orphan_embeddings": orphan_count
            }
            if art_count > 0 and coverage < 50:
                issues.append(f"Only {coverage}% of artifacts have embeddings ({emb_count}/{art_count})")
            if orphan_count > 0:
                orphan_ids = artifact_store.index.list_orphan_embeddings(limit=5)
                # Guard against None and cap length
                safe_ids = [oid for oid in orphan_ids if oid][:5]
                orphan_preview = ", ".join(safe_ids) if safe_ids else "(error listing)"
                issues.append(f"{orphan_count} orphan embedding(s): [{orphan_preview}] - run duro_prune_orphans")
    except Exception as e:
        checks["embedding_coverage"] = {"status": "error", "message": str(e)}
        issues.append(f"Embedding coverage check error: {e}")

    # 7. Embedding queue depth with failed count and oldest age
    pending_dir = MEMORY_DIR / "pending_embeddings"
    failed_dir = MEMORY_DIR / "failed_embeddings"
    try:
        pending_count = 0
        oldest_pending_age_mins = 0
        failed_count = 0

        if pending_dir.exists():
            pending_files = list(pending_dir.glob("*.pending"))
            pending_count = len(pending_files)

            # Find oldest pending file age
            if pending_files:
                import os
                now = utc_now().timestamp()
                oldest_mtime = min(os.path.getmtime(f) for f in pending_files)
                oldest_pending_age_mins = int((now - oldest_mtime) / 60)

        if failed_dir.exists():
            failed_count = len(list(failed_dir.glob("*.failed")))

        # Queue is concerning if: >100 pending, or oldest >30 mins, or any failed
        queue_warning = pending_count > 100 or oldest_pending_age_mins > 30 or failed_count > 0
        queue_error = pending_count > 500 or oldest_pending_age_mins > 120

        if queue_error:
            status = "error"
        elif queue_warning:
            status = "warning"
        else:
            status = "ok"

        checks["embedding_queue"] = {
            "status": status,
            "pending": pending_count,
            "failed": failed_count,
            "oldest_pending_age_mins": oldest_pending_age_mins
        }

        if pending_count > 100:
            issues.append(f"Embedding queue backlog: {pending_count} pending")
        if oldest_pending_age_mins > 30:
            issues.append(f"Embedding queue stale: oldest item {oldest_pending_age_mins} mins old")
        if failed_count > 0:
            issues.append(f"Embedding queue has {failed_count} failed items")

    except Exception as e:
        checks["embedding_queue"] = {"status": "error", "message": str(e)}
        issues.append(f"Embedding queue check error: {e}")

    # Overall status
    has_errors = any(c.get("status") == "error" for c in checks.values())
    has_warnings = any(c.get("status") == "warning" for c in checks.values())

    return {
        "timestamp": utc_now_iso(),
        "overall": "error" if has_errors else ("warning" if has_warnings else "ok"),
        "checks": checks,
        "issues": issues
    }


# Run health check at startup and log any issues
_health_result = _startup_health_check()
if _health_result["issues"]:
    log_warn("Startup health check found issues:")
    for issue in _health_result["issues"]:
        log_warn(f"  - {issue}")
else:
    log_info("Startup health check passed")


# Initialize orchestrator
orchestrator = Orchestrator(MEMORY_DIR, rules, skills, artifact_store)

# Create MCP server
server = Server("duro-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Duro tools."""
    return [
        # Memory tools
        Tool(
            name="duro_load_context",
            description="Load full Duro context at session start. Returns soul, core memory, today's memory, and recent memories. Call this at the beginning of every session.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_soul": {
                        "type": "boolean",
                        "description": "Include soul.md personality config",
                        "default": True
                    },
                    "recent_days": {
                        "type": "integer",
                        "description": "Number of days of recent memory to load",
                        "default": 3
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["full", "lean", "minimal"],
                        "default": "full",
                        "description": "Context verbosity: full (all detail), lean (tasks+decisions only), minimal (soul+core only)"
                    }
                }
            }
        ),
        Tool(
            name="duro_save_memory",
            description="Save content to today's memory log. Use this to persist important information, learnings, or session notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The content to save"
                    },
                    "section": {
                        "type": "string",
                        "description": "Section header for the entry",
                        "default": "Session Log"
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="duro_save_learning",
            description="Save a specific learning or insight to memory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "learning": {
                        "type": "string",
                        "description": "The learning or insight"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category (e.g., Technical, Process, User Preference)",
                        "default": "General"
                    }
                },
                "required": ["learning"]
            }
        ),
        Tool(
            name="duro_log_task",
            description="Log a completed task with its outcome.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Description of the task"
                    },
                    "outcome": {
                        "type": "string",
                        "description": "Result or outcome of the task"
                    }
                },
                "required": ["task", "outcome"]
            }
        ),
        Tool(
            name="duro_log_failure",
            description="Log a failure with lesson learned. Failures are valuable for building rules.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "What was attempted"
                    },
                    "error": {
                        "type": "string",
                        "description": "What went wrong"
                    },
                    "lesson": {
                        "type": "string",
                        "description": "What to do differently next time"
                    }
                },
                "required": ["task", "error", "lesson"]
            }
        ),
        Tool(
            name="duro_compress_logs",
            description="Compress old memory logs into summaries. Archives raw logs and creates compact summaries for faster context loading. Run this periodically to keep context size manageable.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_query_archive",
            description="Search or retrieve archived raw memory logs. Use when you need full detail from past sessions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Specific date to retrieve (YYYY-MM-DD format)"
                    },
                    "search": {
                        "type": "string",
                        "description": "Search query to find in archives"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return",
                        "default": 5
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters to return (default 4000). Use null/0 for unlimited.",
                        "default": 4000
                    }
                }
            }
        ),
        Tool(
            name="duro_list_archives",
            description="List all available archived memory logs with their sizes.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        # Skills tools
        Tool(
            name="duro_list_skills",
            description="List all available Duro skills with their metadata.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_find_skills",
            description="Find skills matching keywords. Use this to discover which skill to use for a task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords to search for"
                    }
                },
                "required": ["keywords"]
            }
        ),
        Tool(
            name="duro_run_skill",
            description="Execute a Duro skill by name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name or ID of the skill to run"
                    },
                    "args": {
                        "type": "object",
                        "description": "Arguments to pass to the skill",
                        "default": {}
                    }
                },
                "required": ["skill_name"]
            }
        ),
        Tool(
            name="duro_get_skill_code",
            description="Get the source code of a skill for inspection or modification.",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name or ID of the skill"
                    }
                },
                "required": ["skill_name"]
            }
        ),

        # Rules tools
        Tool(
            name="duro_check_rules",
            description="Check which rules apply to a given task. Call this before starting work to get relevant constraints and guidance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the task to check rules against"
                    }
                },
                "required": ["task_description"]
            }
        ),
        Tool(
            name="duro_list_rules",
            description="List all Duro rules.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        # Project tools
        Tool(
            name="duro_get_project",
            description="Load context for a specific project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    }
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="duro_list_projects",
            description="List all tracked projects.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        # Constitution tools (Cartridge Memory System)
        Tool(
            name="duro_load_constitution",
            description="Load a project constitution for context injection. Constitutions are the 'laws of this project' - design rules, constraints, patterns, and deciding axes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project identifier (e.g., 'msj', 'cinematch')"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["minimal", "compact", "full"],
                        "description": "Rendering mode - minimal (~200 tokens), compact (~800), full (~2000)",
                        "default": "compact"
                    }
                },
                "required": ["project_id"]
            }
        ),
        Tool(
            name="duro_list_constitutions",
            description="List all available project constitutions with metadata. Also shows loader status and debug info.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_assemble_context",
            description="Assemble context for a task using the Cartridge Memory System. Returns constitution + relevant skills within token budget.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "What the user wants to do (used for skill matching)"
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Optional project ID for constitution loading"
                    },
                    "constitution_mode": {
                        "type": "string",
                        "enum": ["minimal", "compact", "full"],
                        "default": "compact"
                    },
                    "skill_mode": {
                        "type": "string",
                        "enum": ["minimal", "compact", "full"],
                        "default": "compact"
                    },
                    "budget_skills": {
                        "type": "integer",
                        "default": 30000,
                        "description": "Max tokens for skills"
                    }
                },
                "required": ["task_description"]
            }
        ),
        Tool(
            name="duro_promotion_report",
            description="Get report on pending knowledge promotions. Shows candidates ready for promotion to laws/patterns/skills.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Optional: filter to specific project"
                    }
                }
            }
        ),

        # System tools
        Tool(
            name="duro_status",
            description="Get Duro system status and statistics.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_health_check",
            description="Run health diagnostics on Duro system. Checks: SQLite integrity, index sync, audit chain, disk space, embedding queue. Use this to diagnose issues before they become problems.",
            inputSchema={
                "type": "object",
                "properties": {
                    "verbose": {
                        "type": "boolean",
                        "description": "Include detailed check information",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="duro_heartbeat",
            description="Diagnostic heartbeat to test MCP server responsiveness. Use this to verify the event loop is not blocked. Returns timestamp and latency metrics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "echo": {
                        "type": "string",
                        "description": "Optional string to echo back (proves roundtrip)",
                        "default": ""
                    }
                }
            }
        ),
        Tool(
            name="duro_cancel_operation",
            description="Cancel a long-running background operation (like reembed). Uses cooperative cancellation - the operation will stop at its next checkpoint (every 25 items). Returns immediately; check operation status separately.",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Operation to cancel: 'reembed', 'decay', or 'all'",
                        "enum": ["reembed", "decay", "compress", "all"],
                        "default": "reembed"
                    }
                }
            }
        ),
        Tool(
            name="duro_browser_status",
            description="Get browser sandbox status. Shows sandbox mode, domain restrictions, active profiles, and recent sessions. Use this to understand browser security constraints.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_browser_check_url",
            description="Check if a URL is allowed by browser sandbox policy. Returns whether the domain is allowed and the reason.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to check"
                    }
                },
                "required": ["url"]
            }
        ),

        # Autonomy Layer Tools
        Tool(
            name="duro_autonomy_insights",
            description="Get queued autonomous insights (pending decisions, stale facts, health alerts). Use this to explicitly pull insights that weren't surfaced in load_context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_items": {
                        "type": "integer",
                        "description": "Maximum items to return (default 3)",
                        "default": 3
                    },
                    "types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by event types (pending_decision, stale_fact, maintenance_health_check, etc.)"
                    },
                    "include_debug": {
                        "type": "boolean",
                        "description": "Include debug info (buffer state, quiet mode factors)",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="duro_quiet_mode",
            description="Control quiet mode for surfacing. When enabled, only critical insights are surfaced. Use to reduce interruptions during focused work.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["status", "enable", "disable"],
                        "description": "Action to perform",
                        "default": "status"
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "How long to enable quiet mode (default 60)",
                        "default": 60
                    }
                }
            }
        ),
        Tool(
            name="duro_surfacing_feedback",
            description="Provide feedback on a surfaced insight. Helps tune what gets surfaced in the future.",
            inputSchema={
                "type": "object",
                "properties": {
                    "surfacing_id": {
                        "type": "string",
                        "description": "The ID of the surfaced insight"
                    },
                    "feedback": {
                        "type": "string",
                        "enum": ["helpful", "neutral", "distracting", "wrong"],
                        "description": "Feedback on the surfacing"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes explaining the feedback"
                    }
                },
                "required": ["surfacing_id", "feedback"]
            }
        ),
        Tool(
            name="duro_run_maintenance",
            description="Manually trigger a maintenance task. Use this to force immediate execution of decay, health check, or orphan cleanup.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "enum": ["decay", "health_check", "orphan_cleanup"],
                        "description": "The maintenance task to run"
                    }
                },
                "required": ["task"]
            }
        ),

        # Audit tools (Layer 5)
        Tool(
            name="duro_audit_query",
            description="Query the unified security audit log. Returns security events with filters. Use this to investigate security decisions, violations, and redaction events.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum events to return",
                        "default": 50
                    },
                    "event_type": {
                        "type": "string",
                        "description": "Filter by event type (e.g., 'gate.decision', 'secrets.blocked', 'browser.domain_blocked')"
                    },
                    "tool": {
                        "type": "string",
                        "description": "Filter by tool name"
                    },
                    "decision": {
                        "type": "string",
                        "description": "Filter by decision (ALLOW, DENY, NEED_APPROVAL)"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["info", "warn", "high", "critical"],
                        "description": "Filter by severity level"
                    },
                    "since": {
                        "type": "string",
                        "description": "Only return events after this ISO timestamp"
                    },
                    "include_archives": {
                        "type": "boolean",
                        "description": "Include archived log files",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="duro_audit_verify",
            description="Verify the integrity of the security audit log. Checks hash chain continuity and optional HMAC signatures. Use this to detect tampering.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_audit_stats",
            description="Get statistics about the security audit log. Shows event counts by type, severity, and decision.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        # Layer 6: Intent Guard & Prompt Firewall
        Tool(
            name="duro_intent_status",
            description="Get current intent guard status. Shows valid intent tokens, session context, and untrusted content state. Use for debugging security decisions.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_firewall_status",
            description="Get prompt firewall status. Shows detection stats, vault contents, and sanitization metrics.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_vault_get",
            description="Retrieve raw (unsanitized) content from the Content Vault by vault ID. Requires approval for security. Use when you need to see original untrusted content that was sanitized.",
            inputSchema={
                "type": "object",
                "properties": {
                    "vault_id": {
                        "type": "string",
                        "description": "The vault ID of the stored raw content"
                    }
                },
                "required": ["vault_id"]
            }
        ),
        Tool(
            name="duro_layer6_status",
            description="Get combined Layer 6 security status (intent guard + prompt firewall). Quick overview of prompt injection defenses.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        # Temporal tools (Phase 2)
        Tool(
            name="duro_supersede_fact",
            description="Mark an old fact as superseded by a new fact. Updates the old fact with valid_until and superseded_by. Use when information becomes outdated.",
            inputSchema={
                "type": "object",
                "properties": {
                    "old_fact_id": {
                        "type": "string",
                        "description": "The fact ID being superseded"
                    },
                    "new_fact_id": {
                        "type": "string",
                        "description": "The fact ID that replaces it"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional explanation for the supersession"
                    }
                },
                "required": ["old_fact_id", "new_fact_id"]
            }
        ),
        Tool(
            name="duro_get_related",
            description="Get artifacts related to a given artifact. Returns both explicit relations (supersedes, references) and optionally semantic neighbors.",
            inputSchema={
                "type": "object",
                "properties": {
                    "artifact_id": {
                        "type": "string",
                        "description": "The artifact to find relations for"
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Filter by relation type (e.g., 'supersedes', 'references')"
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["outgoing", "incoming", "both"],
                        "description": "Direction of relations to include",
                        "default": "both"
                    }
                },
                "required": ["artifact_id"]
            }
        ),

        # Auto-capture & Proactive recall tools (Phase 3)
        Tool(
            name="duro_proactive_recall",
            description="Proactively recall relevant memories for current task context. Uses hot path classification + hybrid search to surface memories you might need. Call this at the start of complex tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "Current task or conversation context to find relevant memories for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum memories to return",
                        "default": 10
                    },
                    "include_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter to specific artifact types (e.g., ['fact', 'decision'])"
                    },
                    "force": {
                        "type": "boolean",
                        "description": "If true, always search even if hot path classifier says no",
                        "default": False
                    }
                },
                "required": ["context"]
            }
        ),
        Tool(
            name="duro_extract_learnings",
            description="Auto-extract learnings, facts, and decisions from conversation text. Useful for capturing insights at session end or from tool outputs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Conversation or text to extract learnings from"
                    },
                    "auto_save": {
                        "type": "boolean",
                        "description": "If true, automatically save extracted items as artifacts",
                        "default": False
                    }
                },
                "required": ["text"]
            }
        ),

        # Decay & Maintenance tools (Phase 4)
        Tool(
            name="duro_apply_decay",
            description="Apply time-based confidence decay to unreinforced facts. Pinned facts are never decayed. Run with dry_run=true first to preview changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, calculate decay but don't modify facts",
                        "default": True
                    },
                    "min_importance": {
                        "type": "number",
                        "description": "Only decay facts with importance >= this value",
                        "default": 0
                    },
                    "include_stale_report": {
                        "type": "boolean",
                        "description": "Include list of stale high-importance facts",
                        "default": True
                    }
                }
            }
        ),
        Tool(
            name="duro_reembed",
            description="Re-queue artifacts for embedding. Use after model upgrade, schema change, or to fix bad embeddings.",
            inputSchema={
                "type": "object",
                "properties": {
                    "artifact_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific artifact IDs to re-embed (if not specified, uses filters)"
                    },
                    "artifact_type": {
                        "type": "string",
                        "description": "Re-embed all artifacts of this type"
                    },
                    "all": {
                        "type": "boolean",
                        "description": "Re-embed ALL artifacts (use with caution)",
                        "default": False
                    },
                    "missing_only": {
                        "type": "boolean",
                        "description": "Only embed artifacts that are missing embeddings",
                        "default": False
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max artifacts to process (for chunking large batches)",
                        "default": 100
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Max seconds before stopping with partial result",
                        "default": 120
                    }
                }
            }
        ),
        Tool(
            name="duro_prune_orphans",
            description="Delete orphan embeddings (embeddings for artifacts that no longer exist). Logs as a repair for audit trail. Use max_delete for batched cleanup of large orphan counts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, count orphans without deleting",
                        "default": False
                    },
                    "max_delete": {
                        "type": "integer",
                        "description": "Maximum orphans to delete (default: unlimited). Use for batched cleanup."
                    }
                }
            }
        ),
        Tool(
            name="duro_maintenance_report",
            description="Generate a maintenance report for memory health. Shows: total facts, % pinned, % stale, top stale high-importance facts, embedding/FTS coverage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_stale_list": {
                        "type": "boolean",
                        "description": "Include list of top stale high-importance facts",
                        "default": True
                    },
                    "top_n_stale": {
                        "type": "integer",
                        "description": "Number of stale facts to list",
                        "default": 10
                    }
                }
            }
        ),
        Tool(
            name="duro_reinforce_fact",
            description="Reinforce a fact - mark it as recently used/confirmed. Resets decay clock and increments reinforcement count.",
            inputSchema={
                "type": "object",
                "properties": {
                    "fact_id": {
                        "type": "string",
                        "description": "The fact ID to reinforce"
                    }
                },
                "required": ["fact_id"]
            }
        ),

        # Artifact tools (structured memory)
        Tool(
            name="duro_store_fact",
            description="Store a fact with source attribution. Facts are claims with evidence. High confidence (>=0.8) requires source_urls and evidence_type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "claim": {
                        "type": "string",
                        "description": "The factual claim being recorded"
                    },
                    "source_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "URLs supporting this fact"
                    },
                    "snippet": {
                        "type": "string",
                        "description": "Relevant excerpt or context"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score 0-1",
                        "default": 0.5
                    },
                    "evidence_type": {
                        "type": "string",
                        "enum": ["quote", "paraphrase", "inference", "none"],
                        "description": "How evidence supports the claim: quote (direct), paraphrase (reworded), inference (derived), none",
                        "default": "none"
                    },
                    "provenance": {
                        "type": "string",
                        "enum": ["web", "local_file", "user", "tool_output", "unknown"],
                        "description": "Where the fact came from",
                        "default": "unknown"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Searchable tags"
                    },
                    "workflow": {
                        "type": "string",
                        "description": "Source workflow name",
                        "default": "manual"
                    },
                    "sensitivity": {
                        "type": "string",
                        "enum": ["public", "internal", "sensitive"],
                        "default": "public"
                    }
                },
                "required": ["claim"]
            }
        ),
        Tool(
            name="duro_store_decision",
            description="Store a decision with rationale. Decisions capture choices made and why.",
            inputSchema={
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "description": "The decision made"
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Why this decision was made"
                    },
                    "alternatives": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Other options considered"
                    },
                    "context": {
                        "type": "string",
                        "description": "Situation context"
                    },
                    "reversible": {
                        "type": "boolean",
                        "description": "Whether decision can be undone",
                        "default": True
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Searchable tags"
                    },
                    "workflow": {
                        "type": "string",
                        "description": "Source workflow name",
                        "default": "manual"
                    },
                    "sensitivity": {
                        "type": "string",
                        "enum": ["public", "internal", "sensitive"],
                        "default": "internal"
                    }
                },
                "required": ["decision", "rationale"]
            }
        ),
        Tool(
            name="duro_validate_decision",
            description="Validate or reverse a decision based on evidence. Updates the decision's current truth AND creates an append-only validation event for full history. Use this to record whether a decision worked out.",
            inputSchema={
                "type": "object",
                "properties": {
                    "decision_id": {
                        "type": "string",
                        "description": "The decision ID to validate"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["validated", "reversed", "superseded"],
                        "description": "New status: validated (worked), reversed (didn't work), superseded (replaced)"
                    },
                    "episode_id": {
                        "type": "string",
                        "description": "Optional episode ID that provides evidence"
                    },
                    "result": {
                        "type": "string",
                        "enum": ["success", "partial", "failed"],
                        "description": "Episode result as evidence"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional context about the evidence"
                    },
                    "expected_outcome": {
                        "type": "string",
                        "description": "What was expected to happen"
                    },
                    "actual_outcome": {
                        "type": "string",
                        "description": "What actually happened"
                    },
                    "next_action": {
                        "type": "string",
                        "description": "What to do next based on this validation"
                    },
                    "confidence_delta": {
                        "type": "number",
                        "description": "Override automatic confidence adjustment (e.g., +0.1, -0.2)"
                    }
                },
                "required": ["decision_id", "status"]
            }
        ),
        Tool(
            name="duro_link_decision",
            description="Link a decision to an episode where it was used/tested.",
            inputSchema={
                "type": "object",
                "properties": {
                    "decision_id": {
                        "type": "string",
                        "description": "The decision ID"
                    },
                    "episode_id": {
                        "type": "string",
                        "description": "The episode ID where this decision was applied"
                    }
                },
                "required": ["decision_id", "episode_id"]
            }
        ),
        Tool(
            name="duro_list_unreviewed_decisions",
            description="""List decisions that need review. Surfaces decisions old enough to have outcomes but not yet validated.

Use this to find decisions worth reviewing. Default filters exclude smoke-test/auto-generated decisions.
Returns decisions sorted by: needs_review first, then oldest first.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "older_than_days": {
                        "type": "integer",
                        "description": "Only include decisions older than N days (default 14)",
                        "default": 14
                    },
                    "exclude_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to exclude (default: smoke-test, auto-outcome, generated, test)"
                    },
                    "include_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Only include decisions with these tags (e.g., architectural, strategic, process, design)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max decisions to return (default 20)",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="duro_get_validation_history",
            description="Get full validation history for a decision. Returns all validation events in chronological order, showing how the decision has evolved over time.",
            inputSchema={
                "type": "object",
                "properties": {
                    "decision_id": {
                        "type": "string",
                        "description": "The decision ID to get history for"
                    }
                },
                "required": ["decision_id"]
            }
        ),
        Tool(
            name="duro_review_decision",
            description="""Review a decision with full context preload. This is the discipline installer for closing feedback loops.

Loads context pack:
1. Decision core (id, decision, rationale, age, tags, outcome status)
2. Validation timeline (last 3 events)
3. Linked work (episodes + incidents, top 3 each)
4. 48-hour recent changes scan

Then presents a review template. If not dry_run, calls duro_validate_decision with your inputs.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "decision_id": {
                        "type": "string",
                        "description": "The decision ID to review"
                    },
                    "hours_recent_changes": {
                        "type": "integer",
                        "default": 48,
                        "description": "Hours to scan for recent changes (default 48)"
                    },
                    "risk_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Risk tags for change scan (default: derived from decision tags)"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": True,
                        "description": "If true (default), show context only. If false, also prompt for validation inputs."
                    },
                    "status": {
                        "type": "string",
                        "enum": ["validated", "reversed", "superseded"],
                        "description": "Validation status (required if dry_run=false)"
                    },
                    "result": {
                        "type": "string",
                        "enum": ["success", "partial", "failed"],
                        "description": "Outcome result"
                    },
                    "expected_outcome": {
                        "type": "string",
                        "description": "What was expected to happen"
                    },
                    "actual_outcome": {
                        "type": "string",
                        "description": "What actually happened"
                    },
                    "next_action": {
                        "type": "string",
                        "description": "One concrete next action"
                    },
                    "confidence_delta": {
                        "type": "number",
                        "description": "Confidence adjustment (-0.5 to +0.5)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional notes"
                    }
                },
                "required": ["decision_id"]
            }
        ),
        Tool(
            name="duro_review_next_decisions",
            description="""Review the next N unreviewed decisions in sequence.

Pulls from list_unreviewed_decisions and returns context for each.
Use this to install the habit: 'review 3 decisions every session'.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "default": 3,
                        "description": "Number of decisions to review (default 3)"
                    },
                    "older_than_days": {
                        "type": "integer",
                        "default": 14,
                        "description": "Only decisions older than N days (default 14)"
                    },
                    "include_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Only include decisions with these tags"
                    },
                    "exclude_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exclude decisions with these tags"
                    }
                }
            }
        ),

        # Incident & Change Ledger tools (Root Cause Analysis)
        # DEBUG GATE: Enforces 3-pass debugging discipline before closing incidents
        Tool(
            name="duro_store_incident",
            description="""Store an incident RCA (Root Cause Analysis). DEBUG GATE ENFORCED - must complete 3 passes:
1. Pass 1 (Repro): repro_steps with at least 2 steps
2. Pass 2 (Boundary): first_bad_boundary naming the boundary surface
3. Pass 3 (Causality): 48-hour recent_change_scan, with changes linked or cleared_reason
4. Prevention: Must be actionable (verb + artifact), no 'be careful' handwaving

Use override=true with override_reason to bypass gate (creates waiver trail).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "symptom": {
                        "type": "string",
                        "description": "What was observed failing"
                    },
                    "actual_cause": {
                        "type": "string",
                        "description": "The real root cause"
                    },
                    "fix": {
                        "type": "string",
                        "description": "What was done to fix it"
                    },
                    "trigger": {
                        "type": "string",
                        "description": "Exact sequence that produces failure"
                    },
                    "first_bad_boundary": {
                        "type": "string",
                        "description": "First place where output becomes wrong (config path, env var, API response, DB read/write, service startup, deploy step)"
                    },
                    "why_not_caught": {
                        "type": "string",
                        "description": "Why this wasn't caught earlier"
                    },
                    "prevention": {
                        "type": "string",
                        "description": "How to prevent recurrence. MUST be actionable (e.g., 'Add startup log of X', 'Assert Y exists', 'Add smoke test'). Banned: 'be careful', 'remember to', etc."
                    },
                    "related_recent_changes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of recent_change artifacts linked to this incident"
                    },
                    # Debug Gate fields
                    "repro_steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Steps to reproduce the issue (gate requires at least 2 steps)"
                    },
                    "recent_change_scan": {
                        "type": "object",
                        "properties": {
                            "hours": {"type": "integer", "default": 48},
                            "risk_tags": {"type": "array", "items": {"type": "string"}},
                            "results": {"type": "array", "items": {"type": "string"}, "description": "Change IDs found by query"},
                            "linked": {"type": "array", "items": {"type": "string"}, "description": "Change IDs actually linked to this incident"},
                            "cleared_reason": {"type": "string", "description": "Required if no changes linked, e.g., 'No infra changes; issue was malformed input'"}
                        },
                        "description": "48-hour recent change scan results. Auto-runs if not provided."
                    },
                    "override": {
                        "type": "boolean",
                        "default": False,
                        "description": "Set to true to bypass debug gate (creates waiver trail)"
                    },
                    "override_reason": {
                        "type": "string",
                        "description": "Required when override=true (e.g., 'prod down, mitigated first')"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "default": "medium"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Searchable tags (config, sync, multi-machine, env, permissions...)"
                    }
                },
                "required": ["symptom", "actual_cause", "fix"]
            }
        ),
        Tool(
            name="duro_store_change",
            description="Store a recent change to the change ledger. Use this when making structural changes (config, db, paths, sync, deploy). This powers the 48-hour rule for debugging.",
            inputSchema={
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": "What was changed (repo/service/module/env/config)"
                    },
                    "change": {
                        "type": "string",
                        "description": "One sentence describing the change"
                    },
                    "why": {
                        "type": "string",
                        "description": "Reason for the change"
                    },
                    "risk_tags": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["config", "db", "paths", "sync", "deploy", "auth", "caching", "env", "permissions", "network", "state", "api", "schema"]
                        },
                        "description": "Risk categories this change touches"
                    },
                    "quick_checks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fast ways to verify the change works"
                    },
                    "commit_hash": {
                        "type": "string",
                        "description": "Git commit hash if applicable"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional searchable tags"
                    }
                },
                "required": ["scope", "change"]
            }
        ),
        Tool(
            name="duro_query_recent_changes",
            description="Query recent changes within a time window. This is the '48-hour rule' query - when debugging, check what changed recently that might be related.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Look back this many hours (default 48)",
                        "default": 48
                    },
                    "risk_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by risk tags (config, db, paths, sync, etc.)"
                    },
                    "scope": {
                        "type": "string",
                        "description": "Filter by scope"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return",
                        "default": 20
                    }
                }
            }
        ),
        # Debug Gate Helper Tools
        Tool(
            name="duro_debug_gate_start",
            description="Start a debug session with gate prompts. Creates a draft incident and returns the prompts to fill.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symptom": {
                        "type": "string",
                        "description": "What was observed failing"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Initial tags for risk tag inference (config, sync, env, etc.)"
                    }
                },
                "required": ["symptom"]
            }
        ),
        Tool(
            name="duro_debug_gate_status",
            description="Check what's missing to pass the debug gate for a draft incident.",
            inputSchema={
                "type": "object",
                "properties": {
                    "incident_id": {
                        "type": "string",
                        "description": "The incident ID to check"
                    }
                },
                "required": ["incident_id"]
            }
        ),
        Tool(
            name="duro_store_design_ref",
            description="Store a design reference for the taste library. Use when studying good designs to extract patterns and rules.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Name of the product/site"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Pattern category (hero, pricing, nav, onboarding, card, form, dashboard, etc.)"
                    },
                    "url": {
                        "type": "string",
                        "description": "URL to the design"
                    },
                    "why_it_works": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-3 bullets on why this design works"
                    },
                    "stealable_rules": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Small, concrete rules to extract"
                    },
                    "style_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Style descriptors (minimal, bold, editorial, playful, etc.)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional searchable tags"
                    }
                },
                "required": ["product_name", "pattern"]
            }
        ),
        Tool(
            name="duro_store_checklist",
            description="Store a checklist template. Use for repeatable processes like 'new_service', 'deploy', 'debug_start'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Template name (e.g., new_service, deploy, debug)"
                    },
                    "description": {
                        "type": "string",
                        "description": "When to use this checklist"
                    },
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "category": {"type": "string"},
                                "required": {"type": "boolean", "default": True}
                            }
                        },
                        "description": "Checklist items"
                    },
                    "code_snippets": {
                        "type": "object",
                        "description": "Stack-specific code snippets (python, node, go, etc.)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Searchable tags"
                    }
                },
                "required": ["name", "items"]
            }
        ),

        Tool(
            name="duro_query_memory",
            description="Query artifacts from memory. SQLite-backed fast search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "artifact_type": {
                        "type": "string",
                        "enum": ["fact", "decision", "skill", "rule", "log", "episode", "evaluation", "skill_stats"],
                        "description": "Filter by artifact type"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (any match)"
                    },
                    "sensitivity": {
                        "type": "string",
                        "enum": ["public", "internal", "sensitive"],
                        "description": "Filter by sensitivity level"
                    },
                    "workflow": {
                        "type": "string",
                        "description": "Filter by source workflow"
                    },
                    "search_text": {
                        "type": "string",
                        "description": "Search in titles/content"
                    },
                    "since": {
                        "type": "string",
                        "description": "ISO date to filter from (e.g., 2026-02-01)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="duro_semantic_search",
            description="Semantic search across artifacts using hybrid vector + keyword matching. Falls back gracefully to keyword-only if embeddings unavailable. Returns ranked results with optional score breakdown.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query"
                    },
                    "artifact_type": {
                        "type": "string",
                        "enum": ["fact", "decision", "episode", "evaluation", "skill_stats", "log"],
                        "description": "Filter by artifact type"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (any match)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return",
                        "default": 20
                    },
                    "explain": {
                        "type": "boolean",
                        "description": "Include score breakdown for debugging/tuning",
                        "default": False
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="duro_get_artifact",
            description="Retrieve full artifact by ID. Returns complete JSON envelope.",
            inputSchema={
                "type": "object",
                "properties": {
                    "artifact_id": {
                        "type": "string",
                        "description": "The artifact ID to retrieve"
                    }
                },
                "required": ["artifact_id"]
            }
        ),
        Tool(
            name="duro_list_artifacts",
            description="List recent artifacts, optionally filtered by type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "artifact_type": {
                        "type": "string",
                        "enum": ["fact", "decision", "skill", "rule", "log", "episode", "evaluation", "skill_stats"],
                        "description": "Filter by type"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="duro_reindex",
            description="Rebuild SQLite index from artifact files. Use if index gets out of sync.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_list_repairs",
            description="List recent repair operations (reindex, reembed). Shows audit trail of self-healing operations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="duro_run_migration",
            description="Run database migrations to add new features (e.g., vector search tables). Safe to run multiple times - migrations are idempotent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "migration_id": {
                        "type": "string",
                        "description": "Specific migration to run (e.g., '001_add_vectors'). If omitted, runs all pending migrations.",
                        "default": None
                    },
                    "action": {
                        "type": "string",
                        "enum": ["up", "status"],
                        "description": "up = apply migration, status = check status without applying",
                        "default": "status"
                    }
                }
            }
        ),
        Tool(
            name="duro_delete_artifact",
            description="Delete an artifact with audit logging. Requires a reason. Refuses to delete sensitive artifacts unless force=True.",
            inputSchema={
                "type": "object",
                "properties": {
                    "artifact_id": {
                        "type": "string",
                        "description": "The artifact ID to delete"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Required: Explanation for why this artifact is being deleted"
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Override sensitivity protection for sensitive artifacts. Use with caution.",
                        "default": False
                    }
                },
                "required": ["artifact_id", "reason"]
            }
        ),
        Tool(
            name="duro_batch_delete",
            description="Batch delete multiple artifacts with a single approval. Use for cleanup operations like removing smoke test artifacts. Requires ONE approval for the entire batch.",
            inputSchema={
                "type": "object",
                "properties": {
                    "artifact_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of artifact IDs to delete"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Explanation for why these artifacts are being deleted (applies to all)"
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Override sensitivity protection for sensitive artifacts.",
                        "default": False
                    }
                },
                "required": ["artifact_ids", "reason"]
            }
        ),
        Tool(
            name="duro_query_audit_log",
            description="Query the audit log (deletions). Returns entries with optional integrity chain verification.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "description": "Filter by event type (e.g., 'delete')",
                        "enum": ["delete"]
                    },
                    "artifact_id": {
                        "type": "string",
                        "description": "Filter by specific artifact ID"
                    },
                    "search_text": {
                        "type": "string",
                        "description": "Search in reason field"
                    },
                    "since": {
                        "type": "string",
                        "description": "ISO date to filter from (e.g., 2026-02-01)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return",
                        "default": 50
                    },
                    "verify_chain": {
                        "type": "boolean",
                        "description": "Verify integrity chain hashes",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="duro_log_audit_repair",
            description="Log an audit chain repair event. Use after manually fixing integrity chain issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "backup_path": {
                        "type": "string",
                        "description": "Path to the backup file"
                    },
                    "backup_hash": {
                        "type": "string",
                        "description": "SHA256 of backup file content"
                    },
                    "repaired_hash": {
                        "type": "string",
                        "description": "SHA256 of repaired file content"
                    },
                    "entries_before": {
                        "type": "integer",
                        "description": "Number of entries in backup"
                    },
                    "entries_after": {
                        "type": "integer",
                        "description": "Number of entries after repair"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why the repair was needed"
                    }
                },
                "required": ["backup_path", "backup_hash", "repaired_hash", "entries_before", "entries_after", "reason"]
            }
        ),
        Tool(
            name="duro_query_repair_log",
            description="Query the audit repair log (meta-audit of chain fixes).",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return",
                        "default": 20
                    }
                }
            }
        ),

        # Orchestration tools
        Tool(
            name="duro_orchestrate",
            description="Route a task through the workflow selector. Checks rules, selects skill/tool, executes, logs run.",
            inputSchema={
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "description": "What you want to do (e.g., 'store fact', 'store decision', 'delete artifact')"
                    },
                    "args": {
                        "type": "object",
                        "description": "Arguments for the task (e.g., claim, confidence, source_urls)",
                        "default": {}
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, show what would happen without executing",
                        "default": False
                    },
                    "sensitivity": {
                        "type": "string",
                        "enum": ["public", "internal", "sensitive"],
                        "description": "Override auto-detected sensitivity"
                    }
                },
                "required": ["intent"]
            }
        ),
        Tool(
            name="duro_list_runs",
            description="List recent orchestration runs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max runs to return",
                        "default": 20
                    },
                    "outcome": {
                        "type": "string",
                        "enum": ["success", "failed", "denied", "dry_run"],
                        "description": "Filter by outcome"
                    }
                }
            }
        ),
        Tool(
            name="duro_get_run",
            description="Get full details of a specific run.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "The run ID to retrieve"
                    }
                },
                "required": ["run_id"]
            }
        ),

        # Episode tools (Phase 1: Feedback Loop)
        Tool(
            name="duro_create_episode",
            description="Create a new episode to track goal-level work. Episodes capture: goal -> plan -> actions -> result -> evaluation. Use for tasks >3min, that use tools, or produce artifacts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "What this episode is trying to achieve"
                    },
                    "plan": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Planned steps to achieve the goal"
                    },
                    "context": {
                        "type": "object",
                        "description": "Context including domain, constraints, environment",
                        "properties": {
                            "domain": {"type": "string"},
                            "constraints": {"type": "array", "items": {"type": "string"}},
                            "environment": {"type": "object"}
                        }
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Searchable tags"
                    }
                },
                "required": ["goal"]
            }
        ),
        Tool(
            name="duro_add_episode_action",
            description="Add an action to an open episode. Actions are refs (run_id, tool, summary) not full outputs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {
                        "type": "string",
                        "description": "The episode ID to update"
                    },
                    "run_id": {
                        "type": "string",
                        "description": "Run ID of the action (if orchestrated)"
                    },
                    "tool": {
                        "type": "string",
                        "description": "Tool used in this action"
                    },
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of what the action did"
                    }
                },
                "required": ["episode_id", "summary"]
            }
        ),
        Tool(
            name="duro_close_episode",
            description="Close an episode with its result. This marks the episode as complete and calculates duration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {
                        "type": "string",
                        "description": "The episode ID to close"
                    },
                    "result": {
                        "type": "string",
                        "enum": ["success", "partial", "failed"],
                        "description": "Final outcome of the episode"
                    },
                    "result_summary": {
                        "type": "string",
                        "description": "Brief summary of what was achieved"
                    },
                    "links": {
                        "type": "object",
                        "description": "References to artifacts created/used during this episode",
                        "properties": {
                            "facts_created": {"type": "array", "items": {"type": "string"}},
                            "decisions_created": {"type": "array", "items": {"type": "string"}},
                            "decisions_used": {"type": "array", "items": {"type": "string"}},
                            "skills_used": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                "required": ["episode_id", "result"]
            }
        ),
        Tool(
            name="duro_evaluate_episode",
            description="Create an evaluation for a closed episode. Rubric: outcome_quality, cost, correctness_risk, reusability, reproducibility (all 0-5 scale).",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {
                        "type": "string",
                        "description": "The episode ID to evaluate"
                    },
                    "rubric": {
                        "type": "object",
                        "description": "Evaluation scores (0-5 scale)",
                        "properties": {
                            "outcome_quality": {"type": "object", "properties": {"score": {"type": "integer"}, "notes": {"type": "string"}}},
                            "cost": {"type": "object", "properties": {"duration_mins": {"type": "number"}, "tools_used": {"type": "integer"}, "tokens_bucket": {"type": "string", "enum": ["XS", "S", "M", "L", "XL"]}}},
                            "correctness_risk": {"type": "object", "properties": {"score": {"type": "integer"}, "notes": {"type": "string"}}},
                            "reusability": {"type": "object", "properties": {"score": {"type": "integer"}, "notes": {"type": "string"}}},
                            "reproducibility": {"type": "object", "properties": {"score": {"type": "integer"}, "notes": {"type": "string"}}}
                        }
                    },
                    "grade": {
                        "type": "string",
                        "description": "Overall grade (A+, A, B+, B, C, D, F)"
                    },
                    "memory_updates": {
                        "type": "object",
                        "description": "Artifacts to reinforce or decay",
                        "properties": {
                            "reinforce": {"type": "array", "items": {"type": "object"}},
                            "decay": {"type": "array", "items": {"type": "object"}}
                        }
                    },
                    "next_change": {
                        "type": "string",
                        "description": "What to do differently next time"
                    }
                },
                "required": ["episode_id", "rubric", "grade"]
            }
        ),
        Tool(
            name="duro_apply_evaluation",
            description="Apply memory updates from an evaluation. Reinforces/decays confidence on facts and skill stats. Deltas capped at +/-0.02, confidence range 0.05-0.99.",
            inputSchema={
                "type": "object",
                "properties": {
                    "evaluation_id": {
                        "type": "string",
                        "description": "The evaluation ID to apply"
                    }
                },
                "required": ["evaluation_id"]
            }
        ),
        Tool(
            name="duro_get_episode",
            description="Get full details of an episode including actions and links.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {
                        "type": "string",
                        "description": "The episode ID to retrieve"
                    }
                },
                "required": ["episode_id"]
            }
        ),
        Tool(
            name="duro_list_episodes",
            description="List recent episodes, optionally filtered by status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "closed"],
                        "description": "Filter by episode status"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max episodes to return",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="duro_suggest_episode",
            description="Check if current work should become an episode. Returns suggestion based on: tools_used, duration >3min, or artifact production. Use this for auto-detection without full automation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tools_used": {
                        "type": "boolean",
                        "description": "Whether tools were used in this work"
                    },
                    "duration_mins": {
                        "type": "number",
                        "description": "Duration of work so far in minutes"
                    },
                    "artifacts_produced": {
                        "type": "boolean",
                        "description": "Whether any artifacts (facts, decisions, code) were produced"
                    },
                    "goal_summary": {
                        "type": "string",
                        "description": "Brief summary of what was being worked on"
                    }
                },
                "required": ["tools_used"]
            }
        ),

        # === Autonomy Tools ===
        Tool(
            name="duro_check_permission",
            description="Check if an action is permitted based on autonomy level and reputation. Returns whether action is allowed, required approval, or should downgrade to 'propose only' mode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action to check (e.g., 'edit_file', 'delete_file', 'deploy', 'store_decision')"
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain override (auto-detected from action if not provided)"
                    },
                    "context": {
                        "type": "object",
                        "description": "Optional context hints: {is_destructive: bool, affects_production: bool, is_reversible: bool}",
                        "properties": {
                            "is_destructive": {"type": "boolean"},
                            "affects_production": {"type": "boolean"},
                            "is_reversible": {"type": "boolean"}
                        }
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="duro_can_execute",
            description="""Quick precheck: can this tool call be executed? Returns machine-readable JSON.

Use this BEFORE executing any tool call that might require approval.
Returns {can_execute: bool, action_needed: "none"|"approve"|"downgrade", reason: str}

This is the per-tool-call gate for agents - simpler than duro_check_permission.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "The MCP tool about to be called (e.g., 'duro_delete_artifact', 'bash_command')"
                    },
                    "args_hint": {
                        "type": "string",
                        "description": "Optional hint about args (e.g., 'delete', 'rm -rf', 'deploy prod')"
                    },
                    "is_destructive": {
                        "type": "boolean",
                        "description": "Override: mark as destructive regardless of tool name"
                    }
                },
                "required": ["tool_name"]
            }
        ),
        Tool(
            name="duro_get_reputation",
            description="Get reputation scores for all domains or a specific domain. Shows autonomy levels allowed based on reputation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Optional specific domain to check (e.g., 'code_changes', 'incident_rca', 'decisions')"
                    }
                }
            }
        ),
        Tool(
            name="duro_record_outcome",
            description="Record the outcome of an action to update reputation. Call this after an action completes to build reputation history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action that was performed"
                    },
                    "success": {
                        "type": "boolean",
                        "description": "Whether the action succeeded"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence level of the action (0.0-1.0)",
                        "default": 0.5
                    },
                    "was_reverted": {
                        "type": "boolean",
                        "description": "Whether the action was later reverted",
                        "default": False
                    }
                },
                "required": ["action", "success"]
            }
        ),
        Tool(
            name="duro_grant_approval",
            description="""Grant ONE-SHOT approval for a specific high-risk action. Token is consumed on first use and cannot be reused.

IMPORTANT: Approvals are scoped to the EXACT action, not just the tool. The action_id format is:
  tool_name:args_hash (e.g., 'duro_delete_artifact:a1b2c3d4')

When a tool call is blocked by the policy gate, the block message includes the exact action_id to use.
If the arguments change, a new approval is required (the args_hash will differ).

This prevents approval of "delete files" being used for any file - it's scoped to the specific file.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "action_id": {
                        "type": "string",
                        "description": "Scoped action ID in format 'tool_name:args_hash'. Copy this from the policy gate block message."
                    },
                    "duration_seconds": {
                        "type": "integer",
                        "description": "How long the approval is valid (default 300 = 5 minutes, max 900 = 15 minutes)",
                        "default": 300
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this approval is being granted (for audit trail). Required for accountability."
                    }
                },
                "required": ["action_id"]
            }
        ),
        Tool(
            name="duro_autonomy_status",
            description="Get the current autonomy system status including overall reputation, domain scores, and active approvals.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_gate_audit",
            description="Query the policy gate audit log. Shows all tool call decisions (ALLOW/DENY/NEED_APPROVAL), including bypasses and errors. Use for security auditing and debugging permission issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max records to return (default 50)",
                        "default": 50
                    },
                    "tool": {
                        "type": "string",
                        "description": "Filter by tool name (exact match)"
                    },
                    "decision": {
                        "type": "string",
                        "description": "Filter by decision: ALLOW, DENY, or NEED_APPROVAL",
                        "enum": ["ALLOW", "DENY", "NEED_APPROVAL"]
                    },
                    "since": {
                        "type": "string",
                        "description": "ISO timestamp to filter from (e.g., '2026-02-19T00:00:00Z')"
                    }
                }
            }
        ),
        Tool(
            name="duro_workspace_status",
            description="Show current workspace configuration. Displays allowed workspace directories, strict mode setting, and high-risk path approval requirements.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="duro_workspace_add",
            description="Add a directory to the allowed workspaces. File operations will be permitted within this directory and its subdirectories. Adding workspaces outside the home directory requires approval.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the directory to add as a workspace"
                    },
                    "force": {
                        "type": "boolean",
                        "default": False,
                        "description": "Force add after approval has been granted. Required for paths outside home directory."
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="duro_workspace_validate",
            description="Validate a path against workspace constraints. Returns whether the path is allowed, its risk level, and whether approval is required.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to validate"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="duro_classify_action",
            description="Debug tool: classify an action to see its domain, risk level, and what autonomy level is required. Use this to understand why an action might be blocked.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action to classify (e.g., 'edit_file', 'delete_file', 'deploy')"
                    },
                    "context": {
                        "type": "object",
                        "description": "Optional context hints",
                        "properties": {
                            "is_destructive": {"type": "boolean"},
                            "affects_production": {"type": "boolean"},
                            "is_reversible": {"type": "boolean"}
                        }
                    }
                },
                "required": ["action"]
            }
        ),
    ]


# === OUTPUT SCANNING HELPER (Layer 3 post-execution) ===
# Legacy fallback file (used only if unified audit unavailable)
OUTPUT_AUDIT_FILE = Path.home() / ".agent" / "memory" / "audit" / "output_redaction.jsonl"

def _scan_and_redact_tool_output(
    tool_name: str,
    result: list[TextContent]
) -> list[TextContent]:
    """
    Scan tool output for secrets and redact them.

    This is the POST-EXECUTION counterpart to the pre-execution secrets check.
    Tool outputs can leak secrets even if arguments were clean.
    """
    if not SECRETS_OUTPUT_AVAILABLE:
        return result

    if not should_scan_output(tool_name):
        return result

    redacted_result = []
    any_secrets_found = False

    for content in result:
        if content.type == "text" and content.text:
            scan_result = scan_and_redact_output(content.text, tool_name)

            if scan_result.had_secrets:
                any_secrets_found = True

                # Log the redaction event to unified audit
                try:
                    output_hash = compute_output_hash(content.text)

                    if UNIFIED_AUDIT_AVAILABLE:
                        # Use unified audit with hash chain
                        event = build_secrets_event(
                            event_type=EventType.SECRETS_OUTPUT_REDACTED,
                            tool_name=tool_name,
                            action="output_redacted",
                            reason=f"Redacted {scan_result.redaction_count} secrets from output",
                            match_count=scan_result.redaction_count,
                            output_hash=output_hash,
                            output_redacted=True,
                        )
                        append_event(event)
                    else:
                        # Fallback to legacy file
                        audit_entry = create_output_audit_entry(
                            tool_name, scan_result, output_hash
                        )
                        OUTPUT_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
                        with open(OUTPUT_AUDIT_FILE, "a", encoding="utf-8") as f:
                            import json as json_
                            f.write(json_.dumps(audit_entry) + "\n")

                except Exception as e:
                    log_warn(f"Output audit log failed: {e}")

                # Return redacted content
                redacted_result.append(TextContent(
                    type="text",
                    text=scan_result.redacted_output
                ))
            else:
                redacted_result.append(content)
        else:
            redacted_result.append(content)

    if any_secrets_found:
        log_info(f"[SECURITY] Redacted secrets from {tool_name} output")

    return redacted_result


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    # === INTENT CHECK (Layer 6 - capability tokens) ===
    # Intent is minted at user-message boundary, NOT here.
    # Here we only CHECK for existing valid intent.
    #
    # CRITICAL: The model cannot self-authorize by calling tools.
    # on_user_message() must be called from the actual user message handler,
    # not from tool execution paths.
    #
    # We do NOT inject _intent_id into arguments because:
    # 1. It would break args_hash consistency (same action, different hash)
    # 2. require_intent() already checks get_current_intent() as fallback
    # 3. Keeping arguments clean preserves approval scope matching

    # === POLICY GATE (execution-path enforcement) ===
    # Every tool call must pass through this gate. No exceptions.
    if POLICY_GATE_AVAILABLE:
        gate_decision = policy_gate(
            tool_name=name,
            arguments=arguments,
            autonomy_available=AUTONOMY_AVAILABLE,
            check_action_fn=check_action if AUTONOMY_AVAILABLE else None,
            classify_domain_fn=classify_action_domain if AUTONOMY_AVAILABLE else None,
            classify_risk_fn=lambda t, a: ActionRisk.from_action(t, a) if AUTONOMY_AVAILABLE else None,
            get_enforcer_fn=get_autonomy_enforcer if AUTONOMY_AVAILABLE else None,
        )

        if not gate_decision.allowed:
            return [TextContent(type="text", text=gate_decision.to_block_message())]
    elif not AUTONOMY_AVAILABLE:
        # FAIL-CLOSED: If neither gate nor autonomy available, block all non-bypass tools
        # This prevents "oops I forgot to load the security module" holes
        from policy_gate import GATE_BYPASS_TOOLS
        if name not in GATE_BYPASS_TOOLS:
            return [TextContent(type="text", text=f"""## Policy Gate Unavailable

**Tool:** `{name}`
**Status:** BLOCKED (fail-closed)

The policy gate module failed to load. All non-bypass tools are blocked.

Error: {POLICY_GATE_ERROR}

Contact the system administrator or check duro-mcp installation.""")]

    # Inner function to execute tool - allows us to wrap output scanning
    def _execute_tool_handler():
        # Memory tools
        if name == "duro_load_context":
            include_soul = arguments.get("include_soul", True)
            recent_days = arguments.get("recent_days", 3)
            mode = arguments.get("mode", "full")  # full, lean, minimal

            # Auto-compress old logs before loading (keeps context lean)
            compress_results = memory.compress_old_logs()

            result = []
            metrics = {"mode": mode, "chars": 0, "tasks": 0, "decisions": 0, "summaries": 0}

            # === SOUL ===
            # All modes include soul (capped)
            if include_soul:
                soul = memory.load_soul()
                if soul:
                    # Cap to 2500 chars for all modes
                    if len(soul) > 2500:
                        soul = soul[:2497] + "..."
                    result.append(f"## Soul Configuration\n{soul}")
                    metrics["chars"] += len(soul)

            # === CORE MEMORY ===
            if mode == "full":
                # Full core memory
                core = memory.load_core_memory()
                if core:
                    result.append(f"## Core Memory\n{core}")
                    metrics["chars"] += len(core)
            else:
                # Lean/minimal: trimmed core (2000 chars, specific sections)
                core = memory.load_core_trimmed(max_chars=2000)
                if core:
                    result.append(f"## Core Memory (trimmed: User Preferences, Important Context)\n{core}")
                    metrics["chars"] += len(core)

            # === TODAY'S CONTENT ===
            if mode == "full":
                # Full raw log
                today = memory.load_today_memory()
                if today:
                    result.append(f"## Today's Memory\n{today}")
                    metrics["chars"] += len(today)
            elif mode == "lean":
                # Tasks only (max 15)
                tasks = memory.load_today_tasks_only(max_tasks=15)
                if tasks:
                    result.append(tasks)
                    # Count tasks from the output
                    task_count = tasks.count("\n- [")
                    metrics["tasks"] = task_count
                    metrics["chars"] += len(tasks)
            # minimal: no today content

            # === ACTIVE DECISIONS (lean only) ===
            if mode == "lean":
                active_decisions = artifact_store.get_active_decisions(limit=5, max_age_days=7, min_confidence=0.5)
                if active_decisions:
                    decisions_lines = ["## Active Decisions (updated within 7 days, confidence >= 0.5)"]
                    for d in active_decisions:
                        status_badge = f"[{d['status']}]" if d.get('status') else ""
                        age_str = f"{d['age_hours']}h ago" if d.get('age_hours') else ""
                        decisions_lines.append(
                            f"- {d['decision'][:80]} (conf: {d['confidence']:.2f}, {status_badge} {age_str})"
                        )
                    decisions_section = "\n".join(decisions_lines)
                    result.append(decisions_section)
                    metrics["decisions"] = len(active_decisions)
                    metrics["chars"] += len(decisions_section)

            # === RECENT SUMMARIES ===
            if mode == "full":
                # All recent summaries
                recent = memory.load_recent_memory(days=recent_days, use_summaries=True)
                today_date = datetime.now().strftime("%Y-%m-%d")
                older_days = {k: v for k, v in recent.items() if k != today_date}
                if older_days:
                    result.append("## Recent Memory (Summaries)")
                    for date, content in list(older_days.items()):
                        result.append(f"### {date}\n{content}")
                        metrics["chars"] += len(content)
                    metrics["summaries"] = len(older_days)
            elif mode == "lean":
                # Just yesterday's summary (1 day back, 800 chars)
                summary = memory.load_recent_summary(days_back=1, max_chars=800)
                if summary:
                    result.append(f"## Yesterday's Summary (continuity)\n{summary}")
                    metrics["summaries"] = 1
                    metrics["chars"] += len(summary)
            # minimal: no summaries

            # === AUTONOMY SURFACING ===
            # Surface queued insights (2 sections max, 3 items each)
            if AUTONOMY_LAYER_AVAILABLE and autonomy_scheduler:
                try:
                    # First, ensure session started (populates buffer with pending decisions/stale facts)
                    # This is idempotent with TTL caching
                    autonomy_scheduler.ensure_session_started_sync(context=mode)

                    # Get surfacing events (sync, respects quiet mode)
                    surfacing = autonomy_scheduler.get_surfacing_events(
                        max_items=6,  # Max 6 total (3 per section)
                        context=mode,
                    )

                    events = surfacing.get("events", [])
                    if events and surfacing.get("surfaced"):
                        # Split into categories (max 3 each)
                        pending = [e for e in events if e.get("type") == "pending_decision"][:3]
                        stale = [e for e in events if e.get("type") == "stale_fact"][:3]

                        # Add pending decisions section
                        if pending:
                            lines = ["## Decisions Awaiting Review"]
                            for e in pending:
                                p = e.get("payload", {})
                                age = p.get("age_days", "?")
                                decision = p.get("decision", "Untitled")[:60]
                                lines.append(f"- [{age}d] {decision}...")
                            pending_section = "\n".join(lines)
                            result.append(pending_section)
                            metrics["chars"] += len(pending_section)

                        # Add stale facts section
                        if stale:
                            lines = ["## Stale Facts (need reinforcement)"]
                            for e in stale:
                                p = e.get("payload", {})
                                claim = p.get("claim", "Unknown")[:60]
                                conf = p.get("confidence", 0.5)
                                lines.append(f"- {claim} ({conf:.0%})")
                            stale_section = "\n".join(lines)
                            result.append(stale_section)
                            metrics["chars"] += len(stale_section)
                except Exception as e:
                    # Non-fatal, log and continue
                    log_warn(f"Surfacing error in load_context: {e}")

            # === FOOTER ===
            # Context footer with metrics
            footer_parts = [f"Context: {mode}"]
            footer_parts.append(f"{metrics['chars']} chars")
            if metrics["tasks"]:
                footer_parts.append(f"{metrics['tasks']} tasks")
            if metrics["decisions"]:
                footer_parts.append(f"{metrics['decisions']} decisions")
            if metrics["summaries"]:
                footer_parts.append(f"{metrics['summaries']} summary" if metrics["summaries"] == 1 else f"{metrics['summaries']} summaries")

            footer = "\n---\n" + " | ".join(footer_parts)
            result.append(footer)

            # Add compression note if applicable
            if compress_results:
                compressed_dates = [d for d, s in compress_results.items() if "compressed" in s]
                if compressed_dates:
                    result.append(f"*Auto-compressed {len(compressed_dates)} old log(s). Use `duro_query_archive` to access full details.*")

            text = "\n\n".join(result) if result else "No context loaded."
            return [TextContent(type="text", text=text)]

        elif name == "duro_save_memory":
            content = arguments["content"]
            section = arguments.get("section", "Session Log")
            success = memory.save_to_today(content, section)
            # Also create indexed log artifact (check return value)
            log_success, log_id, _ = artifact_store.store_log(
                event_type="info",
                message=content,
                tags=[section]
            )
            if not log_success:
                logging.warning(f"Failed to create log artifact for save_memory")
            text = f"Memory saved to today's log under '{section}'." if success else "Failed to save memory."
            return [TextContent(type="text", text=text)]

        elif name == "duro_save_learning":
            learning = arguments["learning"]
            category = arguments.get("category", "General")
            success = memory.save_learning(learning, category)
            # Also create indexed log artifact (check return value)
            log_success, log_id, _ = artifact_store.store_log(
                event_type="learning",
                message=learning,
                tags=[category]
            )
            if not log_success:
                logging.warning(f"Failed to create log artifact for save_learning")
            text = f"Learning saved: {learning[:100]}..." if success else "Failed to save learning."
            return [TextContent(type="text", text=text)]

        elif name == "duro_log_task":
            task = arguments["task"]
            outcome = arguments["outcome"]
            success = memory.save_task_completed(task, outcome)
            # Also create indexed log artifact (check return value)
            log_success, log_id, _ = artifact_store.store_log(
                event_type="task_complete",
                message=f"{task}: {outcome}",
                task=task,
                outcome=outcome
            )
            if not log_success:
                logging.warning(f"Failed to create log artifact for log_task: {task}")
            text = "Task logged successfully." if success else "Failed to log task."
            return [TextContent(type="text", text=text)]

        elif name == "duro_log_failure":
            task = arguments["task"]
            error = arguments["error"]
            lesson = arguments["lesson"]
            success = memory.save_failure(task, error, lesson)
            # Also create indexed log artifact (check return value)
            log_success, log_id, _ = artifact_store.store_log(
                event_type="task_fail",
                message=f"{task}: {error}",
                task=task,
                error=error,
                lesson=lesson
            )
            if not log_success:
                logging.warning(f"Failed to create log artifact for log_failure: {task}")
            text = "Failure logged with lesson." if success else "Failed to log failure."
            return [TextContent(type="text", text=text)]

        elif name == "duro_compress_logs":
            results = memory.compress_old_logs()
            if results:
                text = "## Memory Compression Results\n\n"
                for date, status in results.items():
                    text += f"- **{date}**: {status}\n"
                stats = memory.get_memory_stats()
                text += f"\n**Current stats:** {stats['active_logs']} active, {stats['summaries']} summaries, {stats['archived_logs']} archived"
            else:
                text = "No logs to compress. Only today's log is active."
            return [TextContent(type="text", text=text)]

        elif name == "duro_query_archive":
            date = arguments.get("date")
            search = arguments.get("search")
            limit = arguments.get("limit", 5)
            max_chars = arguments.get("max_chars", 4000)

            if date:
                # Retrieve specific archived log
                content = memory.load_archived_log(date)
                if content:
                    original_len = len(content)
                    # Apply truncation if max_chars is set and content exceeds it
                    if max_chars and original_len > max_chars:
                        content = content[:max_chars]
                        text = f"## Archived Log: {date}\n\n{content}\n\n---\n*Truncated: showing {max_chars:,} of {original_len:,} chars. Use `max_chars=0` for full log.*"
                    else:
                        text = f"## Archived Log: {date}\n\n{content}"
                else:
                    text = f"No archived log found for {date}"
            elif search:
                # Search through archives
                results = memory.search_archives(search, limit)
                if results:
                    text = f"## Search Results: '{search}'\n\n"
                    for r in results:
                        text += f"### {r['date']}\n"
                        for match in r['matches']:
                            text += f"- Line {match['line_num']}: {match['text']}\n"
                        text += "\n"
                else:
                    text = f"No matches found for '{search}' in archives"
            else:
                text = "Please provide either 'date' or 'search' parameter"
            return [TextContent(type="text", text=text)]

        elif name == "duro_list_archives":
            archives = memory.list_available_archives()
            if archives:
                text = "## Available Archives\n\n"
                total_size = 0
                for a in archives:
                    text += f"- **{a['date']}**: {a['size_kb']} KB\n"
                    total_size += a['size_bytes']
                text += f"\n**Total:** {len(archives)} archives, {round(total_size/1024, 1)} KB"
            else:
                text = "No archives available. Run `duro_compress_logs` to archive old memory logs."
            return [TextContent(type="text", text=text)]

        # Skills tools
        elif name == "duro_list_skills":
            summary = skills.get_skills_summary()
            result = f"## Duro Skills ({summary['total_skills']} total)\n\n"
            result += f"**By tier:** Core: {summary['by_tier']['core']}, Tested: {summary['by_tier']['tested']}, Untested: {summary['by_tier']['untested']}\n\n"
            for s in summary["skills"]:
                result += f"- **{s['name']}** [{s['tier']}]: {s['description']}\n"
            return [TextContent(type="text", text=result)]

        elif name == "duro_find_skills":
            keywords = arguments["keywords"]
            matches = skills.find_skills(keywords)
            if matches:
                result = f"## Skills matching {keywords}\n\n"
                for s in matches:
                    result += f"- **{s['name']}** [{s.get('tier')}]: {s.get('description', '')}\n"
            else:
                result = f"No skills found matching: {keywords}"
            return [TextContent(type="text", text=result)]

        elif name == "duro_run_skill":
            skill_name = arguments["skill_name"]
            args = arguments.get("args", {})
            success, output = skills.run_skill(skill_name, args)
            text = f"**Skill execution {'succeeded' if success else 'failed'}**\n\n{output}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_get_skill_code":
            skill_name = arguments["skill_name"]
            code = skills.get_skill_code(skill_name)
            if code:
                text = f"```python\n{code}\n```"
            else:
                text = f"Skill '{skill_name}' not found."
            return [TextContent(type="text", text=text)]

        # Rules tools
        elif name == "duro_check_rules":
            task_desc = arguments["task_description"]
            applicable = rules.check_rules(task_desc)
            formatted = rules.format_rules_for_context(applicable)

            # Mark rules as used
            for r in applicable:
                rules.apply_rule(r["rule"]["id"])

            return [TextContent(type="text", text=formatted)]

        elif name == "duro_list_rules":
            summary = rules.get_rules_summary()
            result = f"## Duro Rules ({summary['total_rules']} total)\n\n"
            result += f"**Hard rules:** {summary['hard_rules']} | **Soft rules:** {summary['soft_rules']}\n\n"
            for r in summary["rules"]:
                result += f"- **{r['name']}** [{r['type']}]: triggers on {r['keywords']}\n"
            return [TextContent(type="text", text=result)]

        # Project tools
        elif name == "duro_get_project":
            project_name = arguments["project_name"]
            projects_dir = Path(CONFIG["paths"]["projects_dir"])
            project_dir = projects_dir / project_name

            if not project_dir.exists():
                return [TextContent(type="text", text=f"Project '{project_name}' not found.")]

            # Load project files
            result = f"## Project: {project_name}\n\n"

            # Look for common project files
            for filename in ["README.md", "PRODUCTION_WORKFLOW.md", "CHARACTER_BIBLE.md", "setup.py"]:
                file_path = project_dir / filename
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")[:1000]
                    result += f"### {filename}\n{content}...\n\n"

            return [TextContent(type="text", text=result)]

        elif name == "duro_list_projects":
            projects_dir = Path(CONFIG["paths"]["projects_dir"])
            if projects_dir.exists():
                projects = [d.name for d in projects_dir.iterdir() if d.is_dir()]
                result = f"## Projects ({len(projects)})\n\n" + "\n".join(f"- {p}" for p in projects)
            else:
                result = "No projects directory found."
            return [TextContent(type="text", text=result)]

        # Constitution tools (Cartridge Memory System)
        elif name == "duro_load_constitution":
            if not CONSTITUTION_AVAILABLE:
                err_msg = f"❌ Constitution loader not available.\n"
                err_msg += f"Path: {AGENT_LIB_PATH}\n"
                if CONSTITUTION_IMPORT_ERROR:
                    err_msg += f"Error: {CONSTITUTION_IMPORT_ERROR}"
                return [TextContent(type="text", text=err_msg)]

            project_id = arguments.get("project_id")
            if not project_id or not isinstance(project_id, str):
                return [TextContent(type="text", text="❌ project_id is required and must be a string")]

            mode = arguments.get("mode", "compact")
            # Normalize mode
            if mode not in ("minimal", "compact", "full"):
                mode = "compact"

            try:
                const = load_constitution(project_id)
                if not const:
                    available = sorted(list_constitutions())
                    return [TextContent(type="text", text=f"❌ No constitution found for: {project_id}\nAvailable: {', '.join(available) or 'none'}")]

                rendered = render_constitution(const, mode)
                return [TextContent(type="text", text=rendered)]
            except ValueError as e:
                return [TextContent(type="text", text=f"❌ {str(e)}")]

        elif name == "duro_list_constitutions":
            lines = ["## Cartridge Memory System Status\n"]
            lines.append(f"**Lib Path:** `{AGENT_LIB_PATH}`\n")
            lines.append("### Module Status")
            lines.append(f"- Constitution Loader: {'OK' if CONSTITUTION_AVAILABLE else 'FAIL'}{'' if CONSTITUTION_AVAILABLE else f' ({CONSTITUTION_IMPORT_ERROR})'}")
            lines.append(f"- Context Assembler: {'OK' if ASSEMBLER_AVAILABLE else 'FAIL'}{'' if ASSEMBLER_AVAILABLE else f' ({ASSEMBLER_IMPORT_ERROR})'}")
            lines.append(f"- Promotion Compactor: {'OK' if COMPACTOR_AVAILABLE else 'FAIL'}{'' if COMPACTOR_AVAILABLE else f' ({COMPACTOR_IMPORT_ERROR})'}")

            if not CONSTITUTION_AVAILABLE:
                return [TextContent(type="text", text="\n".join(lines))]

            project_ids = sorted(list_constitutions())  # Sorted for stability
            if not project_ids:
                lines.append("\nNo constitutions found in `~/.agent/constitutions/`")
                return [TextContent(type="text", text="\n".join(lines))]

            lines.append(f"\n### Projects ({len(project_ids)})\n")
            for pid in project_ids:
                info = get_constitution_info(pid)
                if info:
                    lines.append(f"**{info['name']}** (`{pid}`) v{info['version']}")
                    lines.append(f"  - Laws: {info['law_count']} ({info['hard_law_count']} hard)")
                    lines.append(f"  - Patterns: {info['pattern_count']}")
                    tokens = info['token_estimate']
                    lines.append(f"  - Tokens: ~{tokens['minimal']}/{tokens['compact']}/{tokens['full']} (min/cmp/full)")
                    lines.append("")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_assemble_context":
            if not ASSEMBLER_AVAILABLE:
                err_msg = f"Context assembler not available.\n"
                if ASSEMBLER_IMPORT_ERROR:
                    err_msg += f"Error: {ASSEMBLER_IMPORT_ERROR}"
                return [TextContent(type="text", text=err_msg)]

            task_desc = arguments.get("task_description", "")
            if not task_desc:
                return [TextContent(type="text", text="❌ task_description is required")]

            project_id = arguments.get("project_id")
            const_mode = arguments.get("constitution_mode", "compact")
            skill_mode = arguments.get("skill_mode", "compact")
            budget_skills = arguments.get("budget_skills", 30000)

            try:
                # Map string modes to enums
                const_render = RenderMode(const_mode) if const_mode in ("minimal", "compact", "full") else RenderMode.COMPACT
                skill_render = RenderMode(skill_mode) if skill_mode in ("minimal", "compact", "full") else RenderMode.COMPACT

                # Build token budget
                budget = TokenBudget(skills=budget_skills)

                # If project_id provided, use it; otherwise auto-detect
                working_dir = Path.cwd()
                if project_id:
                    # Override auto-detection by loading constitution directly
                    const = load_constitution(project_id)
                    if const:
                        const_text = render_constitution(const, const_render.value)
                    else:
                        const_text = None
                else:
                    const_text = None

                pack = assemble_context(
                    task_description=task_desc,
                    working_dir=working_dir,
                    budget=budget,
                    constitution_mode=const_render,
                    skill_mode=skill_render
                )

                # Override constitution if explicitly provided
                if project_id and const_text:
                    pack.constitution = const_text

                formatted = format_context_for_injection(pack)

                result = f"## Assembled Context\n\n"
                result += f"**Task:** {task_desc[:100]}{'...' if len(task_desc) > 100 else ''}\n"
                result += f"**Total Tokens:** ~{pack.total_tokens}\n"
                result += f"**Budget Used:** {pack.budget_used}\n\n"

                # Debug section
                if pack.debug:
                    d = pack.debug
                    result += "### Debug Info\n"
                    result += f"- Working Dir: `{d.working_dir}`\n"
                    result += f"- Detected Project: {d.detected_project or 'none'} (via {d.project_detection_method})\n"
                    result += f"- Constitution: {d.constitution_reason}\n"
                    result += f"- Domain Hints: {d.domain_hints or 'none'}\n"
                    result += f"- Skills: {d.skills_scanned} scanned, {d.skills_matched} matched, {d.skills_selected} selected\n"

                    if d.skill_candidates:
                        result += "\n**Top Skill Candidates:**\n"
                        for c in d.skill_candidates[:5]:
                            result += f"  - {c['name']} (score: {c['score']:.1f})\n"

                result += "\n---\n\n"
                result += formatted

                return [TextContent(type="text", text=result)]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Assembly failed: {str(e)}")]

        elif name == "duro_promotion_report":
            if not COMPACTOR_AVAILABLE:
                err_msg = "Promotion compactor not available."
                if COMPACTOR_IMPORT_ERROR:
                    err_msg += f"\nError: {COMPACTOR_IMPORT_ERROR}"
                return [TextContent(type="text", text=err_msg)]

            try:
                report = get_promotion_report()

                lines = ["## Promotion Report\n"]
                lines.append(f"**Ready for Promotion:** {report['ready_for_promotion']}")
                lines.append(f"**Pending (building evidence):** {len(report['waiting'])}")
                lines.append(f"**Contradicted (rejected):** {report['contradicted']}")

                if report['ready']:
                    lines.append("\n### Ready to Promote\n")
                    for item in report['ready']:
                        lines.append(f"- `{item['id']}` ({item['type']})")
                        lines.append(f"  Score: {item['score']:.1f} | Occurrences: {item['occurrences']}")
                        lines.append(f"  Preview: {item['content_preview'][:60]}...")

                if report['waiting']:
                    lines.append("\n### Pending (need more evidence)\n")
                    for item in report['waiting'][:5]:  # Top 5
                        lines.append(f"- `{item['id']}` ({item['type']}) - score: {item['score']:.1f}")

                return [TextContent(type="text", text="\n".join(lines))]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Report failed: {str(e)}")]

        # System tools
        elif name == "duro_status":
            mem_stats = memory.get_memory_stats()
            skill_summary = skills.get_skills_summary()
            rule_summary = rules.get_rules_summary()
            artifact_stats = artifact_store.get_stats()

            # Get embedding stats for visibility
            emb_stats = artifact_store.index.get_embedding_stats()
            pending_dir = MEMORY_DIR / "pending_embeddings"
            pending_count = 0
            oldest_pending_mins = 0
            if pending_dir.exists():
                pending_files = list(pending_dir.glob("*.pending"))
                pending_count = len(pending_files)
                if pending_files:
                    import os
                    now = utc_now().timestamp()
                    oldest_mtime = min(os.path.getmtime(f) for f in pending_files)
                    oldest_pending_mins = int((now - oldest_mtime) / 60)

            # Embedding status indicator
            emb_coverage = emb_stats.get('coverage_pct', 0)
            if pending_count == 0 and emb_coverage >= 99:
                emb_status = "✅"
            elif pending_count > 100 or oldest_pending_mins > 30:
                emb_status = "⚠️"
            else:
                emb_status = "🔄"

            emb_lag_info = ""
            if pending_count > 0:
                emb_lag_info = f" ({pending_count} pending, oldest {oldest_pending_mins}m)"

            result = f"""## Duro System Status

**Memory**
- Active logs: {mem_stats['active_logs']}
- Summaries: {mem_stats['summaries']}
- Archived: {mem_stats['archived_logs']}
- Core memory: {'Yes' if mem_stats['core_memory_exists'] else 'No'}
- Today's log: {'Yes' if mem_stats['today_file_exists'] else 'No'}

**Artifacts (Structured Memory)**
- Total artifacts: {artifact_stats['total_artifacts']}
- By type: {artifact_stats['by_type']}
- By sensitivity: {artifact_stats['by_sensitivity']}

**Embeddings** {emb_status}
- Coverage: {emb_stats.get('embeddings_count', 0)}/{emb_stats.get('artifacts_count', 0)} ({emb_coverage:.1f}%){emb_lag_info}

**Skills**
- Total skills: {skill_summary['total_skills']}
- Core: {skill_summary['by_tier']['core']} | Tested: {skill_summary['by_tier']['tested']} | Untested: {skill_summary['by_tier']['untested']}

**Rules**
- Total rules: {rule_summary['total_rules']}
- Hard: {rule_summary['hard_rules']} | Soft: {rule_summary['soft_rules']}

**Status:** Operational
**Timestamp:** {datetime.now().isoformat()}
"""
            return [TextContent(type="text", text=result)]

        elif name == "duro_health_check":
            verbose = arguments.get("verbose", False)
            health = _startup_health_check()

            # Build output
            status_icons = {"ok": "✅", "warning": "⚠️", "error": "❌"}
            overall_icon = status_icons.get(health["overall"], "❓")

            lines = [f"## Duro Health Check {overall_icon}\n"]
            lines.append(f"**Timestamp:** {health['timestamp']}")
            lines.append(f"**Overall Status:** {health['overall'].upper()}\n")

            lines.append("### Checks\n")
            for check_name, check_data in health["checks"].items():
                icon = status_icons.get(check_data.get("status"), "❓")
                status = check_data.get("status", "unknown")
                lines.append(f"- **{check_name}**: {icon} {status}")

                if verbose:
                    # Show detailed info for each check
                    for key, value in check_data.items():
                        if key != "status":
                            lines.append(f"  - {key}: {value}")

            if health["issues"]:
                lines.append("\n### Issues Found\n")
                for issue in health["issues"]:
                    lines.append(f"- {issue}")

            # Verbose mode: add artifact types breakdown for drift debugging
            if verbose:
                lines.append("\n### Artifact Types Breakdown\n")
                from schemas import TYPE_DIRECTORIES
                for type_name, dir_name in TYPE_DIRECTORIES.items():
                    type_dir = MEMORY_DIR / dir_name
                    if type_dir.exists():
                        file_count = len(list(type_dir.glob("*.json")))
                        indexed_count = artifact_store.index.count(type_name)
                        drift = abs(file_count - indexed_count)
                        drift_marker = " ⚠️" if drift > 0 else ""
                        lines.append(f"- **{type_name}**: {file_count} files, {indexed_count} indexed{drift_marker}")
                    else:
                        lines.append(f"- **{type_name}**: (dir not created)")

                # Add search capabilities
                lines.append("\n### Search Capabilities\n")
                search_caps = artifact_store.index.get_search_capabilities()
                lines.append(f"- **Mode:** {search_caps['mode']}")
                lines.append(f"- **FTS5:** {'✅' if search_caps['fts_available'] else '❌'}")
                lines.append(f"- **Vector Search:** {'✅' if search_caps['vector_available'] else '❌'}")
                lines.append(f"- **Embeddings:** {search_caps['embedding_count']}")

                # Add embedding model status
                from embeddings import get_embedding_status
                emb_status = get_embedding_status()
                lines.append(f"- **Embedding Model:** {emb_status['model_name'] or 'Not available'}")
                lines.append(f"- **Model Loaded:** {'✅' if emb_status['model_loaded'] else '❌'}")

            if not health["issues"] and not verbose:
                lines.append("\n*All systems operational. Use verbose=true for details.*")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_heartbeat":
            # Diagnostic heartbeat - proves event loop is responsive
            import time
            start_time = time.time()
            echo = arguments.get("echo", "")

            # Get current timestamp
            from time_utils import utc_now_iso
            timestamp = utc_now_iso()

            # Measure how long it took to get here
            latency_ms = (time.time() - start_time) * 1000

            # Get embedding model status (quick check)
            from embeddings import get_embedding_status
            emb_status = get_embedding_status()

            # Get semaphore state
            sem_state = "unknown"
            if _tool_semaphore is not None:
                # Semaphore._value gives available permits
                sem_state = f"{_tool_semaphore._value}/{TOOL_CONCURRENCY_LIMIT} available"

            lines = ["## Duro Heartbeat ❤️\n"]
            lines.append(f"**Timestamp:** {timestamp}")
            lines.append(f"**Latency:** {latency_ms:.2f}ms")
            lines.append(f"**Concurrency:** {sem_state}")
            lines.append(f"**Embedding Model:** {'Loaded ✅' if emb_status['model_loaded'] else 'Not loaded ⏳'}")
            lines.append(f"**Warmed:** {'Yes ✅' if emb_status.get('warmed', False) else 'No'}")

            if echo:
                lines.append(f"\n**Echo:** {echo}")

            lines.append(f"\n*Event loop is responsive. Server is healthy.*")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_cancel_operation":
            operation = (arguments or {}).get("operation", "reembed")

            cancelled = []
            if operation == "all":
                # Cancel all known operations
                for op in ["reembed", "decay", "compress"]:
                    request_cancel(op)
                    cancelled.append(op)
            else:
                request_cancel(operation)
                cancelled.append(operation)

            lines = ["## Cancellation Requested\n"]
            lines.append(f"**Operations:** {', '.join(cancelled)}")
            lines.append("")
            lines.append("Cancellation signals have been sent. Operations will stop at their next checkpoint (typically every 25 items).")
            lines.append("")
            lines.append("*Note: This returns immediately. The operation may take a moment to actually stop.*")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_browser_status":
            if not BROWSER_GUARD_AVAILABLE:
                return [TextContent(type="text", text=f"❌ Browser guard not available: {BROWSER_GUARD_ERROR}")]

            status = get_browser_status()

            lines = ["## Browser Sandbox Status\n"]
            lines.append(f"**Mode:** {status['mode']}")
            lines.append(f"**Active Profiles:** {status['active_profiles']}")
            lines.append(f"**Downloads Dir:** {status['downloads_dir']}")
            lines.append(f"**Max Download Size:** {status['max_download_size_mb']}MB")
            lines.append(f"**Max Session Duration:** {status['max_session_duration_seconds']}s")
            lines.append(f"**Max Pages/Session:** {status['max_pages_per_session']}")
            lines.append("")
            lines.append("**Restrictions:**")
            lines.append(f"- Clipboard: {'Disabled' if status['disable_clipboard'] else 'Enabled'}")
            lines.append(f"- Password Manager: {'Disabled' if status['disable_password_manager'] else 'Enabled'}")
            lines.append(f"- Tag as Untrusted: {'Yes' if status['tag_content_as_untrusted'] else 'No'}")
            lines.append("")
            lines.append(f"**Domain Allowlist:** {status['domain_allowlist'] or '(none - all allowed)'}")
            lines.append(f"**Domain Blocklist Count:** {status['domain_blocklist_count']}")

            if status['recent_sessions']:
                lines.append("\n**Recent Sessions:**")
                for sess in status['recent_sessions'][-3:]:
                    lines.append(f"- {sess.get('event', 'unknown')}: {sess.get('session_id', 'unknown')[:30]}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_browser_check_url":
            url = arguments["url"]

            if not BROWSER_GUARD_AVAILABLE:
                return [TextContent(type="text", text=f"❌ Browser guard not available: {BROWSER_GUARD_ERROR}")]

            config = get_sandbox_config()
            allowed, reason = check_browser_policy(url, "navigate", config)

            domain = normalize_domain(url)
            status_icon = "✅" if allowed else "❌"

            result = f"""## Browser URL Check

**URL:** {url}
**Domain:** {domain}
**Allowed:** {status_icon} {'Yes' if allowed else 'No'}
**Reason:** {reason}
**Sandbox Mode:** {config.mode}
"""
            return [TextContent(type="text", text=result)]

        # Autonomy Layer Tools
        elif name == "duro_autonomy_insights":
            if not AUTONOMY_LAYER_AVAILABLE or autonomy_scheduler is None:
                return [TextContent(type="text", text=f"❌ Autonomy layer not available: {AUTONOMY_LAYER_ERROR}")]

            max_items = arguments.get("max_items", 3)
            types_filter = arguments.get("types")
            include_debug = arguments.get("include_debug", False)

            # Get insights
            surfacing = autonomy_scheduler.get_surfacing_events(
                max_items=max_items,
                type_filter=types_filter,
            )

            events = surfacing.get("events", [])
            lines = ["## Autonomous Insights\n"]

            if not events:
                lines.append("No queued insights available.")
            else:
                for e in events:
                    ev_type = e.get("type", "unknown")
                    payload = e.get("payload", {})
                    priority = e.get("priority", 0)

                    if ev_type == "pending_decision":
                        decision = payload.get("decision", "Unknown")[:80]
                        age = payload.get("age_days", "?")
                        lines.append(f"**[{priority}] Pending Decision** ({age}d ago)")
                        lines.append(f"> {decision}...")
                        lines.append("")
                    elif ev_type == "stale_fact":
                        claim = payload.get("claim", "Unknown")[:80]
                        conf = payload.get("confidence", 0.5)
                        lines.append(f"**[{priority}] Stale Fact** (conf: {conf:.0%})")
                        lines.append(f"> {claim}...")
                        lines.append("")
                    else:
                        lines.append(f"**[{priority}] {ev_type}**")
                        lines.append(f"> {json.dumps(payload)[:100]}...")
                        lines.append("")

            if include_debug:
                status = autonomy_scheduler.get_status()
                lines.append("\n---\n### Debug Info\n")
                lines.append(f"**Buffer Size:** {status['buffer']['size']}")
                lines.append(f"**Quiet Mode:** {status['quiet_mode']['decision']} (score: {status['quiet_mode']['quiet_score']:.2f})")
                lines.append(f"**Session Cache Valid:** {status['session']['cache_valid']}")
                lines.append(f"\n**Factors:**")
                for k, v in status['quiet_mode'].get('factors', {}).items():
                    lines.append(f"- {k}: {v:.2f}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_quiet_mode":
            if not AUTONOMY_LAYER_AVAILABLE or autonomy_scheduler is None:
                return [TextContent(type="text", text=f"❌ Autonomy layer not available: {AUTONOMY_LAYER_ERROR}")]

            action = arguments.get("action", "status")
            duration = arguments.get("duration_minutes", 60)

            if action == "enable":
                autonomy_scheduler.quiet_mode.set_override(True, duration)
                return [TextContent(type="text", text=f"✅ Quiet mode enabled for {duration} minutes. Only critical insights will be surfaced.")]

            elif action == "disable":
                autonomy_scheduler.quiet_mode.set_override(False)
                return [TextContent(type="text", text="✅ Quiet mode disabled. Normal surfacing resumed.")]

            else:  # status
                rep_score = 0.5
                if AUTONOMY_AVAILABLE:
                    store = get_reputation_store()
                    rep_score = store.global_score

                status = autonomy_scheduler.quiet_mode.get_status(reputation=rep_score)
                override = status.get("override")

                lines = ["## Quiet Mode Status\n"]
                lines.append(f"**Decision:** {status['decision']}")
                lines.append(f"**Quiet Score:** {status['quiet_score']:.2f}")

                if override and override.get("enabled"):
                    until = override.get("until_unix", 0)
                    from datetime import datetime
                    until_dt = datetime.fromtimestamp(until)
                    lines.append(f"**Override:** Active until {until_dt.strftime('%H:%M')}")

                lines.append("\n**Factors:**")
                for k, v in status.get("factors", {}).items():
                    lines.append(f"- {k}: {v:.2f}")

                lines.append("\n**Feedback Stats:**")
                fb = status.get("feedback_stats", {})
                lines.append(f"- Total: {fb.get('total', 0)}")
                lines.append(f"- Negative Rate: {fb.get('negative_rate', 0):.1%}")
                counts = fb.get("counts", {})
                for label, count in counts.items():
                    lines.append(f"- {label}: {count}")

                return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_surfacing_feedback":
            if not AUTONOMY_LAYER_AVAILABLE or autonomy_scheduler is None:
                return [TextContent(type="text", text=f"❌ Autonomy layer not available: {AUTONOMY_LAYER_ERROR}")]

            surfacing_id = arguments["surfacing_id"]
            feedback = arguments["feedback"]
            notes = arguments.get("notes", "")

            autonomy_scheduler.feedback.record_explicit_feedback(surfacing_id, feedback, notes)

            return [TextContent(type="text", text=f"✅ Feedback recorded: {feedback}" + (f" ({notes})" if notes else ""))]

        elif name == "duro_run_maintenance":
            if not AUTONOMY_LAYER_AVAILABLE or autonomy_scheduler is None:
                return [TextContent(type="text", text=f"❌ Autonomy layer not available: {AUTONOMY_LAYER_ERROR}")]

            task_name = arguments["task"]

            # Use sync version - we're in a thread pool executor, callables are sync
            result = autonomy_scheduler.maintenance.run_now_sync(task_name)

            lines = [f"## Maintenance: {task_name}\n"]

            if "error" in result:
                lines.append(f"❌ **Error:** {result['error']}")
            else:
                for k, v in result.items():
                    if k not in ("notable", "priority"):
                        lines.append(f"- **{k}:** {v}")

            return [TextContent(type="text", text="\n".join(lines))]

        # Audit tools (Layer 5)
        elif name == "duro_audit_query":
            if not UNIFIED_AUDIT_AVAILABLE:
                return [TextContent(type="text", text=f"❌ Unified audit not available: {UNIFIED_AUDIT_ERROR}")]

            limit = arguments.get("limit", 50)
            event_type = arguments.get("event_type")
            tool_filter = arguments.get("tool")
            decision = arguments.get("decision")
            severity = arguments.get("severity")
            since = arguments.get("since")
            include_archives = arguments.get("include_archives", False)

            events = query_log(
                limit=limit,
                event_type=event_type,
                tool=tool_filter,
                decision=decision,
                severity=severity,
                since=since,
                include_archives=include_archives,
            )

            if not events:
                return [TextContent(type="text", text="No matching events found.")]

            lines = [f"## Security Audit Log ({len(events)} events)\n"]

            for event in events[:20]:  # Show first 20 in detail
                ts = event.get("ts", "")[:19]  # Truncate to datetime
                ev_type = event.get("event_type", "unknown")
                sev = event.get("severity", "info")
                tool_name = event.get("tool", "-")
                dec = event.get("decision", "-")
                reason = event.get("reason", "")[:60]

                sev_icon = {"info": "ℹ️", "warn": "⚠️", "high": "🔴", "critical": "🚨"}.get(sev, "❓")

                lines.append(f"**{ts}** {sev_icon} `{ev_type}`")
                if tool_name != "-":
                    lines.append(f"  Tool: `{tool_name}` | Decision: {dec}")
                if reason:
                    lines.append(f"  {reason}...")
                lines.append("")

            if len(events) > 20:
                lines.append(f"*...and {len(events) - 20} more events*")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_audit_verify":
            if not UNIFIED_AUDIT_AVAILABLE:
                return [TextContent(type="text", text=f"❌ Unified audit not available: {UNIFIED_AUDIT_ERROR}")]

            result = verify_log()

            status_icon = "✅" if result.valid else "❌"

            lines = [f"## Audit Log Verification {status_icon}\n"]
            lines.append(f"**Valid:** {'Yes' if result.valid else 'No'}")
            lines.append(f"**Total Events:** {result.total_events}")
            lines.append(f"**Verified Events:** {result.verified_events}")

            if result.signed:
                sig_icon = "✅" if result.signature_valid else "⚠️"
                lines.append(f"**HMAC Signed:** Yes {sig_icon}")
            else:
                lines.append("**HMAC Signed:** No (hash chain only)")

            if not result.valid:
                lines.append(f"\n**First Broken Line:** {result.first_broken_line}")
                if result.first_broken_event_id:
                    lines.append(f"**Broken Event ID:** {result.first_broken_event_id}")
                if result.error:
                    lines.append(f"**Error:** {result.error}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_audit_stats":
            if not UNIFIED_AUDIT_AVAILABLE:
                return [TextContent(type="text", text=f"❌ Unified audit not available: {UNIFIED_AUDIT_ERROR}")]

            stats = get_audit_stats()

            lines = ["## Security Audit Statistics\n"]
            lines.append(f"**Log File:** {stats['log_file']}")
            lines.append(f"**Log Exists:** {'Yes' if stats['log_exists'] else 'No'}")
            lines.append(f"**Log Size:** {stats['log_size_bytes'] / 1024:.1f} KB")
            lines.append(f"**Total Events:** {stats['total_events']}")
            lines.append(f"**HMAC Key Available:** {'Yes' if stats['hmac_key_available'] else 'No'}")
            lines.append(f"**Signed Events:** {'Yes' if stats['signed'] else 'No'}")

            if stats['by_event_type']:
                lines.append("\n**By Event Type:**")
                for ev_type, count in sorted(stats['by_event_type'].items(), key=lambda x: -x[1]):
                    lines.append(f"  - {ev_type}: {count}")

            if stats['by_severity']:
                lines.append("\n**By Severity:**")
                for sev, count in stats['by_severity'].items():
                    lines.append(f"  - {sev}: {count}")

            if stats['by_decision']:
                lines.append("\n**By Decision:**")
                for dec, count in stats['by_decision'].items():
                    lines.append(f"  - {dec}: {count}")

            return [TextContent(type="text", text="\n".join(lines))]

        # Layer 6: Intent Guard & Prompt Firewall tools
        elif name == "duro_intent_status":
            if not INTENT_GUARD_AVAILABLE:
                return [TextContent(type="text", text=f"❌ Intent guard not available: {INTENT_GUARD_ERROR}")]

            status = get_intent_status()
            current = get_current_intent()
            session = get_session_context()

            lines = ["## Intent Guard Status (Layer 6)\n"]
            lines.append(f"**Bypass Active:** {'Yes (testing)' if status.get('bypass_active') else 'No'}")
            lines.append(f"**Has Valid Intent:** {'Yes' if status.get('has_valid_intent') else 'No'}")
            lines.append(f"**Total Tokens:** {status.get('total_tokens', 0)}")
            lines.append(f"**Valid Tokens:** {status.get('valid_tokens', 0)}")
            lines.append(f"**Expired Tokens:** {status.get('expired_tokens', 0)}")
            lines.append(f"**Consumed Tokens:** {status.get('consumed_tokens', 0)}")

            if current:
                lines.append("\n**Current Intent Token:**")
                lines.append(f"  - ID: `{current.token_id[:30]}...`")
                lines.append(f"  - Source: {current.source}")
                lines.append(f"  - Expires: {current.expires_at}")
                if current.scope:
                    lines.append(f"  - Scope: {', '.join(current.scope[:5])}")

            lines.append("\n**Session Context:**")
            lines.append(f"  - Untrusted Output: {'Yes' if session.last_tool_output_untrusted else 'No'}")
            if session.last_untrusted_source_id:
                lines.append(f"  - Last Source: {session.last_untrusted_source_id}")
            if session.last_untrusted_domain:
                lines.append(f"  - Last Domain: {session.last_untrusted_domain}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_firewall_status":
            if not PROMPT_FIREWALL_AVAILABLE:
                return [TextContent(type="text", text=f"❌ Prompt firewall not available: {PROMPT_FIREWALL_ERROR}")]

            status = get_firewall_status()

            lines = ["## Prompt Firewall Status (Layer 6)\n"]
            lines.append(f"**Detection Enabled:** Yes")
            lines.append(f"**Pattern Count:** {status.get('pattern_count', 0)}")
            lines.append(f"**Detections (session):** {status.get('detection_count', 0)}")
            lines.append(f"**Sanitizations (session):** {status.get('sanitization_count', 0)}")

            if status.get('vault_entries', 0) > 0:
                lines.append(f"\n**Content Vault:**")
                lines.append(f"  - Entries: {status.get('vault_entries', 0)}")
                lines.append(f"  - Total Size: {status.get('vault_size_bytes', 0) / 1024:.1f} KB")

            recent = status.get('recent_detections', [])
            if recent:
                lines.append("\n**Recent Detections:**")
                for d in recent[:5]:
                    lines.append(f"  - [{d.get('severity', '?')}] {d.get('pattern', 'unknown')}: {d.get('context', '')[:50]}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_vault_get":
            if not PROMPT_FIREWALL_AVAILABLE:
                return [TextContent(type="text", text=f"❌ Prompt firewall not available: {PROMPT_FIREWALL_ERROR}")]

            vault_id = arguments["vault_id"]
            raw_content = get_raw_content(vault_id)

            if raw_content is None:
                return [TextContent(type="text", text=f"❌ Vault entry not found: {vault_id}")]

            lines = ["## Raw Content from Vault\n"]
            lines.append(f"**Vault ID:** `{vault_id}`")
            lines.append(f"**Source:** {raw_content.get('source_id', 'unknown')}")
            lines.append(f"**Domain:** {raw_content.get('domain', 'unknown')}")
            lines.append(f"**Stored At:** {raw_content.get('stored_at', 'unknown')}")
            lines.append(f"**Content Length:** {len(raw_content.get('content', ''))} chars")
            lines.append("\n---\n")
            lines.append("```")
            lines.append(raw_content.get('content', '(empty)')[:2000])
            if len(raw_content.get('content', '')) > 2000:
                lines.append(f"\n... ({len(raw_content.get('content', '')) - 2000} more chars)")
            lines.append("```")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_layer6_status":
            lines = ["## Layer 6 Security Status\n"]
            lines.append("Layer 6 provides prompt injection defense through capability tokens and content provenance.\n")

            # Intent Guard
            lines.append("### Intent Guard")
            if INTENT_GUARD_AVAILABLE:
                status = get_intent_status()
                lines.append(f"- Status: **Active** {'(bypass mode)' if status.get('bypass_active') else ''}")
                lines.append(f"- Valid Intent: {'Yes' if status.get('has_valid_intent') else 'No'}")
                lines.append(f"- Tokens: {status.get('valid_tokens', 0)} valid / {status.get('total_tokens', 0)} total")
            else:
                lines.append(f"- Status: **Unavailable** ({INTENT_GUARD_ERROR})")

            # Prompt Firewall
            lines.append("\n### Prompt Firewall")
            if PROMPT_FIREWALL_AVAILABLE:
                fw_status = get_firewall_status()
                lines.append(f"- Status: **Active**")
                lines.append(f"- Patterns: {fw_status.get('pattern_count', 0)}")
                lines.append(f"- Detections: {fw_status.get('detection_count', 0)}")
                lines.append(f"- Vault Entries: {fw_status.get('vault_entries', 0)}")
            else:
                lines.append(f"- Status: **Unavailable** ({PROMPT_FIREWALL_ERROR})")

            # Session Context
            if INTENT_GUARD_AVAILABLE:
                session = get_session_context()
                lines.append("\n### Session Context")
                if session.last_tool_output_untrusted:
                    lines.append(f"- **Warning:** Last output was from untrusted source")
                    lines.append(f"- Source: {session.last_untrusted_source_id}")
                else:
                    lines.append("- No untrusted content in current context")

            return [TextContent(type="text", text="\n".join(lines))]

        # Temporal tools (Phase 2)
        elif name == "duro_supersede_fact":
            old_fact_id = arguments["old_fact_id"]
            new_fact_id = arguments["new_fact_id"]
            reason = arguments.get("reason")

            success, msg = artifact_store.supersede_fact(old_fact_id, new_fact_id, reason)

            if success:
                text = f"✅ {msg}"
            else:
                text = f"❌ {msg}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_get_related":
            artifact_id = arguments["artifact_id"]
            relation_type = arguments.get("relation_type")
            direction = arguments.get("direction", "both")

            relations = artifact_store.index.get_relations(
                artifact_id,
                direction=direction,
                relation_type=relation_type
            )

            if not relations:
                text = f"No relations found for '{artifact_id}'."
            else:
                lines = [f"## Relations for {artifact_id}\n"]
                for rel in relations:
                    dir_icon = "→" if rel["direction"] == "outgoing" else "←"
                    other_id = rel["target_id"] if rel["direction"] == "outgoing" else rel["source_id"]
                    lines.append(f"- {dir_icon} **{rel['relation']}** {other_id}")
                    if rel.get("metadata"):
                        lines.append(f"  - {rel['metadata']}")
                text = "\n".join(lines)
            return [TextContent(type="text", text=text)]

        # Auto-capture & Proactive recall tools (Phase 3)
        elif name == "duro_proactive_recall":
            from proactive import ProactiveRecall

            context = arguments["context"]
            limit = arguments.get("limit", 10)
            include_types = arguments.get("include_types")
            force = arguments.get("force", False)

            # Create ProactiveRecall instance
            recall = ProactiveRecall(artifact_store, artifact_store.index)
            result = recall.recall(
                context=context,
                limit=limit,
                include_types=include_types,
                force=force
            )

            if not result.triggered:
                text = f"**Proactive Recall:** No relevant memories found.\n\nReason: {result.reason}"
            else:
                lines = [f"## Proactive Recall Results\n"]
                lines.append(f"**Categories matched:** {', '.join(result.categories_matched) or 'none'}")
                lines.append(f"**Search mode:** {result.search_mode}")
                lines.append(f"**Recall time:** {result.recall_time_ms}ms\n")

                if result.memories:
                    lines.append("### Relevant Memories\n")
                    for i, mem in enumerate(result.memories, 1):
                        score = round(mem.get("relevance_score", 0), 3)
                        lines.append(f"**{i}. [{mem['type']}]** {mem['summary'][:200]}")
                        lines.append(f"   - ID: `{mem['id']}`")
                        lines.append(f"   - Score: {score} | Tags: {', '.join(mem.get('tags', []))}\n")
                else:
                    lines.append("*No memories met the relevance threshold.*")

                text = "\n".join(lines)
            return [TextContent(type="text", text=text)]

        elif name == "duro_extract_learnings":
            from proactive import extract_learnings_from_text

            text_input = arguments["text"]
            auto_save = arguments.get("auto_save", False)

            result = extract_learnings_from_text(
                text=text_input,
                artifact_store=artifact_store if auto_save else None,
                auto_save=auto_save
            )

            lines = ["## Extracted Learnings\n"]
            lines.append(f"**Total items found:** {result['count']}")
            if auto_save:
                lines.append(f"**Auto-saved:** {len(result['saved_ids'])} artifacts\n")
            else:
                lines.append("*(Use auto_save=true to persist these)*\n")

            if result["learnings"]:
                lines.append("### Learnings\n")
                for i, learning in enumerate(result["learnings"], 1):
                    lines.append(f"{i}. {learning}")
                lines.append("")

            if result["facts"]:
                lines.append("### Facts\n")
                for fact in result["facts"]:
                    conf = fact.get("confidence", 0.5)
                    lines.append(f"- **{fact['claim'][:150]}** (confidence: {conf})")
                lines.append("")

            if result["decisions"]:
                lines.append("### Decisions\n")
                for dec in result["decisions"]:
                    lines.append(f"- **{dec['decision'][:100]}**")
                    lines.append(f"  - Rationale: {dec.get('rationale', '')[:100]}")
                lines.append("")

            if result['count'] == 0:
                lines.append("*No learnings, facts, or decisions detected in the text.*")

            text = "\n".join(lines)
            return [TextContent(type="text", text=text)]

        # Decay & Maintenance tools (Phase 4)
        elif name == "duro_apply_decay":
            from decay import apply_batch_decay, DecayConfig, DEFAULT_DECAY_CONFIG

            dry_run = arguments.get("dry_run", True)
            min_importance = arguments.get("min_importance", 0)
            include_stale_report = arguments.get("include_stale_report", True)

            # Load all facts
            facts = artifact_store.query(artifact_type="fact", limit=10000)
            full_facts = [artifact_store.get_artifact(f["id"]) for f in facts]
            full_facts = [f for f in full_facts if f is not None]

            # Filter by importance if specified
            if min_importance > 0:
                full_facts = [f for f in full_facts if f.get("data", {}).get("importance", 0.5) >= min_importance]

            # Apply decay
            result = apply_batch_decay(full_facts, DEFAULT_DECAY_CONFIG, dry_run=dry_run)

            # Save changes if not dry run
            if not dry_run:
                for fact in full_facts:
                    artifact_store._update_artifact_file(fact)

            lines = ["## Decay Results\n"]
            lines.append(f"**Mode:** {'DRY RUN' if dry_run else 'APPLIED'}")
            lines.append(f"**Total facts:** {result.total_facts}")
            lines.append(f"**Decayed:** {result.decayed_count}")
            lines.append(f"**Skipped (pinned):** {result.skipped_pinned}")
            lines.append(f"**Skipped (grace period):** {result.skipped_grace_period}")
            lines.append(f"**Skipped (reinforcement):** {result.skipped_reinforcement}")
            lines.append(f"**Now stale:** {result.stale_count}\n")

            if include_stale_report and result.stale_count > 0:
                lines.append("### Stale Facts (top 10)\n")
                stale = [r for r in result.results if r.get("stale")][:10]
                for s in stale:
                    lines.append(f"- `{s['id']}` conf: {s['new_confidence']:.3f} (was {s['old_confidence']:.3f})")

            text = "\n".join(lines)
            return [TextContent(type="text", text=text)]

        elif name == "duro_reembed":
            from embedding_worker import EmbeddingQueue
            import subprocess
            import time

            embedding_queue = EmbeddingQueue(MEMORY_DIR)
            artifact_ids = arguments.get("artifact_ids")
            artifact_type = arguments.get("artifact_type")
            all_artifacts = arguments.get("all", False)
            missing_only = arguments.get("missing_only", False)
            limit = arguments.get("limit", 100)
            timeout_seconds = arguments.get("timeout_seconds", 120)

            # Get before metrics
            caps = artifact_store.index.get_search_capabilities()
            before_metrics = {
                "embedding_count": caps.get("embedding_count", 0),
                "artifacts_count": artifact_store.index.count(),
                "pending_queue": embedding_queue.get_pending_count()
            }

            # Get code version (git sha)
            try:
                code_version = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=Path(__file__).parent,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
            except Exception:
                code_version = "unknown"

            # Collect artifact IDs to process
            to_process = []
            trigger = "manual"

            if artifact_ids:
                # Specific IDs
                to_process = artifact_ids
                trigger = f"explicit_ids:{len(artifact_ids)}"
            elif artifact_type:
                # All of a type
                results = artifact_store.query(artifact_type=artifact_type, limit=10000)
                to_process = [r["id"] for r in results]
                trigger = f"artifact_type:{artifact_type}"
            elif all_artifacts:
                # Everything
                results = artifact_store.query(limit=10000)
                to_process = [r["id"] for r in results]
                trigger = "all_artifacts"
            elif missing_only:
                # Only missing embeddings
                to_process = artifact_store.index.get_missing_embedding_ids(limit=limit)
                trigger = f"missing_only:{len(to_process)}"
            else:
                return [TextContent(type="text", text="No artifacts specified. Use artifact_ids, artifact_type, missing_only=true, or all=true.")]

            # Filter to missing only if requested (for type/all queries)
            if missing_only and not artifact_ids:
                existing_ids = set(artifact_store.index.get_embedded_artifact_ids())
                to_process = [aid for aid in to_process if aid not in existing_ids]
                trigger += "+missing_only"

            # Apply limit
            original_count = len(to_process)
            if limit and len(to_process) > limit:
                to_process = to_process[:limit]
                trigger += f"+limit:{limit}"

            # Start repair log
            repair_id = artifact_store.index.start_repair(
                repair_type="embed_backfill",
                trigger=trigger,
                before_metrics=before_metrics,
                missing_ids=to_process[:100],  # Cap logged IDs
                code_version=code_version
            )

            # Crash-proof repair logging with try/finally
            embedded = 0
            failed = 0
            skipped = 0
            cleared = 0
            timed_out = False
            error_blob = None
            repair_result = "success"
            start_time = time.time()

            try:
                total = len(to_process)
                for i, aid in enumerate(to_process):
                    # Check timeout
                    elapsed = time.time() - start_time
                    if elapsed > timeout_seconds:
                        timed_out = True
                        error_blob = f"Timeout after {timeout_seconds}s at {i}/{total}"
                        repair_result = "partial"
                        break

                    # Cooperative cancellation check (every 25 items)
                    if i > 0 and i % 25 == 0:
                        if is_cancelled("reembed"):
                            error_blob = f"Cancelled by user at {i}/{total}"
                            repair_result = "cancelled"
                            log_info(f"[duro_reembed] Cancellation requested at {i}/{total}")
                            break
                        # Progress output
                        log_info(f"[duro_reembed] Progress: {i}/{total} ({embedded} embedded, {failed} failed, {elapsed:.1f}s)")

                    try:
                        result = _embed_artifact_sync(aid)
                        if result:
                            embedded += 1
                        else:
                            # Check if artifact exists - if not, skip; if yes, mark as failed
                            artifact = artifact_store.get_artifact(aid)
                            if artifact:
                                failed += 1
                            else:
                                skipped += 1
                    except Exception as item_err:
                        failed += 1
                        log_warn(f"[duro_reembed] Error on {aid}: {item_err}")

                # Clear any pending items from queue (they're now processed)
                cleared = embedding_queue.clear_queue()

                if failed > 0 and repair_result == "success":
                    repair_result = "partial"

            except Exception as e:
                repair_result = "failed"
                error_blob = repr(e)
                raise

            finally:
                # Clear cancellation flag (important: even on crash)
                clear_cancel("reembed")

                # Always complete the repair log, even on crash
                caps_after = artifact_store.index.get_search_capabilities()
                after_metrics = {
                    "embedding_count": caps_after.get("embedding_count", 0),
                    "artifacts_count": artifact_store.index.count(),
                    "pending_queue": embedding_queue.get_pending_count()
                }
                artifact_store.index.complete_repair(
                    repair_id=repair_id,
                    after_metrics=after_metrics,
                    processed_count=embedded,
                    failed_count=failed,
                    canonical_mutations=0,  # Embeddings never mutate canonical
                    result=repair_result,
                    error_blob=error_blob
                )

            elapsed = time.time() - start_time
            lines = [f"## Re-embed {'Partial' if timed_out else 'Complete'}"]
            lines.append(f"\n**Processed:** {embedded + failed + skipped}/{len(to_process)} artifacts")
            if original_count > len(to_process):
                lines.append(f"**Note:** Limited from {original_count} to {len(to_process)}")
            lines.append(f"- Embedded: {embedded}")
            lines.append(f"- Failed: {failed}")
            lines.append(f"- Skipped (not found): {skipped}")
            lines.append(f"- Time: {elapsed:.1f}s")
            if timed_out:
                lines.append(f"- **Timed out** after {timeout_seconds}s")
            lines.append(f"- Pending queue cleared: {cleared}")
            lines.append(f"- Repair logged: #{repair_id}")
            text = "\n".join(lines)
            return [TextContent(type="text", text=text)]

        elif name == "duro_prune_orphans":
            import time
            import subprocess

            dry_run = arguments.get("dry_run", False)
            max_delete = arguments.get("max_delete")

            # Count orphans first
            orphan_count = artifact_store.index.count_orphan_embeddings()
            orphan_ids = artifact_store.index.list_orphan_embeddings(limit=10)

            if orphan_count == 0:
                return [TextContent(type="text", text="## No Orphans\n\nNo orphan embeddings found.")]

            if dry_run:
                lines = [f"## Orphan Embeddings (Dry Run)"]
                lines.append(f"\n**Found:** {orphan_count} orphan(s)")
                lines.append(f"\n**Sample IDs:**")
                for oid in orphan_ids[:10]:
                    if oid:  # Guard against None
                        lines.append(f"- `{oid}`")
                lines.append(f"\nRun with `dry_run=false` to delete.")
                if orphan_count > 1000:
                    lines.append(f"**Tip:** Use `max_delete=1000` for batched cleanup.")
                return [TextContent(type="text", text="\n".join(lines))]

            # Get code version (git sha)
            try:
                code_version = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=Path(__file__).parent,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
            except Exception:
                code_version = "unknown"

            # Start repair log
            repair_id = artifact_store.index.start_repair(
                repair_type="prune_orphans",
                trigger="manual" if max_delete is None else f"manual+batch:{max_delete}",
                before_metrics={"orphan_count": orphan_count, "max_delete": max_delete},
                missing_ids=orphan_ids[:50],
                code_version=code_version
            )

            start_time = time.time()
            result = artifact_store.index.prune_orphan_embeddings(max_delete=max_delete)
            elapsed = time.time() - start_time

            # Use remaining from result (already computed)
            after_orphan_count = result.get("remaining", 0)

            # Complete repair log
            artifact_store.index.complete_repair(
                repair_id=repair_id,
                after_metrics={"orphan_count": after_orphan_count},
                processed_count=result.get("count", 0),
                failed_count=1 if "error" in result else 0,
                canonical_mutations=0,  # Embeddings never mutate canonical
                result="success" if "error" not in result else "failed",
                error_blob=result.get("error")
            )

            lines = [f"## Orphan Embeddings Pruned"]
            lines.append(f"\n**Deleted:** {result.get('count', 0)} orphan(s)")
            remaining_str = str(after_orphan_count) if after_orphan_count >= 0 else "unknown (error)"
            lines.append(f"**Remaining:** {remaining_str}")
            lines.append(f"**Time:** {elapsed:.2f}s")
            lines.append(f"**Repair logged:** #{repair_id}")
            if result.get("pruned_ids"):
                lines.append(f"\n**Pruned IDs (first 10):**")
                for oid in result["pruned_ids"][:10]:
                    if oid:  # Guard against None
                        lines.append(f"- `{oid}`")
            if after_orphan_count > 0:
                lines.append(f"\n**Note:** {after_orphan_count} orphan(s) remaining. Run again to continue.")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_maintenance_report":
            from decay import generate_maintenance_report, DEFAULT_DECAY_CONFIG

            include_stale_list = arguments.get("include_stale_list", True)
            top_n_stale = arguments.get("top_n_stale", 10)

            # Load all facts
            facts = artifact_store.query(artifact_type="fact", limit=10000)
            full_facts = [artifact_store.get_artifact(f["id"]) for f in facts]
            full_facts = [f for f in full_facts if f is not None]

            # Generate report
            report = generate_maintenance_report(full_facts, DEFAULT_DECAY_CONFIG, top_n_stale)

            # Get embedding/FTS coverage
            fts_stats = artifact_store.index.get_fts_completeness()
            emb_stats = artifact_store.index.get_embedding_stats()

            lines = ["## Maintenance Report\n"]
            lines.append("### Fact Health\n")
            lines.append(f"- **Total facts:** {report.total_facts}")
            lines.append(f"- **Pinned:** {report.pinned_count} ({report.pinned_pct}%)")
            lines.append(f"- **Stale:** {report.stale_count} ({report.stale_pct}%)")
            lines.append(f"- **Avg confidence:** {report.avg_confidence}")
            lines.append(f"- **Avg importance:** {report.avg_importance}")
            lines.append(f"- **Avg reinforcement count:** {report.avg_reinforcement_count}")
            lines.append(f"- **Oldest unreinforced:** {report.oldest_unreinforced_days} days\n")

            lines.append("### Index Coverage\n")
            fts_coverage = fts_stats.get("coverage_pct", 0)
            emb_coverage = emb_stats.get("coverage_pct", 0)
            lines.append(f"- **FTS coverage:** {fts_coverage}%")
            lines.append(f"- **Embedding coverage:** {emb_coverage}%\n")

            if include_stale_list and report.top_stale_high_importance:
                lines.append("### Top Stale High-Importance Facts\n")
                for fact in report.top_stale_high_importance:
                    lines.append(f"- `{fact['id']}` imp={fact['importance']}, conf={fact['confidence']:.3f}")
                    lines.append(f"  - {fact['claim'][:80]}...")
                    lines.append(f"  - Inactive: {fact['days_inactive']} days")

            text = "\n".join(lines)
            return [TextContent(type="text", text=text)]

        elif name == "duro_reinforce_fact":
            from decay import reinforce_fact

            fact_id = arguments["fact_id"]
            fact = artifact_store.get_artifact(fact_id)

            if not fact:
                return [TextContent(type="text", text=f"Fact not found: {fact_id}")]

            if fact.get("type") != "fact":
                return [TextContent(type="text", text=f"Artifact {fact_id} is not a fact (type: {fact.get('type')})")]

            # Reinforce
            updated_fact = reinforce_fact(fact)
            artifact_store._update_artifact_file(updated_fact)

            data = updated_fact.get("data", {})
            text = f"## Fact Reinforced\n\n- **ID:** `{fact_id}`\n- **Reinforcement count:** {data.get('reinforcement_count', 0)}\n- **Last reinforced:** {data.get('last_reinforced_at')}"
            return [TextContent(type="text", text=text)]

        # Artifact tools
        elif name == "duro_store_fact":
            success, artifact_id, path = artifact_store.store_fact(
                claim=arguments["claim"],
                source_urls=arguments.get("source_urls"),
                snippet=arguments.get("snippet"),
                confidence=arguments.get("confidence", 0.5),
                tags=arguments.get("tags"),
                workflow=arguments.get("workflow", "manual"),
                sensitivity=arguments.get("sensitivity", "public"),
                evidence_type=arguments.get("evidence_type", "none"),
                provenance=arguments.get("provenance", "unknown")
            )
            if success:
                # Embed synchronously for immediate vector search
                _embed_artifact_sync(artifact_id)
                text = f"Fact stored successfully.\n- ID: {artifact_id}\n- Path: {path}"
            else:
                text = f"Failed to store fact: {path}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_store_decision":
            success, artifact_id, path = artifact_store.store_decision(
                decision=arguments["decision"],
                rationale=arguments["rationale"],
                alternatives=arguments.get("alternatives"),
                context=arguments.get("context"),
                reversible=arguments.get("reversible", True),
                tags=arguments.get("tags"),
                workflow=arguments.get("workflow", "manual"),
                sensitivity=arguments.get("sensitivity", "internal")
            )
            if success:
                # Embed synchronously for immediate vector search
                _embed_artifact_sync(artifact_id)
                text = f"Decision stored successfully.\n- ID: {artifact_id}\n- Path: {path}"
            else:
                text = f"Failed to store decision: {path}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_validate_decision":
            # Helper: schema-resilient status lookup
            def _decision_status(d: dict | None) -> str | None:
                if not d:
                    return None
                data = d.get("data", {})
                return (
                    d.get("status")
                    or data.get("status")
                    or data.get("validation", {}).get("status")
                    or data.get("outcome", {}).get("status")
                    or data.get("outcome", {}).get("validation_status")
                )

            # Fetch previous status before update (for promotion feeder transition check)
            prev_decision = artifact_store.get_artifact(arguments["decision_id"])
            prev_status = _decision_status(prev_decision)

            success, message, validation_id = artifact_store.validate_decision(
                decision_id=arguments["decision_id"],
                status=arguments["status"],
                episode_id=arguments.get("episode_id"),
                result=arguments.get("result"),
                notes=arguments.get("notes"),
                expected_outcome=arguments.get("expected_outcome"),
                actual_outcome=arguments.get("actual_outcome"),
                next_action=arguments.get("next_action"),
                confidence_delta=arguments.get("confidence_delta")
            )
            if success:
                # === Autonomy: handle reopen event for reversals ===
                autonomy_msg = ""
                if arguments["status"] == "reversed" and AUTONOMY_AVAILABLE:
                    try:
                        from autonomy_ladder import handle_reopen_event
                        # Get the decision to find linked action ID
                        decision = artifact_store.get_artifact(arguments["decision_id"])
                        linked_action = None
                        if decision and decision.get("data", {}).get("linked_episodes"):
                            # Use first episode as proxy for action ID
                            linked_action = decision["data"]["linked_episodes"][0]
                        reopen_result = handle_reopen_event(
                            artifact_type="decision",
                            artifact_id=arguments["decision_id"],
                            linked_action_id=linked_action
                        )
                        if reopen_result.get("cancelled"):
                            autonomy_msg = "\n- Autonomy: cancelled pending reward, penalty applied"
                        elif reopen_result.get("penalty_applied"):
                            autonomy_msg = "\n- Autonomy: reopen penalty applied to reputation"
                    except Exception as e:
                        autonomy_msg = f"\n- Autonomy: reopen hook error: {e}"

                # Get updated decision to show new confidence
                decision = artifact_store.get_artifact(arguments["decision_id"])
                confidence = decision["data"]["outcome"]["confidence"] if decision else "?"
                status_icon = {"validated": "✓", "reversed": "✗", "superseded": "→"}.get(arguments["status"], "?")
                text = f"Decision validated.\n- ID: `{arguments['decision_id']}`\n- Status: {status_icon} {arguments['status']}\n- Confidence: {confidence}"
                if validation_id:
                    text += f"\n- Validation event: `{validation_id}`"
                    # Embed the validation event
                    _embed_artifact_sync(validation_id)
                if arguments.get("episode_id"):
                    text += f"\n- Evidence: episode `{arguments['episode_id']}`"
                if arguments.get("next_action"):
                    text += f"\n- Next action: {arguments['next_action']}"
                text += autonomy_msg

                # === Promotion feeder: validated decisions become promotion candidates ===
                # Only feed on STATUS TRANSITION to validated (prevents double-counting)
                post_status = _decision_status(decision)
                is_transition = prev_status != "validated" and post_status == "validated"
                if is_transition and COMPACTOR_AVAILABLE and decision:
                    try:
                        decision_tags = decision.get("tags", [])
                        decision_data = decision.get("data", {})

                        # Check if this prevented a failure (reliability/incident tags)
                        failure_prevention_tags = {"reliability", "incident", "fix", "postmortem", "security", "bug"}
                        prevented_failure = bool(set(decision_tags) & failure_prevention_tags)

                        # Map PromotionType based on tags
                        law_tags = {"security", "policy", "gate", "constraint", "rule", "architecture"}
                        pattern_tags = {"workflow", "process", "tactic", "pattern"}
                        if set(decision_tags) & law_tags:
                            promo_type = PromotionType.PREFERENCE_TO_LAW
                        elif set(decision_tags) & pattern_tags:
                            promo_type = PromotionType.TACTIC_TO_PATTERN
                        else:
                            promo_type = PromotionType.PREFERENCE_TO_LAW  # default

                        # Create observation content from decision
                        observation_content = {
                            "decision": decision_data.get("decision", ""),
                            "rationale": decision_data.get("rationale", ""),
                            "domain": decision_tags[0] if decision_tags else "general"
                        }

                        record_observation(
                            content=observation_content,
                            promotion_type=promo_type,
                            source_decisions=[arguments["decision_id"]],
                            user_endorsed=True,  # validation = endorsement
                            prevented_failure=prevented_failure
                        )
                        text += f"\n- Promotion: observation recorded ({promo_type.value})"
                    except Exception as e:
                        log_warn(f"Promotion feeder failed: {e}")
            else:
                text = f"Failed to validate decision: {message}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_link_decision":
            success, message = artifact_store.link_decision_to_episode(
                decision_id=arguments["decision_id"],
                episode_id=arguments["episode_id"]
            )
            if success:
                text = f"Decision linked to episode.\n- Decision: `{arguments['decision_id']}`\n- Episode: `{arguments['episode_id']}`"
            else:
                text = f"Failed to link decision: {message}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_list_unreviewed_decisions":
            older_than_days = arguments.get("older_than_days", 14)
            decisions = artifact_store.list_unreviewed_decisions(
                older_than_days=older_than_days,
                exclude_tags=arguments.get("exclude_tags"),
                include_tags=arguments.get("include_tags"),
                limit=arguments.get("limit", 20)
            )

            if not decisions:
                # Helpful message with suggestions
                text = f"## No Unreviewed Decisions Found\n\n"
                text += f"No decisions older than {older_than_days} days match the criteria.\n\n"
                if older_than_days > 7:
                    text += f"**Try:** `duro_list_unreviewed_decisions(older_than_days=7)` to see more recent decisions.\n"
                text += "\nAll decisions may have been reviewed, or they may be too recent to need review yet."
            else:
                lines = [f"## Unreviewed Decisions ({len(decisions)} found)\n"]
                for d in decisions:
                    status_icon = "⏳" if d["needs_review"] else "✓"
                    tags_str = ", ".join(d["tags"][:3]) if d["tags"] else "none"
                    lines.append(f"### {status_icon} `{d['id']}`")
                    lines.append(f"**Decision:** {d['decision']}")
                    lines.append(f"- **Age:** {d['age_days']} days")
                    lines.append(f"- **Status:** {d['status']} (confidence: {d['confidence']})")
                    lines.append(f"- **Tags:** {tags_str}")
                    lines.append(f"- **Linked:** {d['linked_episodes_count']} episodes, {d.get('linked_incidents_count', 0)} incidents")
                    if d["last_validated_at"]:
                        lines.append(f"- **Last validated:** {d['last_validated_at']}")
                    # Action-ready next step
                    lines.append(f"\n**Next:** `duro_validate_decision(decision_id=\"{d['id']}\", status=\"validated\", result=\"success\", notes=\"...\")`")
                    lines.append("")
                text = "\n".join(lines)
            return [TextContent(type="text", text=text)]

        elif name == "duro_get_validation_history":
            decision_id = arguments["decision_id"]
            # First verify decision exists
            decision = artifact_store.get_artifact(decision_id)
            if not decision:
                text = f"Decision `{decision_id}` not found."
            elif decision.get("type") != "decision":
                text = f"Artifact `{decision_id}` is not a decision."
            else:
                history = artifact_store.get_validation_history(decision_id)
                if not history:
                    text = f"## Validation History for `{decision_id}`\n\n"
                    text += "No validations recorded yet.\n\n"
                    text += f"**Decision:** {decision['data'].get('decision', 'Unknown')}\n"
                    text += f"**Current status:** {decision['data'].get('outcome', {}).get('status', 'unverified')}\n"
                else:
                    lines = [f"## Validation History for `{decision_id}`\n"]
                    lines.append(f"**Decision:** {decision['data'].get('decision', 'Unknown')}\n")
                    lines.append(f"**{len(history)} validation(s):**\n")
                    for v in history:
                        vdata = v.get("data", {})
                        status_icon = {"validated": "✓", "reversed": "✗", "superseded": "→"}.get(vdata.get("status"), "?")
                        lines.append(f"### {status_icon} {vdata.get('status', '?')} - {v['created_at'][:10]}")
                        lines.append(f"- **ID:** `{v['id']}`")
                        if vdata.get("result"):
                            lines.append(f"- **Result:** {vdata['result']}")
                        if vdata.get("confidence_delta") is not None:
                            delta = vdata["confidence_delta"]
                            delta_str = f"+{delta}" if delta > 0 else str(delta)
                            lines.append(f"- **Confidence delta:** {delta_str} → {vdata.get('confidence_after', '?')}")
                        if vdata.get("expected_outcome"):
                            lines.append(f"- **Expected:** {vdata['expected_outcome']}")
                        if vdata.get("actual_outcome"):
                            lines.append(f"- **Actual:** {vdata['actual_outcome']}")
                        if vdata.get("next_action"):
                            lines.append(f"- **Next action:** {vdata['next_action']}")
                        if vdata.get("notes"):
                            lines.append(f"- **Notes:** {vdata['notes']}")
                        if vdata.get("episode_id"):
                            lines.append(f"- **Episode:** `{vdata['episode_id']}`")
                        lines.append("")
                    text = "\n".join(lines)
            return [TextContent(type="text", text=text)]

        elif name == "duro_review_decision":
            decision_id = arguments["decision_id"]
            dry_run = arguments.get("dry_run", True)

            # Get context pack
            ctx = artifact_store.get_decision_review_context(
                decision_id=decision_id,
                hours_recent_changes=arguments.get("hours_recent_changes", 48),
                risk_tags=arguments.get("risk_tags")
            )

            if "error" in ctx:
                return [TextContent(type="text", text=f"Error: {ctx['error']}")]

            lines = []

            # === SECTION 1: Decision Core ===
            d = ctx["decision"]
            lines.append(f"# Decision Review: `{decision_id}`\n")
            lines.append("## 1. Decision Core\n")
            lines.append(f"**Decision:** {d['decision'][:200]}")
            if d['rationale']:
                lines.append(f"\n**Rationale:** {d['rationale'][:200]}")
            lines.append(f"\n- **Created:** {d['created_at'][:10]} ({d['age_days']} days ago)")
            lines.append(f"- **Tags:** {', '.join(d['tags']) if d['tags'] else 'none'}")
            lines.append(f"- **Current status:** {d['outcome_status']} (confidence: {d['outcome_confidence']})")
            if d['verified_at']:
                lines.append(f"- **Last verified:** {d['verified_at'][:10]}")
            lines.append("")

            # === SECTION 2: Validation Timeline ===
            lines.append("## 2. Validation Timeline\n")
            if not ctx["validation_history"]:
                lines.append("*No validations recorded yet.*\n")
            else:
                lines.append(f"*{ctx['validation_count']} total validation(s), showing last {len(ctx['validation_history'])}:*\n")
                for v in ctx["validation_history"]:
                    vdata = v.get("data", {})
                    status_icon = {"validated": "✓", "reversed": "✗", "superseded": "→"}.get(vdata.get("status"), "?")
                    delta = vdata.get("confidence_delta")
                    delta_str = f"+{delta}" if delta and delta > 0 else str(delta) if delta else ""
                    notes = vdata.get("notes", "")[:60] + "..." if len(vdata.get("notes", "")) > 60 else vdata.get("notes", "")
                    lines.append(f"- {status_icon} **{vdata.get('status', '?')}** ({v['created_at'][:10]}) - {delta_str} → {vdata.get('confidence_after', '?')}")
                    if notes:
                        lines.append(f"  _{notes}_")
            lines.append("")

            # === SECTION 3: Linked Work Evidence ===
            lines.append("## 3. Linked Work Evidence\n")
            lines.append(f"**Episodes:** {ctx['linked_episodes_count']} total")
            if ctx["linked_episodes"]:
                for ep in ctx["linked_episodes"]:
                    result_icon = {"success": "✓", "partial": "~", "failed": "✗"}.get(ep.get("result"), "?")
                    lines.append(f"  - {result_icon} `{ep['id']}` - {ep['goal']}")
            else:
                lines.append("  *None linked*")

            lines.append(f"\n**Incidents:** {ctx['linked_incidents_count']} total")
            if ctx["linked_incidents"]:
                for inc in ctx["linked_incidents"]:
                    sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(inc.get("severity"), "⚪")
                    lines.append(f"  - {sev_icon} `{inc['id']}` - {inc['symptom']}")
            else:
                lines.append("  *None linked*")
            lines.append("")

            # === SECTION 4: Recent Changes Scan ===
            lines.append("## 4. Recent Changes (48-hour scan)\n")
            if ctx.get("risk_tags_used"):
                lines.append(f"*Risk tags: {', '.join(ctx['risk_tags_used'])}*\n")
            if not ctx["recent_changes"]:
                lines.append("*No recent changes found.*")
            else:
                for chg in ctx["recent_changes"][:5]:
                    scope = chg.get("scope", "")
                    change = chg.get("change", "")[:60]
                    lines.append(f"- `{chg['id']}` [{scope}] {change}")
                lines.append("\n*Link any suspects in your validation notes/next_action.*")
            lines.append("")

            # === REVIEW TEMPLATE (the discipline installer) ===
            lines.append("---")
            lines.append("## Review Template\n")
            lines.append("Fill these fields to validate:\n")
            lines.append("- **Expected outcome:** (what was this decision supposed to achieve?)")
            lines.append("- **Actual outcome:** (what actually happened?)")
            lines.append("- **Verdict:**")
            lines.append("  - status: `validated` / `reversed` / `superseded`")
            lines.append("  - result: `success` / `partial` / `failed`")
            lines.append("- **Next action:** (one concrete action)")
            lines.append("- **Confidence delta:** (-0.2 to +0.2 recommended)")
            lines.append("- **Notes:** (optional)")
            lines.append("")

            # === DRY RUN vs EXECUTE ===
            if dry_run:
                lines.append("---")
                lines.append("*dry_run=true: showing context only.*")
                lines.append(f"\n**To validate:** `duro_review_decision(decision_id=\"{decision_id}\", dry_run=false, status=\"validated\", result=\"success\", expected_outcome=\"...\", actual_outcome=\"...\", next_action=\"...\", notes=\"...\")`")
            else:
                # Validate the decision
                status = arguments.get("status")
                if not status:
                    lines.append("---")
                    lines.append("**Error:** `status` is required when dry_run=false")
                    return [TextContent(type="text", text="\n".join(lines))]

                result = arguments.get("result")
                expected_outcome = arguments.get("expected_outcome")
                actual_outcome = arguments.get("actual_outcome")
                next_action = arguments.get("next_action")
                confidence_delta = arguments.get("confidence_delta")
                notes = arguments.get("notes")

                # Soft guardrails
                warnings = []
                if not next_action and result and result != "success":
                    warnings.append("⚠️ Recording a failure without a next_action.")
                if status == "superseded" and not notes:
                    warnings.append("⚠️ Superseding without mentioning the replacement in notes.")
                if confidence_delta is not None:
                    confidence_delta = max(-0.5, min(0.5, confidence_delta))

                # Call validate_decision
                success, msg, validation_id = artifact_store.validate_decision(
                    decision_id=decision_id,
                    status=status,
                    result=result,
                    expected_outcome=expected_outcome,
                    actual_outcome=actual_outcome,
                    next_action=next_action,
                    confidence_delta=confidence_delta,
                    notes=notes
                )

                lines.append("---")
                if success:
                    lines.append("## ✓ Validation Recorded\n")
                    lines.append(f"- **Status:** {status}")
                    if result:
                        lines.append(f"- **Result:** {result}")
                    if validation_id:
                        lines.append(f"- **Validation ID:** `{validation_id}`")
                        _embed_artifact_sync(validation_id)
                    if next_action:
                        lines.append(f"- **Next action:** {next_action}")
                    if warnings:
                        lines.append("\n**Warnings:**")
                        for w in warnings:
                            lines.append(f"  {w}")
                else:
                    lines.append(f"## ✗ Validation Failed\n\n{msg}")

            text = "\n".join(lines)
            return [TextContent(type="text", text=text)]

        elif name == "duro_review_next_decisions":
            n = arguments.get("n", 3)
            older_than_days = arguments.get("older_than_days", 14)
            include_tags = arguments.get("include_tags")
            exclude_tags = arguments.get("exclude_tags")

            # Get unreviewed decisions
            decisions = artifact_store.list_unreviewed_decisions(
                older_than_days=older_than_days,
                include_tags=include_tags,
                exclude_tags=exclude_tags,
                limit=n
            )

            if not decisions:
                text = f"## No Decisions to Review\n\nNo unreviewed decisions older than {older_than_days} days found."
                if older_than_days > 7:
                    text += f"\n\n**Try:** `duro_review_next_decisions(older_than_days=7)` for more recent decisions."
                return [TextContent(type="text", text=text)]

            lines = [f"# Review Queue: {len(decisions)} Decision(s)\n"]
            lines.append(f"*Showing top {len(decisions)} unreviewed decisions (older than {older_than_days} days)*\n")

            for i, dec in enumerate(decisions, 1):
                lines.append(f"---\n## [{i}/{len(decisions)}] `{dec['id']}`\n")

                # Get full context for each
                ctx = artifact_store.get_decision_review_context(
                    decision_id=dec["id"],
                    hours_recent_changes=48
                )

                if "error" in ctx:
                    lines.append(f"*Error loading context: {ctx['error']}*\n")
                    continue

                d = ctx["decision"]
                lines.append(f"**Decision:** {d['decision'][:150]}")
                lines.append(f"\n- **Age:** {d['age_days']} days | **Status:** {d['outcome_status']} | **Confidence:** {d['outcome_confidence']}")
                lines.append(f"- **Validations:** {ctx['validation_count']} | **Episodes:** {ctx['linked_episodes_count']} | **Incidents:** {ctx['linked_incidents_count']}")
                lines.append(f"- **Tags:** {', '.join(d['tags'][:3]) if d['tags'] else 'none'}")

                # Quick validation command
                lines.append(f"\n**Review:** `duro_review_decision(decision_id=\"{dec['id']}\", dry_run=true)`")
                lines.append("")

            lines.append("---")
            lines.append("\n*Pick one and run `duro_review_decision` with `dry_run=false` to validate.*")

            text = "\n".join(lines)
            return [TextContent(type="text", text=text)]

        # Incident & Change Ledger handlers
        elif name == "duro_store_incident":
            success, artifact_id, path = artifact_store.store_incident(
                symptom=arguments["symptom"],
                actual_cause=arguments["actual_cause"],
                fix=arguments["fix"],
                trigger=arguments.get("trigger"),
                first_bad_boundary=arguments.get("first_bad_boundary"),
                why_not_caught=arguments.get("why_not_caught"),
                prevention=arguments.get("prevention"),
                related_recent_changes=arguments.get("related_recent_changes"),
                # Debug Gate fields
                repro_steps=arguments.get("repro_steps"),
                recent_change_scan=arguments.get("recent_change_scan"),
                override=arguments.get("override", False),
                override_reason=arguments.get("override_reason"),
                # Standard fields
                severity=arguments.get("severity", "medium"),
                tags=arguments.get("tags"),
                workflow="debug_rca"
            )
            if success:
                _embed_artifact_sync(artifact_id)
                override_note = " **[GATE OVERRIDDEN]**" if arguments.get("override") else ""
                text = f"## Incident RCA Stored{override_note}\n\n- **ID:** `{artifact_id}`\n- **Symptom:** {arguments['symptom'][:80]}...\n- **Cause:** {arguments['actual_cause'][:80]}...\n- **Fix:** {arguments['fix'][:80]}..."
                if arguments.get("prevention"):
                    text += f"\n- **Prevention:** {arguments['prevention'][:80]}..."
                if arguments.get("override"):
                    text += f"\n- **Override Reason:** {arguments.get('override_reason', 'N/A')}"
            elif artifact_id == "GATE_BLOCKED":
                # Gate blocked - return helpful failure message
                text = f"## Debug Gate Blocked\n\n{path}"
            elif artifact_id == "OVERRIDE_REQUIRES_REASON":
                text = f"## Override Requires Reason\n\n{path}"
            else:
                text = f"Failed to store incident: {path}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_debug_gate_start":
            # Start a debug session with gate prompts
            symptom = arguments["symptom"]
            tags = arguments.get("tags", [])

            # Infer risk tags for 48-hour scan
            risk_tag_candidates = ["config", "db", "paths", "sync", "deploy", "auth", "caching", "env", "permissions", "network", "state", "api", "schema"]
            inferred_risk_tags = [t for t in tags if t in risk_tag_candidates]
            if not inferred_risk_tags:
                inferred_risk_tags = ["config", "env", "paths"]

            # Run 48-hour scan
            results = artifact_store.query_recent_changes(hours=48, risk_tags=inferred_risk_tags, limit=20)

            text = f"""## Debug Gate Started

**Symptom:** {symptom}

---

### Pass 1: Repro
Fill in `repro_steps` with at least 2 steps to reproduce:
```
repro_steps: [
  "Step 1: ...",
  "Step 2: ..."
]
```

---

### Pass 2: Boundary
Fill in `first_bad_boundary` - where does good become bad?
- Config path / env var?
- API response / network call?
- DB read/write / migration?
- Service startup / container / deploy step?

---

### Pass 3: Causality (48-Hour Scan)

**Recent changes (last 48h, tags: {', '.join(inferred_risk_tags)}):**
"""
            if results:
                for r in results:
                    text += f"\n- `{r['id']}`: {r['change'][:60]}... (risk: {', '.join(r.get('risk_tags', []))})"
                text += f"\n\nLink relevant changes via `related_recent_changes` or provide `cleared_reason` if none apply."
            else:
                text += "\nNo recent changes found. Provide `cleared_reason` to confirm none are related."

            text += """

---

### Prevention
Must be **actionable** (verb + artifact):
- "Add startup log of X"
- "Assert Y exists before continuing"
- "Add smoke test that fails if Z"

**Banned:** "be careful", "remember to", "double check"

---

When ready, call `duro_store_incident` with all fields."""

            return [TextContent(type="text", text=text)]

        elif name == "duro_debug_gate_status":
            # Check status of a draft incident
            incident_id = arguments["incident_id"]
            artifact = artifact_store.get_artifact(incident_id)

            if not artifact:
                return [TextContent(type="text", text=f"Incident not found: {incident_id}")]

            if artifact.get("type") != "incident_rca":
                return [TextContent(type="text", text=f"Not an incident: {incident_id}")]

            data = artifact.get("data", {})
            tags = artifact.get("tags", [])

            # Run validation
            gate_passed, failures = artifact_store._validate_debug_gate(
                repro_steps=data.get("repro_steps"),
                first_bad_boundary=data.get("first_bad_boundary"),
                prevention=data.get("prevention"),
                recent_change_scan=data.get("recent_change_scan"),
                tags=tags
            )

            status = data.get("status", "draft")
            override = data.get("override", False)

            if gate_passed:
                text = f"## Debug Gate Status: PASSED ✓\n\n**Incident:** `{incident_id}`\n**Status:** {status}"
            elif override:
                text = f"## Debug Gate Status: OVERRIDDEN\n\n**Incident:** `{incident_id}`\n**Status:** {status}\n**Override Reason:** {data.get('override_reason', 'N/A')}"
            else:
                text = f"## Debug Gate Status: BLOCKED\n\n**Incident:** `{incident_id}`\n**Status:** {status}\n\n**Missing:**\n"
                for f in failures:
                    text += f"• {f}\n"

            return [TextContent(type="text", text=text)]

        elif name == "duro_store_change":
            success, artifact_id, path = artifact_store.store_recent_change(
                scope=arguments["scope"],
                change=arguments["change"],
                why=arguments.get("why"),
                risk_tags=arguments.get("risk_tags"),
                quick_checks=arguments.get("quick_checks"),
                commit_hash=arguments.get("commit_hash"),
                tags=arguments.get("tags"),
                workflow="change_ledger"
            )
            if success:
                _embed_artifact_sync(artifact_id)
                risk_str = ", ".join(arguments.get("risk_tags", [])) or "none"
                text = f"## Change Logged\n\n- **ID:** `{artifact_id}`\n- **Scope:** {arguments['scope']}\n- **Change:** {arguments['change']}\n- **Risk tags:** {risk_str}"
            else:
                text = f"Failed to store change: {path}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_query_recent_changes":
            hours = arguments.get("hours", 48)
            risk_tags = arguments.get("risk_tags")
            scope = arguments.get("scope")
            limit = arguments.get("limit", 20)

            results = artifact_store.query_recent_changes(
                hours=hours,
                risk_tags=risk_tags,
                scope=scope,
                limit=limit
            )

            if results:
                text = f"## Recent Changes (last {hours}h)\n\n"
                for r in results:
                    risk_str = ", ".join(r.get("risk_tags", [])) or "none"
                    text += f"### `{r['id']}`\n"
                    text += f"- **Scope:** {r['scope']}\n"
                    text += f"- **Change:** {r['change']}\n"
                    text += f"- **Risk tags:** {risk_str}\n"
                    text += f"- **When:** {r['created_at']}\n"
                    if r.get("quick_checks"):
                        text += f"- **Quick checks:** {', '.join(r['quick_checks'])}\n"
                    text += "\n"
            else:
                text = f"No changes found in the last {hours} hours."
            return [TextContent(type="text", text=text)]

        elif name == "duro_store_design_ref":
            success, artifact_id, path = artifact_store.store_design_reference(
                product_name=arguments["product_name"],
                pattern=arguments["pattern"],
                url=arguments.get("url"),
                why_it_works=arguments.get("why_it_works"),
                stealable_rules=arguments.get("stealable_rules"),
                style_tags=arguments.get("style_tags"),
                tags=arguments.get("tags"),
                workflow="taste_library"
            )
            if success:
                _embed_artifact_sync(artifact_id)
                text = f"## Design Reference Stored\n\n- **ID:** `{artifact_id}`\n- **Product:** {arguments['product_name']}\n- **Pattern:** {arguments['pattern']}"
                if arguments.get("stealable_rules"):
                    text += f"\n- **Stealable rules:** {len(arguments['stealable_rules'])}"
            else:
                text = f"Failed to store design reference: {path}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_store_checklist":
            success, artifact_id, path = artifact_store.store_checklist_template(
                name=arguments["name"],
                items=arguments["items"],
                description=arguments.get("description"),
                code_snippets=arguments.get("code_snippets"),
                tags=arguments.get("tags"),
                workflow="checklist"
            )
            if success:
                item_count = len(arguments["items"])
                text = f"## Checklist Template Stored\n\n- **ID:** `{artifact_id}`\n- **Name:** {arguments['name']}\n- **Items:** {item_count}"
                if arguments.get("description"):
                    text += f"\n- **Description:** {arguments['description']}"
            else:
                text = f"Failed to store checklist: {path}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_query_memory":
            results = artifact_store.query(
                artifact_type=arguments.get("artifact_type"),
                tags=arguments.get("tags"),
                sensitivity=arguments.get("sensitivity"),
                workflow=arguments.get("workflow"),
                search_text=arguments.get("search_text"),
                since=arguments.get("since"),
                limit=arguments.get("limit", 50)
            )

            # Track retrieval for auto-reinforcement (top 3 facts)
            # Pass full result objects so track_retrieval can filter by type without extra lookup
            if results and AUTONOMY_LAYER_AVAILABLE and autonomy_scheduler:
                autonomy_scheduler.track_retrieval(results, source="query_memory")

            if results:
                text = f"## Query Results ({len(results)} found)\n\n"
                for r in results:
                    text += f"- **{r['id']}** [{r['type']}]: {r['title']}\n"
                    text += f"  Tags: {r['tags']} | Created: {r['created_at'][:10]}\n"
            else:
                text = "No artifacts found matching query."
            return [TextContent(type="text", text=text)]

        elif name == "duro_semantic_search":
            query = arguments["query"]
            artifact_type = arguments.get("artifact_type")
            tags = arguments.get("tags")
            limit = arguments.get("limit", 20)
            explain = arguments.get("explain", False)

            # Get query embedding if available
            from embeddings import embed_text, is_embedding_available
            query_embedding = None
            if is_embedding_available():
                query_embedding = embed_text(query)

            # Run hybrid search
            search_result = artifact_store.index.hybrid_search(
                query=query,
                query_embedding=query_embedding,
                artifact_type=artifact_type,
                tags=tags,
                limit=limit,
                explain=explain
            )

            results = search_result["results"]
            mode = search_result["mode"]

            # Track retrieval for auto-reinforcement (top 3 facts)
            # Pass full result objects so track_retrieval can filter by type without extra lookup
            if results and AUTONOMY_LAYER_AVAILABLE and autonomy_scheduler:
                autonomy_scheduler.track_retrieval(results, source="semantic_search")

            text = f"## Semantic Search Results\n\n"
            text += f"**Mode:** {mode} | **Query:** \"{query}\"\n"
            text += f"**Candidates:** {search_result['total_candidates']} (FTS: {search_result['fts_count']}, Vec: {search_result['vector_count']})\n\n"

            if results:
                for r in results:
                    score = r["search_score"]
                    text += f"- **{r['id']}** [{r['type']}] (score: {score:.3f})\n"
                    text += f"  {r['title']}\n"
                    if explain and "score_components" in r:
                        sc = r["score_components"]
                        text += f"  _Components: rrf={sc['rrf_base']:.3f}, type={sc['type_weight']:.2f}, recency={sc['recency_boost']:.3f}_\n"
                        if r.get("explain"):
                            text += f"  _Explain: {r['explain']}_\n"
                    text += "\n"
            else:
                text += "No results found.\n"

            return [TextContent(type="text", text=text)]

        elif name == "duro_get_artifact":
            artifact_id = arguments["artifact_id"]
            artifact = artifact_store.get_artifact(artifact_id)
            if artifact:
                text = f"## Artifact: {artifact_id}\n\n```json\n{json.dumps(artifact, indent=2)}\n```"
            else:
                text = f"Artifact '{artifact_id}' not found."
            return [TextContent(type="text", text=text)]

        elif name == "duro_list_artifacts":
            results = artifact_store.list_artifacts(
                artifact_type=arguments.get("artifact_type"),
                limit=arguments.get("limit", 50)
            )
            if results:
                text = f"## Artifacts ({len(results)} listed)\n\n"
                for r in results:
                    text += f"- **{r['id']}** [{r['type']}]: {r['title']}\n"
            else:
                text = "No artifacts found."
            return [TextContent(type="text", text=text)]

        elif name == "duro_reindex":
            import subprocess

            # Get before metrics
            before_count = artifact_store.index.count()
            before_metrics = {"indexed_count": before_count}

            # Get code version
            try:
                code_version = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=Path(__file__).parent,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
            except Exception:
                code_version = "unknown"

            # Start repair log
            repair_id = artifact_store.index.start_repair(
                repair_type="full_reindex",
                trigger="manual",
                before_metrics=before_metrics,
                code_version=code_version
            )

            # Crash-proof repair logging with try/finally
            success_count = 0
            error_count = 0
            error_blob = None
            repair_result = "success"

            try:
                success_count, error_count = artifact_store.reindex()
                if error_count > 0:
                    repair_result = "partial"
            except Exception as e:
                repair_result = "failed"
                error_blob = repr(e)
                raise
            finally:
                # Always complete the repair log, even on crash
                after_count = artifact_store.index.count()
                after_metrics = {"indexed_count": after_count}
                artifact_store.index.complete_repair(
                    repair_id=repair_id,
                    after_metrics=after_metrics,
                    processed_count=success_count,
                    failed_count=error_count,
                    canonical_mutations=0,  # Reindex never mutates canonical
                    result=repair_result,
                    error_blob=error_blob
                )

            text = f"Reindex complete.\n- Indexed: {success_count}\n- Errors: {error_count}\n- Repair logged: #{repair_id}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_list_repairs":
            limit = arguments.get("limit", 20)

            # Cleanup any stuck in_progress repairs (older than 10 min)
            cleaned = artifact_store.index.cleanup_stuck_repairs(max_age_minutes=10)

            repairs = artifact_store.index.get_recent_repairs(limit=limit)

            if repairs:
                text = f"## Repair Log ({len(repairs)} entries)\n\n"
                if cleaned > 0:
                    text += f"**Note:** Marked {cleaned} stuck in_progress repair(s) as failed.\n\n"
                for r in repairs:
                    status_icon = {"success": "✅", "partial": "⚠️", "failed": "❌", "in_progress": "🔄", "pending": "⏳"}.get(r["result"], "?")
                    duration = f"{r['duration_ms']}ms" if r.get("duration_ms") else "in progress"
                    text += f"- **#{r['id']}** {status_icon} `{r['repair_type']}` ({r['started_at'][:16]})\n"
                    text += f"  - Trigger: {r['trigger']}\n"
                    text += f"  - Duration: {duration}\n"
                    if r.get("processed_count"):
                        text += f"  - Processed: {r['processed_count']}, Failed: {r.get('failed_count', 0)}\n"
                    if r.get("canonical_mutations", 0) > 0:
                        text += f"  - ⚠️ Canonical mutations: {r['canonical_mutations']}\n"
                    if r.get("error_blob"):
                        text += f"  - Error: {r['error_blob'][:100]}\n"
                    text += "\n"
            else:
                text = "No repair operations logged yet."
                if cleaned > 0:
                    text += f"\n\n**Note:** Marked {cleaned} stuck in_progress repair(s) as failed."
            return [TextContent(type="text", text=text)]

        elif name == "duro_run_migration":
            action = arguments.get("action", "status")
            migration_id = arguments.get("migration_id")  # Optional: specific migration

            from migrations.runner import get_status, run_all_pending, run_migration

            migrations_dir = Path(__file__).parent / "migrations"
            db_path = str(DB_PATH)  # Use same DB_PATH as main server

            if action == "status":
                status = get_status(migrations_dir, db_path)
                text = "## Migration Status\n\n"

                if status["applied"]:
                    text += "### Applied\n"
                    for m in status["applied"]:
                        text += f"- ✅ **{m['migration_id']}** ({m['applied_at'][:10]})\n"
                else:
                    text += "No migrations applied yet.\n"

                if status["pending"]:
                    text += "\n### Pending\n"
                    for m in status["pending"]:
                        text += f"- ⏳ **{m['migration_id']}**\n"

                if status["modified"]:
                    text += "\n### ⚠️ Modified Since Applied\n"
                    for m in status["modified"]:
                        text += f"- **{m['migration_id']}** (checksum changed)\n"

            elif action == "up":
                if migration_id:
                    # Run specific migration
                    migration_path = migrations_dir / f"m{migration_id}.py"
                    if not migration_path.exists():
                        migration_path = migrations_dir / f"{migration_id}.py"
                    if not migration_path.exists():
                        return [TextContent(type="text", text=f"Migration not found: {migration_id}")]

                    result = run_migration(db_path, migration_path)
                    text = f"## Migration: {result['migration_id']}\n\n"
                    text += f"- **Success:** {'✅' if result['success'] else '❌'}\n"
                    text += f"- **Message:** {result['message']}\n"
                    if result.get("details"):
                        text += f"- **Details:** {result['details']}\n"
                else:
                    # Run all pending
                    result = run_all_pending(migrations_dir, db_path)
                    text = "## Migration Run\n\n"
                    text += f"- **Success:** {'✅' if result['success'] else '❌'}\n"
                    if result["applied"]:
                        text += f"- **Applied:** {', '.join(result['applied'])}\n"
                    if result["skipped"]:
                        text += f"- **Skipped:** {', '.join(result['skipped'])}\n"
                    if result["failed"]:
                        text += f"- **Failed:** {', '.join(result['failed'])}\n"
            else:
                text = f"Unknown action: {action}. Use 'status' or 'up'."

            return [TextContent(type="text", text=text)]

        elif name == "duro_delete_artifact":
            artifact_id = arguments["artifact_id"]
            reason = arguments["reason"]
            force = arguments.get("force", False)

            # === Autonomy gate for destructive MCP tool ===
            if AUTONOMY_AVAILABLE:
                tool_name = "duro_delete_artifact"
                domain = classify_action_domain(tool_name)
                action_id = f"{tool_name}_{domain}"
                context = {"is_destructive": True}

                # Precheck without consuming token
                perm = check_action(tool_name, context, action_id=action_id, consume_token=False)

                if not perm.allowed:
                    text = f"## Autonomy Blocked\n\n"
                    text += f"**Action:** `{tool_name}`\n"
                    text += f"**Domain:** `{domain}`\n"
                    text += f"**Reason:** {perm.reason}\n\n"
                    if perm.requires_approval:
                        text += f"**To approve:** `duro_grant_approval(action_id=\"{action_id}\")`"
                    return [TextContent(type="text", text=text)]

                # If allowed via token, consume it NOW
                if perm.allowed_via_token:
                    enforcer = get_autonomy_enforcer()
                    consumed = enforcer.use_approval(action_id, used_by=f"mcp_{artifact_id}")
                    if not consumed:
                        text = f"## Autonomy Blocked\n\n"
                        text += f"**Action:** `{tool_name}`\n"
                        text += f"**Reason:** Approval token expired or already used\n\n"
                        text += f"**To approve:** `duro_grant_approval(action_id=\"{action_id}\")`"
                        return [TextContent(type="text", text=text)]

            success, message = artifact_store.delete_artifact(
                artifact_id=artifact_id,
                reason=reason,
                force=force
            )

            if success:
                text = f"Deleted successfully.\n- ID: {artifact_id}\n- {message}"
            else:
                text = f"Delete failed: {message}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_batch_delete":
            artifact_ids = arguments["artifact_ids"]
            reason = arguments["reason"]
            force = arguments.get("force", False)

            if not artifact_ids:
                return [TextContent(type="text", text="No artifact IDs provided.")]

            # === Single autonomy gate for entire batch ===
            # CRITICAL: action_id includes hash of exact batch args
            # This prevents "approve once, delete anything" attacks
            if AUTONOMY_AVAILABLE:
                tool_name = "duro_batch_delete"
                domain = classify_action_domain("duro_delete_artifact")  # Same domain as single delete

                # Compute hash of exact batch args (binds approval to THIS batch)
                if POLICY_GATE_AVAILABLE:
                    batch_hash = compute_args_hash(arguments)
                else:
                    # Fallback: simple hash
                    import hashlib
                    canonical = json.dumps({"ids": sorted(artifact_ids), "reason": reason, "force": force}, sort_keys=True)
                    batch_hash = hashlib.sha256(canonical.encode()).hexdigest()[:16]

                action_id = f"duro_batch_delete_{domain}_{batch_hash}"
                context = {"is_destructive": True}

                # Precheck without consuming token
                perm = check_action(tool_name, context, action_id=action_id, consume_token=False)

                if not perm.allowed:
                    text = f"## Autonomy Blocked\n\n"
                    text += f"**Action:** `{tool_name}`\n"
                    text += f"**Domain:** `{domain}`\n"
                    text += f"**Batch size:** {len(artifact_ids)} artifacts\n"
                    text += f"**Batch hash:** `{batch_hash}`\n"
                    text += f"**Reason:** {perm.reason}\n\n"
                    if perm.requires_approval:
                        text += f"**To approve:** `duro_grant_approval(action_id=\"{action_id}\")`"
                    return [TextContent(type="text", text=text)]

                # Consume token once for entire batch
                if perm.allowed_via_token:
                    enforcer = get_autonomy_enforcer()
                    consumed = enforcer.use_approval(action_id, used_by=f"mcp_batch_{batch_hash}")
                    if not consumed:
                        text = f"## Autonomy Blocked\n\n"
                        text += f"**Action:** `{tool_name}`\n"
                        text += f"**Reason:** Approval token expired or already used\n\n"
                        text += f"**To approve:** `duro_grant_approval(action_id=\"{action_id}\")`"
                        return [TextContent(type="text", text=text)]

            # Process batch deletion
            deleted = []
            failed = []

            for aid in artifact_ids:
                success, message = artifact_store.delete_artifact(
                    artifact_id=aid,
                    reason=reason,
                    force=force
                )
                if success:
                    deleted.append(aid)
                else:
                    failed.append((aid, message))

            # Build result
            lines = ["## Batch Delete Results\n"]
            lines.append(f"**Deleted:** {len(deleted)} / {len(artifact_ids)}")

            if deleted:
                lines.append(f"\n### Deleted ({len(deleted)})")
                for aid in deleted[:20]:  # Show first 20
                    lines.append(f"- `{aid}`")
                if len(deleted) > 20:
                    lines.append(f"- ... and {len(deleted) - 20} more")

            if failed:
                lines.append(f"\n### Failed ({len(failed)})")
                for aid, msg in failed[:10]:
                    lines.append(f"- `{aid}`: {msg}")
                if len(failed) > 10:
                    lines.append(f"- ... and {len(failed) - 10} more")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_query_audit_log":
            result = artifact_store.query_audit_log(
                event_type=arguments.get("event_type"),
                artifact_id=arguments.get("artifact_id"),
                search_text=arguments.get("search_text"),
                since=arguments.get("since"),
                limit=arguments.get("limit", 50),
                verify_chain=arguments.get("verify_chain", False)
            )

            lines = [f"## Audit Log Query Results\n"]
            lines.append(f"**Total entries:** {result['total']}")

            if result.get("chain_valid") is not None:
                chain_status = "✅ Valid" if result["chain_valid"] else "❌ BROKEN - possible tampering"
                lines.append(f"**Integrity chain:** {chain_status}")

                # Show per-link details if available
                chain_details = result.get("chain_details", [])
                if chain_details:
                    lines.append("\n### Chain Verification\n")
                    lines.append("| # | timestamp | entry_hash | prev_hash | link |")
                    lines.append("|---|-----------|------------|-----------|------|")
                    for detail in chain_details:
                        entry_num = detail.get("entry", "?")
                        timestamp = detail.get("timestamp", "?")
                        entry_hash_len = detail.get("entry_hash_len", 0)
                        prev_hash_len = detail.get("prev_hash_len", 0)
                        link_ok = detail.get("link_ok")
                        status = detail.get("status", "unknown")

                        if link_ok is True:
                            link_icon = "✅"
                        elif link_ok is False:
                            link_icon = "❌"
                        elif status == "legacy":
                            link_icon = "⚪"
                        else:
                            link_icon = "⚠️"

                        lines.append(f"| {entry_num} | {timestamp} | {entry_hash_len} | {prev_hash_len} | {link_icon} |")

                    # Also show any broken links with details
                    broken = [d for d in chain_details if d.get("status") == "broken"]
                    if broken:
                        lines.append("\n**Broken links:**")
                        for d in broken:
                            lines.append(f"- Entry {d['entry']}: {d['message']}")

            if result.get("error"):
                lines.append(f"**Error:** {result['error']}")

            if result["entries"]:
                lines.append("\n### Entries\n")
                for entry in result["entries"]:
                    ts = entry.get("timestamp", "?")[:19]
                    aid = entry.get("artifact_id", "?")
                    reason = entry.get("reason", "")
                    force = " [FORCE]" if entry.get("force_used") else ""
                    lines.append(f"- `{ts}` | `{aid}` | {reason}{force}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_log_audit_repair":
            success = artifact_store.log_audit_repair(
                backup_path=arguments["backup_path"],
                backup_hash=arguments["backup_hash"],
                repaired_hash=arguments["repaired_hash"],
                entries_before=arguments["entries_before"],
                entries_after=arguments["entries_after"],
                reason=arguments["reason"]
            )
            if success:
                text = "Audit repair logged successfully."
            else:
                text = "Failed to log audit repair."
            return [TextContent(type="text", text=text)]

        elif name == "duro_query_repair_log":
            limit = arguments.get("limit", 20)
            logs_dir = Path(CONFIG["paths"]["memory_dir"]) / "logs"
            repairs_log = logs_dir / "audit_repairs.jsonl"

            if not repairs_log.exists():
                return [TextContent(type="text", text="No repair log found (no repairs recorded).")]

            entries = []
            try:
                with open(repairs_log, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entries.append(json.loads(line))
            except Exception as e:
                return [TextContent(type="text", text=f"Error reading repair log: {e}")]

            entries = entries[-limit:][::-1]  # Most recent first

            lines = [f"## Audit Repair Log ({len(entries)} entries)\n"]
            for entry in entries:
                ts = entry.get("timestamp", "?")[:19]
                reason = entry.get("reason", "?")
                before = entry.get("entries_before", "?")
                after = entry.get("entries_after", "?")
                lines.append(f"- `{ts}` | {before}→{after} entries | {reason}")

            return [TextContent(type="text", text="\n".join(lines))]

        # Orchestration tools
        elif name == "duro_orchestrate":
            intent = arguments["intent"]
            args = arguments.get("args", {})
            dry_run = arguments.get("dry_run", False)
            sensitivity = arguments.get("sensitivity")

            result = orchestrator.orchestrate(
                intent=intent,
                args=args,
                dry_run=dry_run,
                sensitivity=sensitivity
            )

            # Format output
            lines = ["## Orchestration Result\n"]
            lines.append(f"**Run ID:** `{result['run_id']}`")
            lines.append(f"**Intent:** {result['intent']}")
            lines.append(f"**Plan:** {result['plan']} ({result['plan_type']})")

            if result['rules_applied']:
                lines.append(f"**Rules Applied:** {', '.join(result['rules_applied'])}")

            if result['constraints']:
                lines.append(f"**Constraints:** {json.dumps(result['constraints'])}")

            outcome_icon = {
                "success": "✅",
                "failed": "❌",
                "denied": "🚫",
                "dry_run": "👁️"
            }.get(result['outcome'], "❓")

            lines.append(f"**Outcome:** {outcome_icon} {result['outcome']}")

            if result['error']:
                lines.append(f"**Error:** {result['error']}")

            if result['artifacts_created']:
                lines.append(f"**Artifacts Created:** {', '.join(result['artifacts_created'])}")

            lines.append(f"**Duration:** {result['duration_ms']}ms")
            lines.append(f"**Run Log:** `{result['run_path']}`")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_list_runs":
            limit = arguments.get("limit", 20)
            outcome = arguments.get("outcome")

            runs = orchestrator.list_runs(limit=limit, outcome=outcome)

            if not runs:
                return [TextContent(type="text", text="No runs found.")]

            lines = [f"## Recent Runs ({len(runs)} shown)\n"]
            lines.append("| Run ID | Intent | Outcome | Duration |")
            lines.append("|--------|--------|---------|----------|")

            for run in runs:
                run_id = run.get("run_id", "?")[:25]
                intent = run.get("intent", "?")
                outcome = run.get("outcome", "?")
                duration = run.get("duration_ms", 0)

                outcome_icon = {"success": "✅", "failed": "❌", "denied": "🚫", "dry_run": "👁️"}.get(outcome, "❓")
                lines.append(f"| `{run_id}` | {intent} | {outcome_icon} | {duration}ms |")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_get_run":
            run_id = arguments["run_id"]
            run = orchestrator.get_run(run_id)

            if not run:
                return [TextContent(type="text", text=f"Run '{run_id}' not found.")]

            text = f"## Run: {run_id}\n\n```json\n{json.dumps(run, indent=2)}\n```"
            return [TextContent(type="text", text=text)]

        # Episode tools
        elif name == "duro_create_episode":
            goal = arguments["goal"]
            plan = arguments.get("plan", [])
            context = arguments.get("context", {})
            tags = arguments.get("tags", [])

            success, episode_id, path = artifact_store.store_episode(
                goal=goal,
                plan=plan,
                context=context,
                tags=tags
            )

            if success:
                # Embed synchronously for immediate vector search
                _embed_artifact_sync(episode_id)
                text = f"Episode created successfully.\n- ID: `{episode_id}`\n- Goal: {goal[:100]}...\n- Status: open"
            else:
                text = f"Failed to create episode: {path}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_add_episode_action":
            episode_id = arguments["episode_id"]
            action = {
                "run_id": arguments.get("run_id"),
                "tool": arguments.get("tool"),
                "summary": arguments["summary"]
            }

            success, message = artifact_store.update_episode(episode_id, {"action": action})

            if success:
                text = f"Action added to episode `{episode_id}`.\n- Tool: {action.get('tool', 'N/A')}\n- Summary: {action['summary'][:100]}"
            else:
                text = f"Failed to add action: {message}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_close_episode":
            episode_id = arguments["episode_id"]
            result = arguments["result"]
            result_summary = arguments.get("result_summary", "")
            links = arguments.get("links", {})

            updates = {
                "status": "closed",
                "result": result,
                "result_summary": result_summary
            }
            if links:
                updates["links"] = links

            success, message = artifact_store.update_episode(episode_id, updates)

            if success:
                # Re-embed with result_summary now included
                _embed_artifact_sync(episode_id)
                # Get updated episode to show duration
                episode = artifact_store.get_artifact(episode_id)
                duration = episode["data"].get("duration_mins", "?")
                result_icon = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(result, "❓")
                text = f"Episode closed.\n- ID: `{episode_id}`\n- Result: {result_icon} {result}\n- Duration: {duration} mins"
            else:
                text = f"Failed to close episode: {message}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_evaluate_episode":
            episode_id = arguments["episode_id"]
            rubric = arguments["rubric"]
            grade = arguments["grade"]
            memory_updates = arguments.get("memory_updates", {"reinforce": [], "decay": []})
            next_change = arguments.get("next_change")

            success, eval_id, path = artifact_store.store_evaluation(
                episode_id=episode_id,
                rubric=rubric,
                grade=grade,
                memory_updates=memory_updates,
                next_change=next_change
            )

            if success:
                # Embed synchronously for immediate vector search
                _embed_artifact_sync(eval_id)
                text = f"Evaluation created.\n- ID: `{eval_id}`\n- Episode: `{episode_id}`\n- Grade: {grade}\n- Memory updates pending: {len(memory_updates.get('reinforce', []))} reinforce, {len(memory_updates.get('decay', []))} decay"
            else:
                text = f"Failed to create evaluation: {path}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_apply_evaluation":
            evaluation_id = arguments["evaluation_id"]

            success, message, applied = artifact_store.apply_evaluation(evaluation_id)

            if success:
                lines = [f"Evaluation applied.\n- ID: `{evaluation_id}`"]
                if applied.get("reinforced"):
                    lines.append(f"\n**Reinforced ({len(applied['reinforced'])}):**")
                    for r in applied["reinforced"]:
                        lines.append(f"  - `{r['id']}` ({r['type']}): +{r['delta']:.3f} → {r['new_confidence']:.3f}")
                if applied.get("decayed"):
                    lines.append(f"\n**Decayed ({len(applied['decayed'])}):**")
                    for d in applied["decayed"]:
                        lines.append(f"  - `{d['id']}` ({d['type']}): {d['delta']:.3f} → {d['new_confidence']:.3f}")
                if applied.get("errors"):
                    lines.append(f"\n**Errors ({len(applied['errors'])}):**")
                    for e in applied["errors"]:
                        lines.append(f"  - `{e['id']}`: {e['error']}")
                text = "\n".join(lines)
            else:
                text = f"Failed to apply evaluation: {message}"
            return [TextContent(type="text", text=text)]

        elif name == "duro_get_episode":
            episode_id = arguments["episode_id"]
            episode = artifact_store.get_artifact(episode_id)

            if not episode:
                return [TextContent(type="text", text=f"Episode '{episode_id}' not found.")]

            text = f"## Episode: {episode_id}\n\n```json\n{json.dumps(episode, indent=2)}\n```"
            return [TextContent(type="text", text=text)]

        elif name == "duro_list_episodes":
            status = arguments.get("status")
            limit = arguments.get("limit", 20)

            # Query episodes via index
            results = artifact_store.query(artifact_type="episode", limit=limit)

            # Filter by status if specified (post-query since index doesn't have status field)
            if status:
                filtered = []
                for r in results:
                    ep = artifact_store.get_artifact(r["id"])
                    if ep and ep["data"].get("status") == status:
                        filtered.append(r)
                results = filtered[:limit]

            if not results:
                return [TextContent(type="text", text=f"No episodes found{' with status ' + status if status else ''}.")]

            lines = [f"## Episodes ({len(results)} found)\n"]
            lines.append("| ID | Goal | Status | Duration |")
            lines.append("|-----|------|--------|----------|")

            for r in results:
                ep = artifact_store.get_artifact(r["id"])
                if ep:
                    ep_id = ep["id"][:20]
                    goal = ep["data"].get("goal", "")[:40]
                    ep_status = ep["data"].get("status", "?")
                    duration = ep["data"].get("duration_mins", "-")
                    status_icon = {"open": "🔵", "closed": "✅"}.get(ep_status, "❓")
                    lines.append(f"| `{ep_id}` | {goal} | {status_icon} {ep_status} | {duration} |")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_suggest_episode":
            tools_used = arguments.get("tools_used", False)
            duration_mins = arguments.get("duration_mins", 0)
            artifacts_produced = arguments.get("artifacts_produced", False)
            goal_summary = arguments.get("goal_summary", "")

            # Criteria for suggesting an episode
            should_create = False
            reasons = []

            if tools_used:
                should_create = True
                reasons.append("tools were used")
            if duration_mins >= 3:
                should_create = True
                reasons.append(f"duration is {duration_mins:.1f}min (>=3min)")
            if artifacts_produced:
                should_create = True
                reasons.append("artifacts were produced")

            if should_create:
                text = f"**Episode Suggested** ✨\n\nThis looks like an episode because: {', '.join(reasons)}.\n\n"
                text += f"Goal: {goal_summary[:100] if goal_summary else 'Not specified'}\n\n"
                text += "To create: `duro_create_episode(goal=\"{goal}\")`"
            else:
                text = "**No Episode Needed**\n\nThis work doesn't meet episode criteria (tools used, >3min, or artifact production)."

            return [TextContent(type="text", text=text)]

        # === Autonomy Tools ===
        elif name == "duro_check_permission":
            if not AUTONOMY_AVAILABLE:
                return [TextContent(type="text", text=f"Autonomy system not available: {AUTONOMY_IMPORT_ERROR}")]

            action = arguments["action"]
            context = arguments.get("context", {})

            # Check permission (this classifies domain and risk internally)
            result = check_action(action, context)

            # Use the domain from the result for display consistency
            lines = ["## Permission Check\n"]
            lines.append(f"**Action:** `{action}`")
            lines.append(f"**Domain:** `{result.domain}`")
            lines.append(f"**Risk Level:** `{result.action_risk.value}`")
            lines.append(f"**Domain Score:** {result.domain_score:.2f}")
            lines.append("")

            if result.allowed:
                lines.append(f"### ✅ ALLOWED\n")
                lines.append(f"Reason: {result.reason}")
            else:
                lines.append(f"### ❌ BLOCKED\n")
                lines.append(f"Reason: {result.reason}")
                lines.append(f"- Current Level: L{result.current_level.value} ({result.current_level.name})")
                lines.append(f"- Required Level: L{result.required_level.value} ({result.required_level.name})")

                if result.downgrade_to:
                    lines.append(f"\n**Downgrade:** Must operate in `{result.downgrade_to}` mode")
                if result.requires_approval:
                    lines.append(f"**Requires:** Explicit user approval")
                    lines.append(f"\nTo approve: `duro_grant_approval(action_id=\"{action}_{result.domain}\")`")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_can_execute":
            # Per-tool-call gate - returns machine-readable JSON
            if not AUTONOMY_AVAILABLE:
                # Fail open if autonomy unavailable
                response = {
                    "can_execute": True,
                    "action_needed": "none",
                    "reason": "Autonomy system unavailable, defaulting to allow"
                }
                return [TextContent(type="text", text=json.dumps(response))]

            tool_name = arguments["tool_name"]
            args_hint = arguments.get("args_hint", "")
            is_destructive = arguments.get("is_destructive", False)

            # Build action string from tool + hint
            action = tool_name
            if args_hint:
                action = f"{tool_name}:{args_hint}"

            # Build context
            context = {}
            if is_destructive:
                context["is_destructive"] = True

            # Check permission without consuming token (precheck)
            result = check_action(action, context, consume_token=False)

            # Compute canonical action_id (tool_name + domain, NOT including args_hint)
            # This matches what gate tools like duro_delete_artifact expect
            canonical_action_id = f"{tool_name}_{result.domain}"

            # Build machine-readable response
            if result.allowed:
                response = {
                    "can_execute": True,
                    "action_needed": "none",
                    "reason": result.reason,
                    "risk": result.action_risk.value,
                    "domain": result.domain,
                    "action_id": canonical_action_id
                }
            else:
                action_needed = "approve"
                if result.downgrade_to:
                    action_needed = "downgrade"

                response = {
                    "can_execute": False,
                    "action_needed": action_needed,
                    "reason": result.reason,
                    "risk": result.action_risk.value,
                    "domain": result.domain,
                    "current_level": result.current_level.value,
                    "required_level": result.required_level.value,
                    "action_id": canonical_action_id
                }

                if action_needed == "approve":
                    response["approve_cmd"] = f"duro_grant_approval(action_id=\"{canonical_action_id}\")"
                elif action_needed == "downgrade":
                    response["downgrade_to"] = result.downgrade_to

            return [TextContent(type="text", text=json.dumps(response))]

        elif name == "duro_get_reputation":
            if not AUTONOMY_AVAILABLE:
                return [TextContent(type="text", text=f"Autonomy system not available: {AUTONOMY_IMPORT_ERROR}")]

            domain = arguments.get("domain")
            store = get_reputation_store()

            lines = ["## Reputation Scores\n"]
            lines.append(f"**Global Score:** {store.global_score:.2f}")
            lines.append("")

            if domain:
                # Single domain
                ds = store.get_domain_score(domain)
                allowed_level = store.get_allowed_level(domain)
                lines.append(f"### Domain: `{domain}`\n")
                lines.append(f"- **Score:** {ds.score:.2f}")
                lines.append(f"- **Allowed Level:** L{allowed_level.value} ({allowed_level.name})")
                lines.append(f"- **Reopen Rate:** {ds.reopen_rate:.1%}")
                lines.append(f"- **Revert Rate:** {ds.revert_rate:.1%}")
                lines.append(f"- **Total Closures:** {ds.total_closures}")
                lines.append(f"- **Last Updated:** {ds.last_updated[:10] if ds.last_updated else 'never'}")
            else:
                # All domains
                if store.scores:
                    lines.append("| Domain | Score | Level | Reopen | Revert |")
                    lines.append("|--------|-------|-------|--------|--------|")
                    for domain_name, ds in sorted(store.scores.items(), key=lambda x: -x[1].score):
                        allowed_level = store.get_allowed_level(domain_name)
                        lines.append(f"| `{domain_name}` | {ds.score:.2f} | L{allowed_level.value} | {ds.reopen_rate:.0%} | {ds.revert_rate:.0%} |")
                else:
                    lines.append("*No domain scores yet. Scores build as actions are recorded.*")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_record_outcome":
            if not AUTONOMY_AVAILABLE:
                return [TextContent(type="text", text=f"Autonomy system not available: {AUTONOMY_IMPORT_ERROR}")]

            action = arguments["action"]
            success = arguments["success"]
            confidence = arguments.get("confidence", 0.5)
            was_reverted = arguments.get("was_reverted", False)

            record_outcome(action, success, confidence, was_reverted)

            domain = classify_action_domain(action)
            store = get_reputation_store()
            ds = store.get_domain_score(domain)

            event = "confident_revert" if was_reverted else ("successful_closure" if success else "validation_failure")

            lines = ["## Outcome Recorded\n"]
            lines.append(f"**Action:** `{action}`")
            lines.append(f"**Domain:** `{domain}`")
            lines.append(f"**Event:** `{event}`")
            lines.append(f"**New Domain Score:** {ds.score:.2f}")
            lines.append(f"**Global Score:** {store.global_score:.2f}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_grant_approval":
            if not AUTONOMY_AVAILABLE:
                return [TextContent(type="text", text=f"Autonomy system not available: {AUTONOMY_IMPORT_ERROR}")]

            action_id = arguments["action_id"]
            duration = arguments.get("duration_seconds", 300)
            reason = arguments.get("reason", "User requested approval")

            # Validate action_id format (should be tool_name:args_hash for scoped approval)
            is_scoped = ":" in action_id
            if not is_scoped:
                # Legacy tool-level approval - warn but allow
                lines = ["## Warning: Unscoped Approval\n"]
                lines.append(f"Action ID `{action_id}` is not scoped to a specific action.")
                lines.append("Scoped format is `tool_name:args_hash` (e.g., from gate block message).")
                lines.append("\nProceeding with tool-level approval (less secure).\n")
            else:
                lines = []

            # Use global enforcer to preserve tokens
            enforcer = get_autonomy_enforcer()
            enforcer.grant_approval(action_id, duration, reason)

            lines.append("## Approval Granted\n")
            lines.append(f"**Action ID:** `{action_id}`")
            if is_scoped:
                tool_part, hash_part = action_id.split(":", 1)
                lines.append(f"**Tool:** `{tool_part}`")
                lines.append(f"**Args Hash:** `{hash_part}`")
            lines.append(f"**Duration:** {duration} seconds")
            lines.append(f"**Expires:** in {duration // 60} min {duration % 60} sec")
            lines.append(f"**Reason:** {reason}")
            lines.append(f"\n*ONE-SHOT approval scoped to exact action. Consumed on first use.*")
            if is_scoped:
                lines.append("*If arguments change, a new approval is required.*")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_autonomy_status":
            lines = ["## Autonomy System Status\n"]

            if not AUTONOMY_AVAILABLE:
                lines.append(f"**Status:** ❌ Not Available")
                lines.append(f"**Error:** {AUTONOMY_IMPORT_ERROR}")
                return [TextContent(type="text", text="\n".join(lines))]

            store = get_reputation_store()

            lines.append(f"**Status:** ✅ Active")
            lines.append(f"**Global Reputation:** {store.global_score:.2f}")
            lines.append(f"**Domains Tracked:** {len(store.scores)}")
            lines.append("")

            # Level thresholds
            lines.append("### Autonomy Levels\n")
            lines.append("| Level | Name | Threshold | Capabilities |")
            lines.append("|-------|------|-----------|--------------|")
            level_caps = {
                0: "read, search",
                1: "plan, propose",
                2: "edit files, safe commands",
                3: "destructive ops (w/ approval)",
                4: "full trust (domain-specific)",
            }
            from autonomy_ladder import DOMAIN_THRESHOLDS
            for level in AutonomyLevel:
                threshold = DOMAIN_THRESHOLDS.get(level, 0.0)
                caps = level_caps.get(level.value, "?")
                lines.append(f"| L{level.value} | {level.name} | {threshold:.2f} | {caps} |")

            # Top domains
            if store.scores:
                lines.append("\n### Top Domains by Score\n")
                sorted_domains = sorted(store.scores.items(), key=lambda x: -x[1].score)[:5]
                for domain_name, ds in sorted_domains:
                    allowed = store.get_allowed_level(domain_name)
                    lines.append(f"- **{domain_name}:** {ds.score:.2f} (L{allowed.value})")

            # Active approvals
            enforcer = get_autonomy_enforcer()
            active_tokens = [
                (aid, t) for aid, t in enforcer.approval_tokens.items()
                if t.is_valid
            ]
            if active_tokens:
                lines.append("\n### Active Approval Tokens\n")
                for action_id, token in active_tokens:
                    lines.append(f"- `{action_id}` (expires: {token.expires_at.isoformat()[:19]})")

            # Recent approval log
            recent_log = enforcer.get_approval_log(5)
            if recent_log:
                lines.append("\n### Recent Approval Activity\n")
                for entry in recent_log[-5:]:
                    event_icon = {"grant": "✅", "use": "🔓", "revoke": "❌"}.get(entry["event"], "?")
                    lines.append(f"- {event_icon} {entry['event']} `{entry['action_id']}` ({entry['timestamp'][:19]})")

            # Policy gate stats (if available)
            if POLICY_GATE_AVAILABLE:
                lines.append("\n### Policy Gate Stats\n")
                gate_stats = get_gate_stats()
                lines.append(f"- Total decisions: {gate_stats['total']}")
                lines.append(f"- By decision: {gate_stats['by_decision']}")
                lines.append(f"- Bypasses: {gate_stats['bypasses']}")
                lines.append(f"- Breakglass uses: {gate_stats['breakglass_uses']}")
                if gate_stats['errors']:
                    lines.append(f"- Errors: {gate_stats['errors']}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_gate_audit":
            if not POLICY_GATE_AVAILABLE:
                return [TextContent(type="text", text=f"Policy gate not available: {POLICY_GATE_ERROR}")]

            limit = arguments.get("limit", 50)
            tool_filter = arguments.get("tool")
            decision_filter = arguments.get("decision")
            since = arguments.get("since")

            records = query_gate_audit(
                limit=limit,
                tool_filter=tool_filter,
                decision_filter=decision_filter,
                since=since
            )

            lines = ["## Gate Audit Log\n"]
            stats = get_gate_stats()
            lines.append(f"**Total Decisions:** {stats['total']}")
            lines.append(f"**By Decision:** ALLOW={stats['by_decision'].get('ALLOW', 0)}, DENY={stats['by_decision'].get('DENY', 0)}, NEED_APPROVAL={stats['by_decision'].get('NEED_APPROVAL', 0)}")
            lines.append(f"**Bypasses:** {stats['bypasses']} | **Breakglass:** {stats['breakglass_uses']} | **Errors:** {stats['errors']}")
            lines.append("")

            if records:
                lines.append(f"### Recent Records (showing {len(records)} of {stats['total']})\n")
                for r in records[:20]:  # Show max 20 in output
                    icon = {"ALLOW": "✅", "DENY": "❌", "NEED_APPROVAL": "⏳"}.get(r.get("decision"), "?")
                    bypass_tag = " [bypass]" if r.get("bypass") else ""
                    breakglass_tag = " [BREAKGLASS]" if r.get("breakglass") else ""
                    error_tag = f" [err: {r.get('error')}]" if r.get("error") else ""
                    lines.append(f"- {icon} `{r.get('tool')}` ({r.get('risk')}/{r.get('domain')}) - {r.get('safe_summary')[:50]}{bypass_tag}{breakglass_tag}{error_tag}")
            else:
                lines.append("*No audit records found.*")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_workspace_status":
            if not WORKSPACE_GUARD_AVAILABLE:
                return [TextContent(type="text", text=f"Workspace guard not available: {WORKSPACE_GUARD_ERROR}")]

            status = get_workspace_status()
            lines = ["## Workspace Configuration\n"]
            lines.append(f"**Strict Mode:** {'Yes' if status['strict'] else 'No'}")
            lines.append(f"**High-Risk Approval:** {'Required' if status['high_risk_require_approval'] else 'Not required'}")
            lines.append(f"**Loaded From:** {status['loaded_from']}")
            lines.append(f"**Config File:** {status['config_file']}")
            lines.append("")
            lines.append("### Allowed Workspaces\n")
            for ws in status["workspaces"]:
                lines.append(f"- `{ws}`")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_workspace_add":
            if not WORKSPACE_GUARD_AVAILABLE:
                return [TextContent(type="text", text=f"Workspace guard not available: {WORKSPACE_GUARD_ERROR}")]

            path = arguments["path"]
            force = arguments.get("force", False)

            # If force=True, verify we have approval for this action
            if force and POLICY_GATE_AVAILABLE:
                from policy_gate import compute_args_hash
                args_hash = compute_args_hash({"path": path, "action": "workspace_add"})
                action_id = f"duro_workspace_add:{args_hash}"

                # Check for approval token
                if AUTONOMY_AVAILABLE:
                    enforcer = get_autonomy_enforcer()
                    token = enforcer.approval_tokens.get(action_id)
                    if not token or not token.is_valid:
                        return [TextContent(type="text", text=f"""## Approval Required

Adding workspace outside home directory requires explicit approval.

**Path:** `{path}`

To approve, run:
```
duro_grant_approval(
  action_id="{action_id}",
  reason="<why this workspace is needed>"
)
```

Then retry with `force=true`.""")]
                    # Consume the token
                    enforcer.use_approval(action_id, used_by="duro_workspace_add")

            success, message, requires_approval = add_workspace(path, force=force)

            if requires_approval:
                # Need approval for this path
                from policy_gate import compute_args_hash
                args_hash = compute_args_hash({"path": path, "action": "workspace_add"})
                action_id = f"duro_workspace_add:{args_hash}"

                lines = ["## Approval Required\n"]
                lines.append(f"Adding this workspace is a **privilege escalation**.")
                lines.append(f"\n**Path:** `{path}`")
                lines.append(f"**Reason:** {message}")
                lines.append(f"\nTo approve, run:")
                lines.append(f"```")
                lines.append(f"duro_grant_approval(")
                lines.append(f"  action_id=\"{action_id}\",")
                lines.append(f"  reason=\"<why this workspace is needed>\"")
                lines.append(f")")
                lines.append(f"```")
                lines.append(f"\nThen retry with `force=true`.")
                return [TextContent(type="text", text="\n".join(lines))]

            if success:
                reload_workspace_config()
                return [TextContent(type="text", text=f"## Workspace Added\n\n{message}")]
            else:
                return [TextContent(type="text", text=f"## Failed to Add Workspace\n\n{message}")]

        elif name == "duro_workspace_validate":
            if not WORKSPACE_GUARD_AVAILABLE:
                return [TextContent(type="text", text=f"Workspace guard not available: {WORKSPACE_GUARD_ERROR}")]

            path = arguments["path"]
            result = validate_path(path)

            lines = ["## Path Validation\n"]
            lines.append(f"**Path:** `{path}`")
            lines.append(f"**Valid:** {'Yes' if result.valid else 'No'}")
            lines.append(f"**Risk Level:** {result.risk_level}")
            lines.append(f"**Requires Approval:** {'Yes' if result.requires_approval else 'No'}")
            lines.append(f"**Reason:** {result.reason}")
            if result.normalized_path:
                lines.append(f"**Normalized:** `{result.normalized_path}`")
            if result.workspace_match:
                lines.append(f"**Workspace Match:** `{result.workspace_match}`")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "duro_classify_action":
            if not AUTONOMY_AVAILABLE:
                return [TextContent(type="text", text=f"Autonomy system not available: {AUTONOMY_IMPORT_ERROR}")]

            action = arguments["action"]
            context = arguments.get("context", {})

            # Classify domain and risk
            domain = classify_action_domain(action)
            risk = classify_action_risk(action, context)

            # Get current allowed level for this domain
            store = get_reputation_store()
            ds = store.get_domain_score(domain)
            allowed_level = store.get_allowed_level(domain)

            # Determine required level for this risk
            from autonomy_ladder import LEVEL_CAPABILITIES
            required_level = AutonomyLevel.L0_OBSERVE
            for level in AutonomyLevel:
                if risk in LEVEL_CAPABILITIES.get(level, set()):
                    required_level = level
                    break

            # Would this be allowed?
            would_allow = risk in LEVEL_CAPABILITIES.get(allowed_level, set())

            lines = ["## Action Classification\n"]
            lines.append(f"**Action:** `{action}`")
            lines.append(f"**Domain:** `{domain}`")
            lines.append(f"**Risk Level:** `{risk.value}`")
            lines.append("")
            lines.append(f"**Required Level:** L{required_level.value} ({required_level.name})")
            lines.append(f"**Current Domain Score:** {ds.score:.2f}")
            lines.append(f"**Allowed Level:** L{allowed_level.value} ({allowed_level.name})")
            lines.append("")

            if would_allow:
                lines.append("### ✅ Would be ALLOWED")
            else:
                lines.append("### ❌ Would be BLOCKED")
                lines.append(f"\nNeed domain score >= threshold for L{required_level.value}")
                if risk in (ActionRisk.DESTRUCTIVE, ActionRisk.CRITICAL):
                    lines.append("Or: request approval token with `duro_grant_approval`")

            return [TextContent(type="text", text="\n".join(lines))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    # === EXECUTE TOOL WITH OUTPUT SCANNING (Layer 3 post-execution) ===
    # This closes the "args clean, output leaks" gap by scanning all tool outputs
    #
    # RELIABILITY: Tool execution is wrapped with:
    # 1. Semaphore to limit concurrent executions (prevents overload)
    # 2. Timeout to prevent indefinite hangs
    # 3. Split thread executors (fast vs heavy) to prevent zombie contamination
    # 4. Heavy executor quarantine on timeout (Windows-safe pattern)
    global _tool_semaphore, _heavy_semaphore
    if _tool_semaphore is None:
        _tool_semaphore = asyncio.Semaphore(TOOL_CONCURRENCY_LIMIT)
    if _heavy_semaphore is None:
        _heavy_semaphore = asyncio.Semaphore(1)  # Only 1 heavy op at a time

    timeout = _get_tool_timeout(name)
    loop = asyncio.get_running_loop()
    is_heavy = name in HEAVY_TOOLS

    try:
        # Heavy tools get extra semaphore to prevent dogpiling
        if is_heavy:
            async with _heavy_semaphore:
                # Capture executor INSIDE semaphore to avoid race with reset
                executor = _heavy_executor
                async with _tool_semaphore:
                    try:
                        result = await asyncio.wait_for(
                            loop.run_in_executor(executor, _execute_tool_handler),
                            timeout=timeout
                        )
                    except asyncio.TimeoutError:
                        log_warn(f"Heavy tool '{name}' timed out after {timeout}s - quarantining executor")
                        # Signal cooperative cancellation so zombie thread stops soon
                        if name == "duro_reembed":
                            request_cancel("reembed")
                        elif name == "duro_apply_decay":
                            request_cancel("decay")
                        elif name == "duro_compress_logs":
                            request_cancel("compress")
                        _reset_heavy_executor()
                        return [TextContent(type="text", text=f"## Tool Timeout\n\n**Tool:** `{name}`\n**Timeout:** {timeout} seconds\n\nThe heavy operation timed out. The executor has been reset.\nCancellation signal sent (may take up to 25 items to fully stop).\nYou can retry the operation, or try with smaller batch sizes.\n\nCheck `~/.duro/logs/mcp_server.log` for details.")]
        else:
            async with _tool_semaphore:
                try:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(_fast_executor, _execute_tool_handler),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    log_warn(f"Tool '{name}' timed out after {timeout}s")
                    return [TextContent(type="text", text=f"## Tool Timeout\n\n**Tool:** `{name}`\n**Timeout:** {timeout} seconds\n\nThe tool execution timed out. This may indicate:\n- Heavy operation in progress (try again later)\n- System resource constraints\n- A bug in the tool implementation\n\nCheck `~/.duro/logs/mcp_server.log` for details.")]

        scanned_result = _scan_and_redact_tool_output(name, result)

        # === UNTRUSTED CONTENT WRAPPING (Layer 6 post-execution) ===
        # Browser/web tool outputs are wrapped with provenance markers to prevent
        # prompt injection from web content being treated as trusted instructions
        if PROMPT_FIREWALL_AVAILABLE and INTENT_GUARD_AVAILABLE:
            if name in UNTRUSTED_SOURCE_TOOLS:
                # Mark session as having untrusted output
                domain = arguments.get("url", arguments.get("query", "unknown"))
                if isinstance(domain, str) and len(domain) > 50:
                    domain = domain[:50] + "..."

                # Wrap each text content with untrusted markers
                wrapped_result = []
                for content in scanned_result:
                    if hasattr(content, 'text') and content.text:
                        # Process and wrap the untrusted content
                        processed = process_untrusted_content(
                            content=content.text,
                            domain=domain,
                            tool_name=name,
                            store_in_vault=True  # Store original in vault
                        )
                        # Mark session with the source_id from processing
                        mark_untrusted_output(processed.source_id, domain)
                        wrapped_result.append(TextContent(type="text", text=processed.sanitized_content))

                        # === AUDIT LOGGING (Layer 6 → Layer 5) ===
                        if UNIFIED_AUDIT_AVAILABLE:
                            content_hash = compute_content_hash(content.text)
                            patterns = []

                            # Log injection detection if any
                            if processed.detection.has_injection:
                                patterns = [s.pattern_name for s in processed.detection.signals[:5]]
                                inj_event = build_injection_event(
                                    event_type=EventType.INJECTION_DETECTED,
                                    source_id=processed.source_id,
                                    domain=domain,
                                    severity_detected=processed.detection.highest_severity,
                                    patterns=patterns,
                                    content_hash=content_hash,  # For forensic correlation
                                    reason=f"Injection detected in {name} output",
                                    severity=Severity.WARN,
                                )
                                append_event(inj_event)

                                # Log injection blocked if action denied due to severity
                                if not processed.allowed:
                                    blocked_event = build_injection_event(
                                        event_type=EventType.INJECTION_BLOCKED,
                                        source_id=processed.source_id,
                                        domain=domain,
                                        severity_detected=processed.detection.highest_severity,
                                        patterns=patterns,
                                        content_hash=content_hash,
                                        reason=f"Content blocked: {processed.reason}",
                                        severity=Severity.WARN,
                                    )
                                    append_event(blocked_event)

                            # Log untrusted content received
                            untrusted_event = build_untrusted_content_event(
                                event_type=EventType.UNTRUSTED_CONTENT_RECEIVED,
                                source_id=processed.source_id,
                                domain=domain,
                                tool_name=name,
                                content_hash=content_hash,
                                vault_stored=processed.vault_stored,
                                severity=Severity.INFO,
                            )
                            append_event(untrusted_event)

                            # Log content wrapped
                            wrapped_event = build_untrusted_content_event(
                                event_type=EventType.UNTRUSTED_CONTENT_WRAPPED,
                                source_id=processed.source_id,
                                domain=domain,
                                tool_name=name,
                                content_hash=content_hash,
                                vault_stored=processed.vault_stored,
                                severity=Severity.INFO,
                            )
                            append_event(wrapped_event)
                    else:
                        wrapped_result.append(content)
                return wrapped_result

        return scanned_result
    except Exception as e:
        # Error messages are internal, don't need scanning
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]


async def _run_deferred_startup():
    """Run heavy startup tasks in background after server is listening."""
    await asyncio.sleep(0.5)  # Let server start listening first
    log_info("Running deferred startup consistency check...")
    try:
        _startup_ensure_consistency()
        log_info("Deferred startup: consistency check complete")
    except Exception as e:
        log_warn(f"Deferred startup error (non-fatal): {e}")

    # Preload and warmup embedding model in background thread
    # This prevents first embedding tool call from blocking
    log_info("Preloading embedding model...")
    try:
        # Run in thread to not block event loop
        loop = asyncio.get_running_loop()  # Fixed: must use running loop
        loaded = await loop.run_in_executor(_fast_executor, preload_embedding_model)
        if loaded:
            warmed = await loop.run_in_executor(_fast_executor, warmup_embedding_model)
            if warmed:
                log_info("Deferred startup: embedding model preloaded and warmed")
            else:
                log_warn("Deferred startup: embedding model loaded but warmup failed")
        else:
            log_warn("Deferred startup: embedding model failed to load (semantic search disabled)")
    except Exception as e:
        log_warn(f"Deferred startup: embedding preload error (non-fatal): {e}")

    log_info("Deferred startup complete")


async def main():
    """Run the Duro MCP server."""
    # Initialize autonomy scheduler
    scheduler = _init_autonomy_scheduler()
    if scheduler:
        # Start maintenance loop in background
        asyncio.create_task(scheduler.maintenance.maintenance_loop())

    # Start deferred startup in background
    asyncio.create_task(_run_deferred_startup())

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
