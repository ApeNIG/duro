"""Changes endpoint - recent change ledger for 48-hour rule."""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

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


@router.get("/changes")
async def get_recent_changes(
    hours: int = Query(48, ge=1, le=168),  # Default 48h, max 1 week
    scope: str | None = None,
    risk_tags: list[str] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Get recent changes from the change ledger."""
    try:
        conn = get_db_connection()

        # Build query
        query = """
            SELECT
                id, title, content, created_at,
                json_extract(content, '$.scope') as scope,
                json_extract(content, '$.change') as change_desc,
                json_extract(content, '$.why') as why,
                json_extract(content, '$.risk_tags') as risk_tags,
                json_extract(content, '$.commit_hash') as commit_hash,
                json_extract(content, '$.quick_checks') as quick_checks
            FROM artifacts
            WHERE type = 'recent_change'
            AND created_at >= datetime('now', ?)
        """
        params: list[Any] = [f'-{hours} hours']

        if scope:
            query += " AND json_extract(content, '$.scope') LIKE ?"
            params.append(f'%{scope}%')

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)

        changes = []
        for row in cursor.fetchall():
            change = {
                "id": row["id"],
                "scope": row["scope"] or "unknown",
                "change": row["change_desc"] or row["title"],
                "why": row["why"],
                "risk_tags": [],
                "commit_hash": row["commit_hash"],
                "quick_checks": [],
                "created_at": row["created_at"],
            }

            # Parse JSON arrays
            if row["risk_tags"]:
                try:
                    import json
                    change["risk_tags"] = json.loads(row["risk_tags"])
                except (json.JSONDecodeError, TypeError):
                    pass

            if row["quick_checks"]:
                try:
                    import json
                    change["quick_checks"] = json.loads(row["quick_checks"])
                except (json.JSONDecodeError, TypeError):
                    pass

            # Filter by risk tags if specified
            if risk_tags:
                if not any(tag in change["risk_tags"] for tag in risk_tags):
                    continue

            changes.append(change)

        # Get risk tag distribution
        cursor = conn.execute("""
            SELECT json_extract(content, '$.risk_tags') as risk_tags
            FROM artifacts
            WHERE type = 'recent_change'
            AND created_at >= datetime('now', ?)
        """, [f'-{hours} hours'])

        tag_counts: dict[str, int] = {}
        for row in cursor.fetchall():
            if row["risk_tags"]:
                try:
                    import json
                    tags = json.loads(row["risk_tags"])
                    for tag in tags:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass

        conn.close()

        return {
            "changes": changes,
            "total": len(changes),
            "hours": hours,
            "risk_tag_distribution": tag_counts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/changes/timeline")
async def get_change_timeline(
    hours: int = Query(48, ge=1, le=168),
) -> dict[str, Any]:
    """Get change timeline grouped by hour for visualization."""
    try:
        conn = get_db_connection()

        cursor = conn.execute("""
            SELECT
                strftime('%Y-%m-%d %H:00', created_at) as hour,
                COUNT(*) as count,
                GROUP_CONCAT(DISTINCT json_extract(content, '$.scope')) as scopes
            FROM artifacts
            WHERE type = 'recent_change'
            AND created_at >= datetime('now', ?)
            GROUP BY hour
            ORDER BY hour DESC
        """, [f'-{hours} hours'])

        timeline = []
        for row in cursor.fetchall():
            timeline.append({
                "hour": row["hour"],
                "count": row["count"],
                "scopes": (row["scopes"] or "").split(",") if row["scopes"] else [],
            })

        conn.close()

        return {
            "timeline": timeline,
            "hours": hours,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
