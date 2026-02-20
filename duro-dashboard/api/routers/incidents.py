"""Incident dashboard endpoints."""

import sqlite3
import json
from pathlib import Path
from typing import Any, Optional
from collections import Counter

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

DURO_DB_PATH = Path.home() / ".agent" / "memory" / "index.db"


def get_db_connection() -> sqlite3.Connection:
    """Create read-only connection to Duro database."""
    if not DURO_DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Duro database not found")

    conn = sqlite3.connect(f"file:{DURO_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 3000")
    return conn


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert SQLite row to dict with parsed JSON fields."""
    d = dict(row)
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except json.JSONDecodeError:
            d["tags"] = []
    return d


def load_json_file(path: str) -> dict[str, Any] | None:
    """Load a JSON file safely."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@router.get("/incidents")
async def list_incidents(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> dict[str, Any]:
    """List incidents with optional filtering."""
    try:
        conn = get_db_connection()

        # Build query - incidents are stored as 'incident_rca' type
        conditions = ["type = 'incident_rca'"]
        params = []

        where_clause = f"WHERE {' AND '.join(conditions)}"

        # Get total count
        count_query = f"SELECT COUNT(*) FROM artifacts {where_clause}"
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get incidents
        query = f"""
            SELECT id, type, created_at, updated_at, sensitivity, title, tags, file_path
            FROM artifacts
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor = conn.execute(query, params + [limit, offset])

        incidents = []
        for row in cursor.fetchall():
            incident = row_to_dict(row)

            # Load full content
            if incident.get("file_path"):
                content = load_json_file(incident["file_path"])
                if content:
                    incident["symptom"] = content.get("symptom")
                    incident["actual_cause"] = content.get("actual_cause")
                    incident["fix"] = content.get("fix")
                    incident["prevention"] = content.get("prevention")
                    incident["severity"] = content.get("severity", "medium")
                    incident["repro_steps"] = content.get("repro_steps", [])
                    incident["first_bad_boundary"] = content.get("first_bad_boundary")
                    incident["why_not_caught"] = content.get("why_not_caught")

            # Filter by severity if specified
            if severity and incident.get("severity") != severity:
                continue

            incidents.append(incident)

        conn.close()

        return {
            "incidents": incidents[:limit],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(incidents) < total,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict[str, Any]:
    """Get a single incident with full RCA details."""
    try:
        conn = get_db_connection()

        cursor = conn.execute(
            "SELECT * FROM artifacts WHERE id = ? AND type = 'incident_rca'",
            (incident_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")

        incident = row_to_dict(row)

        # Load full content
        if incident.get("file_path"):
            content = load_json_file(incident["file_path"])
            if content:
                incident["content"] = content

        conn.close()

        return incident
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/stats/summary")
async def get_incident_stats() -> dict[str, Any]:
    """Get summary statistics and patterns for incidents."""
    try:
        conn = get_db_connection()

        cursor = conn.execute("""
            SELECT file_path, tags FROM artifacts WHERE type = 'incident_rca'
        """)

        severity_counts = Counter()
        boundary_counts = Counter()
        tag_counts = Counter()
        all_causes = []

        for row in cursor.fetchall():
            content = load_json_file(row["file_path"]) if row["file_path"] else None

            if content:
                severity = content.get("severity", "medium")
                severity_counts[severity] += 1

                boundary = content.get("first_bad_boundary")
                if boundary:
                    boundary_counts[boundary] += 1

                cause = content.get("actual_cause")
                if cause:
                    all_causes.append(cause)

            # Count tags
            tags_str = row["tags"]
            if tags_str:
                try:
                    tags = json.loads(tags_str)
                    for tag in tags:
                        tag_counts[tag] += 1
                except json.JSONDecodeError:
                    pass

        conn.close()

        return {
            "total": sum(severity_counts.values()),
            "by_severity": dict(severity_counts),
            "common_boundaries": [
                {"boundary": b, "count": c}
                for b, c in boundary_counts.most_common(5)
            ],
            "common_tags": [
                {"tag": t, "count": c}
                for t, c in tag_counts.most_common(10)
            ],
            "recent_causes": all_causes[:5],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents/patterns")
async def get_incident_patterns() -> dict[str, Any]:
    """Analyze incident patterns for recurring issues."""
    try:
        conn = get_db_connection()

        cursor = conn.execute("""
            SELECT file_path, created_at FROM artifacts
            WHERE type = 'incident_rca'
            ORDER BY created_at DESC
        """)

        # Collect data for pattern analysis
        boundaries = []
        preventions = []
        why_not_caught = []

        for row in cursor.fetchall():
            content = load_json_file(row["file_path"]) if row["file_path"] else None
            if content:
                if content.get("first_bad_boundary"):
                    boundaries.append(content["first_bad_boundary"])
                if content.get("prevention"):
                    preventions.append(content["prevention"])
                if content.get("why_not_caught"):
                    why_not_caught.append(content["why_not_caught"])

        conn.close()

        # Analyze patterns
        boundary_freq = Counter(boundaries)

        return {
            "recurring_boundaries": [
                {"boundary": b, "occurrences": c}
                for b, c in boundary_freq.most_common(5)
                if c > 1  # Only show recurring
            ],
            "preventions_implemented": preventions[:10],
            "detection_gaps": why_not_caught[:10],
            "pattern_summary": {
                "total_incidents": len(boundaries),
                "unique_boundaries": len(set(boundaries)),
                "has_recurring_patterns": any(c > 1 for c in boundary_freq.values()),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
