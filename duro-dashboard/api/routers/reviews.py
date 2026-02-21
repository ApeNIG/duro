"""Decision review endpoints."""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .stats import get_db_connection

router = APIRouter()


class ReviewRequest(BaseModel):
    decision_id: str
    status: str  # 'validated', 'partial', or 'reversed'
    notes: Optional[str] = None


class ReviewResponse(BaseModel):
    success: bool
    message: str
    validation_id: Optional[str] = None


@router.post("/reviews", response_model=ReviewResponse)
async def create_review(request: ReviewRequest):
    """
    Submit a review for a decision.
    Creates a validation file in the Duro format.
    """
    import json
    import random
    import string

    try:
        # Generate validation ID in Duro format
        now = datetime.now(timezone.utc)
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        validation_id = f"dval_{now.strftime('%Y%m%d_%H%M%S')}_{random_suffix}"

        # Create validation artifact in Duro format
        artifact = {
            "id": validation_id,
            "type": "decision_validation",
            "version": "1.0",
            "created_at": now.isoformat() + "Z",
            "updated_at": None,
            "sensitivity": "internal",
            "tags": ["decision-closure", "dashboard-review"],
            "source": {
                "workflow": "dashboard",
                "run_id": None,
                "tool_trace_path": None
            },
            "data": {
                "decision_id": request.decision_id,
                "status": request.status,
                "result": "success" if request.status == "validated" else ("partial" if request.status == "partial" else "failed"),
                "confidence_delta": 0.1 if request.status == "validated" else (0.0 if request.status == "partial" else -0.1),
                "confidence_after": None,
                "notes": request.notes or f"Marked as {request.status} via dashboard"
            }
        }

        # Write to file
        validations_dir = Path.home() / ".agent" / "memory" / "decision_validations"
        validations_dir.mkdir(parents=True, exist_ok=True)

        file_path = validations_dir / f"{validation_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2)

        # Also update the decision file directly to set outcome_status
        decisions_dir = Path.home() / ".agent" / "memory" / "decisions"
        decision_file = decisions_dir / f"{request.decision_id}.json"

        if decision_file.exists():
            try:
                with open(decision_file, "r", encoding="utf-8") as f:
                    decision_data = json.load(f)

                # Update outcome_status in the decision file
                if "data" in decision_data:
                    decision_data["data"]["outcome_status"] = request.status
                else:
                    decision_data["outcome_status"] = request.status

                decision_data["updated_at"] = now.isoformat() + "Z"

                with open(decision_file, "w", encoding="utf-8") as f:
                    json.dump(decision_data, f, indent=2)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: Could not update decision file: {e}")

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
    try:
        conn = get_db_connection()

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

            # Check for validation status
            # First check if decision file has outcome_status
            if file_path:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                        # Check in data.outcome_status or directly
                        if "data" in file_data and file_data["data"].get("outcome_status"):
                            decision["outcome_status"] = file_data["data"]["outcome_status"]
                        elif file_data.get("outcome_status"):
                            decision["outcome_status"] = file_data["outcome_status"]
                except (json.JSONDecodeError, FileNotFoundError, OSError):
                    pass

            # If not found in decision file, search validation files
            if not decision.get("outcome_status"):
                validations_dir = Path.home() / ".agent" / "memory" / "decision_validations"
                if validations_dir.exists():
                    # Find latest validation for this decision
                    latest_validation = None
                    latest_time = None

                    for val_file in validations_dir.glob("dval_*.json"):
                        try:
                            with open(val_file, "r", encoding="utf-8") as f:
                                val_data = json.load(f)
                                if val_data.get("data", {}).get("decision_id") == row["id"]:
                                    val_time = val_data.get("created_at", "")
                                    if latest_time is None or val_time > latest_time:
                                        latest_time = val_time
                                        latest_validation = val_data
                        except (json.JSONDecodeError, OSError):
                            continue

                    if latest_validation:
                        decision["outcome_status"] = latest_validation.get("data", {}).get("status", "pending")

            # Default to pending if no status found
            if not decision.get("outcome_status"):
                decision["outcome_status"] = "pending"

            # Filter by status if requested
            if status is None or decision["outcome_status"] == status:
                decisions.append(decision)

        # Get total count
        count_cursor = conn.execute("SELECT COUNT(*) FROM artifacts WHERE type = 'decision'")
        total = count_cursor.fetchone()[0]

        return {
            "decisions": decisions,
            "total": total,
            "has_more": offset + limit < total
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
