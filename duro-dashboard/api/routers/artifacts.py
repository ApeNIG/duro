"""Artifact listing and detail endpoints."""

import sqlite3
import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .stats import get_db_connection, DURO_DB_PATH

router = APIRouter()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert SQLite row to dict with parsed JSON fields."""
    d = dict(row)
    # Parse JSON fields
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except json.JSONDecodeError:
            d["tags"] = []
    if d.get("source_urls"):
        try:
            d["source_urls"] = json.loads(d["source_urls"])
        except json.JSONDecodeError:
            d["source_urls"] = []
    return d


@router.get("/artifacts")
async def list_artifacts(
    type: Optional[str] = Query(None, description="Filter by artifact type"),
    sensitivity: Optional[str] = Query(None, description="Filter by sensitivity"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    search: Optional[str] = Query(None, description="Search in title"),
) -> dict[str, Any]:
    """List artifacts with optional filtering and pagination."""
    try:
        conn = get_db_connection()

        # Build query
        conditions = []
        params = []

        if type:
            conditions.append("type = ?")
            params.append(type)
        if sensitivity:
            conditions.append("sensitivity = ?")
            params.append(sensitivity)
        if search:
            conditions.append("title LIKE ?")
            params.append(f"%{search}%")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Get total count
        count_query = f"SELECT COUNT(*) FROM artifacts {where_clause}"
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get artifacts
        query = f"""
            SELECT id, type, created_at, updated_at, sensitivity, title, tags, source_workflow
            FROM artifacts
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor = conn.execute(query, params + [limit, offset])
        artifacts = [row_to_dict(row) for row in cursor.fetchall()]

        return {
            "artifacts": artifacts,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(artifacts) < total,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class BulkDeleteRequest(BaseModel):
    """Request model for bulk delete."""
    artifact_ids: list[str]


@router.post("/artifacts/bulk-delete")
async def bulk_delete_artifacts(request: BulkDeleteRequest) -> dict[str, Any]:
    """Delete multiple artifacts by ID."""
    try:
        conn = sqlite3.connect(str(DURO_DB_PATH), timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.row_factory = sqlite3.Row

        deleted = []
        failed = []

        for artifact_id in request.artifact_ids:
            try:
                cursor = conn.execute(
                    "SELECT id, file_path, type, title FROM artifacts WHERE id = ?",
                    (artifact_id,)
                )
                row = cursor.fetchone()

                if not row:
                    failed.append({"id": artifact_id, "reason": "not found"})
                    continue

                artifact = dict(row)
                file_path = artifact.get("file_path")

                # Delete from database
                conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))

                # Delete the file if it exists
                if file_path:
                    path = Path(file_path)
                    if path.exists():
                        path.unlink()

                deleted.append({
                    "id": artifact_id,
                    "type": artifact.get("type"),
                    "title": artifact.get("title"),
                })
            except Exception as e:
                failed.append({"id": artifact_id, "reason": str(e)})

        conn.commit()
        conn.close()

        return {
            "success": True,
            "deleted_count": len(deleted),
            "deleted": deleted,
            "failed_count": len(failed),
            "failed": failed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str) -> dict[str, Any]:
    """Get a single artifact by ID with full details."""
    try:
        conn = get_db_connection()

        cursor = conn.execute(
            "SELECT * FROM artifacts WHERE id = ?",
            (artifact_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Artifact not found")

        artifact = row_to_dict(row)

        # Try to read the actual artifact file for full content
        file_path = artifact.get("file_path")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    artifact["content"] = json.load(f)
            except Exception:
                artifact["content"] = None

        return artifact
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/artifacts/{artifact_id}")
async def delete_artifact(artifact_id: str) -> dict[str, Any]:
    """Delete an artifact by ID."""
    try:
        # First get the artifact to find the file path
        conn = sqlite3.connect(str(DURO_DB_PATH), timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT id, file_path, type, title FROM artifacts WHERE id = ?",
            (artifact_id,)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Artifact not found")

        artifact = dict(row)
        file_path = artifact.get("file_path")

        # Delete from database
        conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
        conn.commit()
        conn.close()

        # Delete the file if it exists
        if file_path:
            path = Path(file_path)
            if path.exists():
                path.unlink()

        return {
            "success": True,
            "deleted_id": artifact_id,
            "type": artifact.get("type"),
            "title": artifact.get("title"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
