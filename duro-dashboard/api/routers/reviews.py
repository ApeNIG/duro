"""Decision review endpoints."""

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Add duro-mcp to path for importing
DURO_MCP_PATH = Path.home() / "duro-mcp"
if DURO_MCP_PATH.exists():
    sys.path.insert(0, str(DURO_MCP_PATH))

router = APIRouter()


class ReviewRequest(BaseModel):
    decision_id: str
    status: str  # 'validated' or 'reversed'
    notes: Optional[str] = None


class ReviewResponse(BaseModel):
    success: bool
    message: str
    validation_id: Optional[str] = None


@router.post("/reviews", response_model=ReviewResponse)
async def create_review(request: ReviewRequest):
    """
    Submit a review for a decision.
    Calls the Duro MCP validate_decision tool.
    """
    try:
        # Try to use Duro MCP tools directly
        try:
            from src.tools.decision_tools import validate_decision

            result = await validate_decision(
                decision_id=request.decision_id,
                status=request.status,
                notes=request.notes or "",
                actual_outcome=request.notes or f"Marked as {request.status} via dashboard",
            )

            return ReviewResponse(
                success=True,
                message=f"Decision {request.status}",
                validation_id=result.get("validation_id") if isinstance(result, dict) else None
            )
        except ImportError:
            # Fallback: Store as a simple validation artifact
            import sqlite3
            import json
            import uuid

            DURO_DB_PATH = Path.home() / ".agent" / "memory" / "index.db"

            validation_id = f"val_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            # Create validation artifact
            artifact = {
                "id": validation_id,
                "type": "decision_validation",
                "created_at": now,
                "title": f"Review: {request.status} - {request.decision_id[:20]}",
                "sensitivity": "internal",
                "workflow": "dashboard",
                "tags": ["dashboard-review", request.status],
                "decision_id": request.decision_id,
                "status": request.status,
                "notes": request.notes,
                "timestamp": now,
            }

            conn = sqlite3.connect(str(DURO_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO artifacts (id, type, created_at, title, sensitivity, tags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                validation_id,
                "decision_validation",
                now,
                artifact["title"],
                "internal",
                json.dumps(artifact["tags"]),
                json.dumps(artifact)
            ))

            conn.commit()
            conn.close()

            return ReviewResponse(
                success=True,
                message=f"Decision {request.status}",
                validation_id=validation_id
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions")
async def get_decisions(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Get decisions with optional status filter.
    Status can be: pending, validated, reversed, superseded
    """
    import sqlite3
    import json

    DURO_DB_PATH = Path.home() / ".agent" / "memory" / "index.db"

    try:
        conn = sqlite3.connect(f"file:{DURO_DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        # Get decisions
        query = """
            SELECT id, type, created_at, title, sensitivity, tags, file_path
            FROM artifacts
            WHERE type = 'decision'
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """

        cursor = conn.execute(query, (limit, offset))
        decisions = []

        for row in cursor.fetchall():
            decision = {
                "id": row["id"],
                "type": row["type"],
                "created_at": row["created_at"],
                "title": row["title"],
                "sensitivity": row["sensitivity"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
            }

            # Try to read additional data from file
            file_path = row["file_path"]
            if file_path:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                        decision["decision"] = file_data.get("decision")
                        decision["rationale"] = file_data.get("rationale")
                        decision["alternatives"] = file_data.get("alternatives")
                        decision["context"] = file_data.get("context")
                        decision["confidence"] = file_data.get("confidence")
                except (json.JSONDecodeError, FileNotFoundError, OSError):
                    pass

            # Check for validation status by searching validation artifacts
            val_cursor = conn.execute("""
                SELECT file_path FROM artifacts
                WHERE type = 'decision_validation'
                AND title LIKE ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (f'%{row["id"]}%',))

            val_row = val_cursor.fetchone()
            if val_row and val_row["file_path"]:
                try:
                    with open(val_row["file_path"], "r", encoding="utf-8") as f:
                        val_data = json.load(f)
                        decision["outcome_status"] = val_data.get("status", "pending")
                except (json.JSONDecodeError, FileNotFoundError, OSError):
                    decision["outcome_status"] = "pending"
            else:
                decision["outcome_status"] = "pending"

            # Filter by status if requested
            if status is None or decision["outcome_status"] == status:
                decisions.append(decision)

        # Get total count
        count_cursor = conn.execute("SELECT COUNT(*) FROM artifacts WHERE type = 'decision'")
        total = count_cursor.fetchone()[0]

        conn.close()

        return {
            "decisions": decisions,
            "total": total,
            "has_more": offset + limit < total
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
