"""Proactive Insights endpoint - surfaces actionable intelligence about memory health."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .stats import get_db_connection

router = APIRouter()

MEMORY_DIR = Path.home() / ".agent" / "memory"
DECISIONS_DIR = MEMORY_DIR / "decisions"
VALIDATIONS_DIR = MEMORY_DIR / "decision_validations"
FACTS_DIR = MEMORY_DIR / "facts"


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


def load_artifact_file(file_path: str) -> dict | None:
    """Load artifact JSON file safely."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def parse_iso_date(date_str: str) -> datetime | None:
    """Parse ISO date string."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


@router.get("/insights/stale")
async def get_stale_knowledge(
    min_age_days: int = Query(14, ge=1),
    min_importance: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(30, ge=1, le=100),
) -> dict[str, Any]:
    """
    Get stale knowledge that needs attention.

    Surfaces:
    - Facts with decaying confidence (not reinforced recently)
    - High-importance facts that are aging
    - Decisions without recent validation

    Staleness = age_days × importance × (1 - last_reinforcement_recency)
    """
    conn = get_db_connection()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=min_age_days)

    stale_facts = []
    stale_decisions = []

    # Get all facts
    cursor = conn.execute("""
        SELECT id, type, title, created_at, file_path
        FROM artifacts
        WHERE type = 'fact' AND file_path IS NOT NULL
        ORDER BY created_at ASC
    """)

    for row in cursor.fetchall():
        content = load_artifact_file(row["file_path"])
        if not content:
            continue

        data = content.get("data", {})
        created_at = parse_iso_date(row["created_at"])
        if not created_at:
            continue

        # Skip if too recent
        if created_at > cutoff:
            continue

        # Calculate staleness
        confidence = data.get("confidence", 0.5)
        importance = data.get("importance", 0.5)
        reinforcement_count = data.get("reinforcement_count", 0)
        last_reinforced = parse_iso_date(data.get("last_reinforced"))
        is_pinned = data.get("pinned", False)

        # Skip pinned facts (they don't decay)
        if is_pinned:
            continue

        # Skip low importance
        if importance < min_importance:
            continue

        # Calculate age
        age_days = (now - created_at).days

        # Calculate days since last reinforcement
        if last_reinforced:
            days_since_reinforcement = (now - last_reinforced).days
        else:
            days_since_reinforcement = age_days  # Never reinforced

        # Staleness score: higher = more stale
        # Age contributes, importance increases urgency, unreinforced facts are more stale
        staleness = (
            (age_days / 30) *
            importance *
            (1 + days_since_reinforcement / 30) *
            (1 - confidence + 0.1)  # Low confidence increases staleness
        )

        stale_facts.append({
            "id": row["id"],
            "title": row["title"] or data.get("claim", "")[:50],
            "claim": data.get("claim", "")[:100],
            "confidence": round(confidence, 2),
            "importance": round(importance, 2),
            "age_days": age_days,
            "days_since_reinforcement": days_since_reinforcement,
            "reinforcement_count": reinforcement_count,
            "staleness_score": round(staleness, 2),
            "tags": data.get("tags", [])[:3],
        })

    # Get decisions without recent validation
    cursor = conn.execute("""
        SELECT id, type, title, created_at, file_path
        FROM artifacts
        WHERE type = 'decision' AND file_path IS NOT NULL
        ORDER BY created_at ASC
    """)

    for row in cursor.fetchall():
        content = load_artifact_file(row["file_path"])
        if not content:
            continue

        data = content.get("data", {})
        created_at = parse_iso_date(row["created_at"])
        if not created_at:
            continue

        # Skip if too recent
        if created_at > cutoff:
            continue

        # Get validation status
        outcome_status = data.get("outcome_status")
        last_validated = parse_iso_date(data.get("last_validated"))
        validation_count = data.get("validation_count", 0)

        # Skip if already validated and recent
        if last_validated and (now - last_validated).days < min_age_days:
            continue

        # Calculate age
        age_days = (now - created_at).days

        # Calculate days since last validation
        if last_validated:
            days_since_validation = (now - last_validated).days
        else:
            days_since_validation = age_days  # Never validated

        # Staleness for decisions
        staleness = (
            (age_days / 30) *
            (1 + days_since_validation / 30)
        )

        # Unvalidated decisions are more urgent
        if outcome_status is None or outcome_status == "pending":
            staleness *= 1.5

        stale_decisions.append({
            "id": row["id"],
            "title": row["title"] or data.get("decision", "")[:50],
            "decision": data.get("decision", "")[:100],
            "age_days": age_days,
            "days_since_validation": days_since_validation,
            "validation_count": validation_count,
            "outcome_status": outcome_status,
            "staleness_score": round(staleness, 2),
            "tags": data.get("tags", [])[:3],
        })

    # Sort by staleness score
    stale_facts.sort(key=lambda x: -x["staleness_score"])
    stale_decisions.sort(key=lambda x: -x["staleness_score"])

    # Limit results
    stale_facts = stale_facts[:limit]
    stale_decisions = stale_decisions[:limit]

    # Stats
    total_stale = len(stale_facts) + len(stale_decisions)
    avg_fact_staleness = sum(f["staleness_score"] for f in stale_facts) / len(stale_facts) if stale_facts else 0
    avg_decision_staleness = sum(d["staleness_score"] for d in stale_decisions) / len(stale_decisions) if stale_decisions else 0

    return {
        "stale_facts": stale_facts,
        "stale_decisions": stale_decisions,
        "stats": {
            "total_stale": total_stale,
            "stale_facts_count": len(stale_facts),
            "stale_decisions_count": len(stale_decisions),
            "avg_fact_staleness": round(avg_fact_staleness, 2),
            "avg_decision_staleness": round(avg_decision_staleness, 2),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/insights/reinforce/{fact_id}")
async def reinforce_fact(fact_id: str) -> dict[str, Any]:
    """
    Reinforce a fact - marks it as recently used/confirmed.
    Resets decay clock and increments reinforcement count.
    """
    conn = get_db_connection()

    # Get the fact
    cursor = conn.execute(
        "SELECT id, file_path FROM artifacts WHERE id = ? AND type = 'fact'",
        (fact_id,)
    )
    row = cursor.fetchone()
    if not row or not row["file_path"]:
        raise HTTPException(status_code=404, detail="Fact not found")

    content = load_artifact_file(row["file_path"])
    if not content:
        raise HTTPException(status_code=500, detail="Could not load fact")

    data = content.get("data", {})
    now = datetime.now(timezone.utc).isoformat()

    # Update reinforcement
    data["last_reinforced"] = now
    data["reinforcement_count"] = data.get("reinforcement_count", 0) + 1

    # Save
    content["data"] = data
    try:
        with open(row["file_path"], "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
        return {
            "success": True,
            "fact_id": fact_id,
            "reinforcement_count": data["reinforcement_count"],
            "last_reinforced": now,
        }
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))
