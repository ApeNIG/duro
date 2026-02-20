"""Stats and health endpoints."""

import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Duro database path
DURO_DB_PATH = Path.home() / ".agent" / "memory" / "index.db"


def get_db_connection() -> sqlite3.Connection:
    """Create read-only connection to Duro database."""
    if not DURO_DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Duro database not found")

    conn = sqlite3.connect(f"file:{DURO_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 3000")
    return conn


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Server health check with latency measurement."""
    start = time.perf_counter()

    try:
        conn = get_db_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM artifacts")
        count = cursor.fetchone()[0]
        conn.close()

        latency_ms = (time.perf_counter() - start) * 1000

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "database": "connected",
            "artifact_count": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "status": "degraded",
            "latency_ms": round(latency_ms, 2),
            "database": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Get artifact counts by type and other statistics."""
    try:
        conn = get_db_connection()

        # Count by type
        cursor = conn.execute("""
            SELECT type, COUNT(*) as count
            FROM artifacts
            GROUP BY type
            ORDER BY count DESC
        """)
        type_counts = {row["type"]: row["count"] for row in cursor.fetchall()}

        # Total count
        cursor = conn.execute("SELECT COUNT(*) FROM artifacts")
        total = cursor.fetchone()[0]

        # Recent activity (last 24h)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM artifacts
            WHERE created_at >= datetime('now', '-24 hours')
        """)
        recent_24h = cursor.fetchone()[0]

        # Last artifact timestamp
        cursor = conn.execute("""
            SELECT created_at FROM artifacts
            ORDER BY created_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        last_activity = row["created_at"] if row else None

        # Count by sensitivity
        cursor = conn.execute("""
            SELECT sensitivity, COUNT(*) as count
            FROM artifacts
            GROUP BY sensitivity
        """)
        sensitivity_counts = {row["sensitivity"]: row["count"] for row in cursor.fetchall()}

        conn.close()

        return {
            "total": total,
            "by_type": type_counts,
            "by_sensitivity": sensitivity_counts,
            "recent_24h": recent_24h,
            "last_activity": last_activity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
