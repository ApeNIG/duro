"""Episode listing and timeline endpoints."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from .stats import get_db_connection

router = APIRouter()

MEMORY_PATH = Path.home() / ".agent" / "memory"


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert SQLite row to dict with parsed JSON fields."""
    d = dict(row)
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except json.JSONDecodeError:
            d["tags"] = []
    return d


def load_episode_content(file_path: str) -> dict[str, Any] | None:
    """Load full episode content from file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@router.get("/episodes")
async def list_episodes(
    status: Optional[str] = Query(None, description="Filter by status: open or closed"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> dict[str, Any]:
    """List episodes with optional filtering."""
    try:
        conn = get_db_connection()

        # Build query
        conditions = ["type = 'episode'"]
        params = []

        where_clause = f"WHERE {' AND '.join(conditions)}"

        # Get total count
        count_query = f"SELECT COUNT(*) FROM artifacts {where_clause}"
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get episodes
        query = f"""
            SELECT id, type, created_at, updated_at, sensitivity, title, tags, file_path
            FROM artifacts
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor = conn.execute(query, params + [limit, offset])

        episodes = []
        for row in cursor.fetchall():
            episode = row_to_dict(row)

            # Load full content to get status, actions, result
            if episode.get("file_path"):
                content = load_episode_content(episode["file_path"])
                if content:
                    episode["goal"] = content.get("goal")
                    episode["plan"] = content.get("plan", [])
                    episode["actions"] = content.get("actions", [])
                    episode["result"] = content.get("result")
                    episode["result_summary"] = content.get("result_summary")
                    episode["status"] = content.get("status", "open")
                    episode["duration_mins"] = content.get("duration_mins")
                    episode["links"] = content.get("links", {})

            # Filter by status if specified
            if status and episode.get("status") != status:
                continue

            episodes.append(episode)

        return {
            "episodes": episodes[:limit],  # Respect limit after filtering
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(episodes) < total,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/episodes/{episode_id}")
async def get_episode(episode_id: str) -> dict[str, Any]:
    """Get a single episode with full details including actions."""
    try:
        conn = get_db_connection()

        cursor = conn.execute(
            "SELECT * FROM artifacts WHERE id = ? AND type = 'episode'",
            (episode_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Episode not found")

        episode = row_to_dict(row)

        # Load full content
        if episode.get("file_path"):
            content = load_episode_content(episode["file_path"])
            if content:
                episode["content"] = content

        # Try to find related evaluation
        eval_cursor = conn.execute("""
            SELECT id, file_path FROM artifacts
            WHERE type = 'evaluation' AND title LIKE ?
            ORDER BY created_at DESC LIMIT 1
        """, (f"%{episode_id}%",))
        eval_row = eval_cursor.fetchone()

        if eval_row:
            eval_content = load_episode_content(eval_row["file_path"])
            if eval_content:
                episode["evaluation"] = {
                    "id": eval_row["id"],
                    "grade": eval_content.get("grade"),
                    "rubric": eval_content.get("rubric"),
                    "next_change": eval_content.get("next_change"),
                }

        return episode
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/episodes/stats/summary")
async def get_episode_stats() -> dict[str, Any]:
    """Get summary statistics for episodes."""
    try:
        conn = get_db_connection()

        # Count total episodes
        cursor = conn.execute(
            "SELECT COUNT(*) FROM artifacts WHERE type = 'episode'"
        )
        total = cursor.fetchone()[0]

        # Load all episodes to count by status and result
        cursor = conn.execute("""
            SELECT file_path FROM artifacts WHERE type = 'episode'
        """)

        status_counts = {"open": 0, "closed": 0}
        result_counts = {"success": 0, "partial": 0, "failed": 0}
        total_duration = 0
        duration_count = 0

        for row in cursor.fetchall():
            content = load_episode_content(row["file_path"])
            if content:
                status = content.get("status", "open")
                status_counts[status] = status_counts.get(status, 0) + 1

                result = content.get("result")
                if result:
                    result_counts[result] = result_counts.get(result, 0) + 1

                duration = content.get("duration_mins")
                if duration:
                    total_duration += duration
                    duration_count += 1

        return {
            "total": total,
            "by_status": status_counts,
            "by_result": result_counts,
            "avg_duration_mins": round(total_duration / duration_count, 1) if duration_count > 0 else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
