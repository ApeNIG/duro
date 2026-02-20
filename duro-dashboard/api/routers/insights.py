"""Proactive Insights endpoint - surfaces actionable intelligence about memory health."""

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

DURO_DB_PATH = Path.home() / ".agent" / "memory" / "index.db"
DECISIONS_DIR = Path.home() / ".agent" / "memory" / "decisions"
VALIDATIONS_DIR = Path.home() / ".agent" / "memory" / "decision_validations"


def get_db_connection() -> sqlite3.Connection:
    """Create read-only connection to Duro database."""
    if not DURO_DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Duro database not found")

    conn = sqlite3.connect(f"file:{DURO_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 3000")
    return conn


def get_decision_outcome_status(decision_id: str, file_path: str | None) -> str | None:
    """Get outcome_status from decision file or validation files."""
    # First check decision file
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "data" in data and data["data"].get("outcome_status"):
                    return data["data"]["outcome_status"]
                if data.get("outcome_status"):
                    return data["outcome_status"]
        except (json.JSONDecodeError, FileNotFoundError, OSError):
            pass

    # Check validation files
    if VALIDATIONS_DIR.exists():
        latest_time = None
        latest_status = None

        for val_file in VALIDATIONS_DIR.glob("dval_*.json"):
            try:
                with open(val_file, "r", encoding="utf-8") as f:
                    val_data = json.load(f)
                    if val_data.get("data", {}).get("decision_id") == decision_id:
                        val_time = val_data.get("created_at", "")
                        if latest_time is None or val_time > latest_time:
                            latest_time = val_time
                            latest_status = val_data.get("data", {}).get("status")
            except (json.JSONDecodeError, OSError):
                continue

        if latest_status:
            return latest_status

    return None


def calculate_age_days(created_at: str) -> int:
    """Calculate days since created_at timestamp."""
    try:
        # Handle various datetime formats
        created_at = created_at.replace("Z", "+00:00")
        if "." in created_at:
            dt = datetime.fromisoformat(created_at)
        else:
            dt = datetime.fromisoformat(created_at)

        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return (now - dt).days
    except (ValueError, TypeError):
        return 0


def get_priority(age_days: int) -> str:
    """Determine priority based on age."""
    if age_days >= 30:
        return "high"
    elif age_days >= 14:
        return "medium"
    return "low"


@router.get("/insights")
async def get_insights() -> dict[str, Any]:
    """
    Get proactive insights about memory health and decisions needing review.

    v1 Metrics (honest, reliable):
    - Total facts and decisions (from DB)
    - Decisions pending review (file scan)
    - Oldest unreviewed decision age
    - Recent activity (24h)
    """
    try:
        conn = get_db_connection()

        # Get total facts
        cursor = conn.execute("SELECT COUNT(*) FROM artifacts WHERE type = 'fact'")
        total_facts = cursor.fetchone()[0]

        # Get total decisions
        cursor = conn.execute("SELECT COUNT(*) FROM artifacts WHERE type = 'decision'")
        total_decisions = cursor.fetchone()[0]

        # Get recent activity (last 24h)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM artifacts
            WHERE created_at >= datetime('now', '-24 hours')
        """)
        recent_24h = cursor.fetchone()[0]

        # Get all decisions to check their review status
        cursor = conn.execute("""
            SELECT id, title, created_at, file_path
            FROM artifacts
            WHERE type = 'decision'
            ORDER BY created_at ASC
        """)

        pending_decisions = []
        for row in cursor.fetchall():
            decision_id = row["id"]
            file_path = row["file_path"]
            outcome_status = get_decision_outcome_status(decision_id, file_path)

            # If no outcome_status or pending, it needs review
            if outcome_status is None or outcome_status == "pending":
                age_days = calculate_age_days(row["created_at"])
                pending_decisions.append({
                    "type": "unreviewed_decision",
                    "id": decision_id,
                    "title": row["title"] or decision_id[:30],
                    "age_days": age_days,
                    "priority": get_priority(age_days),
                })

        conn.close()

        # Sort by age (oldest first) and limit to top 20
        pending_decisions.sort(key=lambda x: -x["age_days"])
        action_items = pending_decisions[:20]

        # Calculate oldest unreviewed
        oldest_unreviewed_days = action_items[0]["age_days"] if action_items else 0

        return {
            "summary": {
                "total_facts": total_facts,
                "total_decisions": total_decisions,
                "pending_review": len(pending_decisions),
                "oldest_unreviewed_days": oldest_unreviewed_days,
                "recent_24h": recent_24h,
            },
            "action_items": action_items,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
