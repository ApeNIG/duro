"""Health and maintenance endpoints - decay queue, maintenance actions."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Duro database path
DURO_DB_PATH = Path.home() / ".agent" / "memory" / "index.db"


def get_db_connection() -> sqlite3.Connection:
    """Get read-only connection to Duro database."""
    if not DURO_DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Duro database not found")

    conn = sqlite3.connect(f"file:{DURO_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 3000")
    return conn


@router.get("/health/decay-queue")
async def get_decay_queue(
    limit: int = 10,
) -> dict[str, Any]:
    """Get facts sorted by decay priority (age x importance x low reinforcement)."""
    try:
        conn = get_db_connection()

        # Get facts with decay scoring using actual schema columns
        cursor = conn.execute("""
            SELECT
                id, title, type,
                created_at, updated_at,
                COALESCE(importance, 0.5) as importance,
                COALESCE(reinforcement_count, 0) as reinforcement_count,
                COALESCE(pinned, 0) as pinned,
                file_path,
                julianday('now') - julianday(updated_at) as days_since_update
            FROM artifacts
            WHERE type = 'fact'
            AND COALESCE(pinned, 0) != 1
            ORDER BY
                (julianday('now') - julianday(updated_at)) *
                COALESCE(importance, 0.5) /
                (COALESCE(reinforcement_count, 0) + 1)
            DESC
            LIMIT ?
        """, (limit,))

        facts = []
        for row in cursor.fetchall():
            # Try to read claim from file if exists
            claim = row["title"]
            confidence = 0.5
            verification_state = "unverified"

            if row["file_path"]:
                try:
                    import json
                    file_path = Path(row["file_path"])
                    if file_path.exists():
                        with open(file_path) as f:
                            data = json.load(f)
                            claim = data.get("claim", claim)
                            confidence = data.get("confidence", confidence)
                            verification_state = data.get("verification_state", verification_state)
                except:
                    pass

            facts.append({
                "id": row["id"],
                "claim": claim,
                "confidence": confidence,
                "importance": row["importance"],
                "reinforcement_count": row["reinforcement_count"],
                "verification_state": verification_state,
                "days_since_update": round(row["days_since_update"], 1),
                "updated_at": row["updated_at"],
            })

        conn.close()

        return {
            "queue": facts,
            "total": len(facts),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/maintenance")
async def get_maintenance_report() -> dict[str, Any]:
    """Get maintenance health report."""
    try:
        conn = get_db_connection()

        # Total facts
        cursor = conn.execute("SELECT COUNT(*) FROM artifacts WHERE type = 'fact'")
        total_facts = cursor.fetchone()[0]

        # Pinned facts (using actual column)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM artifacts
            WHERE type = 'fact'
            AND COALESCE(pinned, 0) = 1
        """)
        pinned_facts = cursor.fetchone()[0]

        # Stale facts (not updated in 30+ days)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM artifacts
            WHERE type = 'fact'
            AND julianday('now') - julianday(updated_at) > 30
            AND COALESCE(pinned, 0) != 1
        """)
        stale_facts = cursor.fetchone()[0]

        # Unverified facts - for now assume all without file_path are unverified
        # In a full implementation we'd read the JSON files
        cursor = conn.execute("""
            SELECT COUNT(*) FROM artifacts
            WHERE type = 'fact'
        """)
        unverified_facts = total_facts  # Simplified - would need file reads

        # Low reinforcement facts (proxy for low confidence)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM artifacts
            WHERE type = 'fact'
            AND COALESCE(reinforcement_count, 0) = 0
        """)
        low_confidence = cursor.fetchone()[0]

        # Artifact type counts
        cursor = conn.execute("""
            SELECT type, COUNT(*) as count
            FROM artifacts
            GROUP BY type
        """)
        type_counts = {row["type"]: row["count"] for row in cursor.fetchall()}

        conn.close()

        return {
            "facts": {
                "total": total_facts,
                "pinned": pinned_facts,
                "pinned_pct": round(pinned_facts / max(total_facts, 1) * 100, 1),
                "stale": stale_facts,
                "stale_pct": round(stale_facts / max(total_facts, 1) * 100, 1),
                "unverified": unverified_facts,
                "low_confidence": low_confidence,
            },
            "artifact_counts": type_counts,
            "health_score": max(0, 100 - (stale_facts / max(total_facts, 1) * 50) - (low_confidence / max(total_facts, 1) * 30)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/embedding-status")
async def get_embedding_status() -> dict[str, Any]:
    """Get embedding coverage status."""
    try:
        conn = get_db_connection()

        # Total artifacts
        cursor = conn.execute("SELECT COUNT(*) FROM artifacts")
        total = cursor.fetchone()[0]

        # Check for embeddings table
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='embeddings'
        """)
        has_embeddings_table = cursor.fetchone() is not None

        embedded_count = 0
        if has_embeddings_table:
            cursor = conn.execute("SELECT COUNT(DISTINCT artifact_id) FROM embeddings")
            embedded_count = cursor.fetchone()[0]

        conn.close()

        return {
            "total_artifacts": total,
            "embedded": embedded_count,
            "coverage_pct": round(embedded_count / max(total, 1) * 100, 1),
            "missing": total - embedded_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
