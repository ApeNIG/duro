"""Promotion Pipeline endpoints - Surface validated decisions ready for promotion."""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .stats import get_db_connection

router = APIRouter()

DECISIONS_DIR = Path.home() / ".agent" / "memory" / "decisions"
VALIDATIONS_DIR = Path.home() / ".agent" / "memory" / "decision_validations"


class PromotionCandidate(BaseModel):
    decision_id: str
    decision_text: str
    confidence: float
    validation_count: int
    status: str
    tags: List[str]
    created_at: str
    last_validated: Optional[str]
    promotion_score: float
    promotion_ready: bool
    suggested_type: str  # "law", "pattern", "skill"


class PromoteRequest(BaseModel):
    decision_id: str
    target_type: str  # "law" or "pattern"
    project_id: Optional[str] = "duro"  # Default project
    law_id: Optional[str] = None
    strength: Optional[str] = "soft"  # "hard" or "soft"


@router.get("/promotions")
async def get_promotion_candidates(
    min_confidence: float = 0.7,
    min_validations: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get decisions that are candidates for promotion to laws/patterns.

    A decision is a candidate if:
    - confidence >= min_confidence
    - validation_count >= min_validations
    - status = 'validated'

    Promotion score = confidence * 10 + validation_count * 2 + (prevented_failure * 3)
    Ready if score >= 10
    """
    conn = get_db_connection()

    # Get all decisions
    query = """
        SELECT id, type, created_at, title, tags, file_path
        FROM artifacts
        WHERE type = 'decision'
        ORDER BY created_at DESC
    """
    cursor = conn.execute(query)

    candidates = []

    for row in cursor.fetchall():
        decision_id = row["id"]
        file_path = row["file_path"]

        if not file_path or not Path(file_path).exists():
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                decision_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # Extract decision info
        data = decision_data.get("data", decision_data)
        confidence = 0.5
        status = "pending"
        decision_text = data.get("decision", row["title"] or "")[:200]

        # Get confidence from outcome
        outcome = data.get("outcome", {})
        if isinstance(outcome, dict):
            confidence = outcome.get("confidence", 0.5)
            status = outcome.get("status", "pending")

        # Skip if not validated or low confidence
        if status != "validated" or confidence < min_confidence:
            continue

        # Count validations for this decision
        validation_count = 0
        last_validated = None
        prevented_failure = False

        if VALIDATIONS_DIR.exists():
            for val_file in VALIDATIONS_DIR.glob("dval_*.json"):
                try:
                    with open(val_file, "r", encoding="utf-8") as f:
                        val_data = json.load(f)
                    if val_data.get("data", {}).get("decision_id") == decision_id:
                        validation_count += 1
                        val_time = val_data.get("created_at")
                        if last_validated is None or (val_time and val_time > last_validated):
                            last_validated = val_time
                        # Check if validation mentions preventing failure
                        notes = val_data.get("data", {}).get("notes", "")
                        if "prevent" in notes.lower() or "avoid" in notes.lower() or "caught" in notes.lower():
                            prevented_failure = True
                except (json.JSONDecodeError, OSError):
                    continue

        if validation_count < min_validations:
            continue

        # Calculate promotion score
        # confidence * 10 (max 10) + validations * 2 (unbounded) + prevented_failure * 3
        promotion_score = (confidence * 10) + (validation_count * 2) + (3 if prevented_failure else 0)
        promotion_ready = promotion_score >= 10

        # Suggest promotion type based on tags and content
        tags = json.loads(row["tags"]) if row["tags"] else []
        suggested_type = "pattern"  # default

        rule_indicators = ["rule", "hard-rule", "always", "never", "must", "constraint", "law"]
        if any(indicator in str(tags).lower() or indicator in decision_text.lower() for indicator in rule_indicators):
            suggested_type = "law"

        skill_indicators = ["workflow", "process", "procedure", "how-to", "step"]
        if any(indicator in str(tags).lower() or indicator in decision_text.lower() for indicator in skill_indicators):
            suggested_type = "skill"

        candidates.append(PromotionCandidate(
            decision_id=decision_id,
            decision_text=decision_text,
            confidence=confidence,
            validation_count=validation_count,
            status=status,
            tags=tags,
            created_at=row["created_at"],
            last_validated=last_validated,
            promotion_score=round(promotion_score, 1),
            promotion_ready=promotion_ready,
            suggested_type=suggested_type
        ))

    # Sort by promotion score descending
    candidates.sort(key=lambda x: x.promotion_score, reverse=True)
    candidates = candidates[:limit]

    ready_count = sum(1 for c in candidates if c.promotion_ready)

    return {
        "candidates": [c.model_dump() for c in candidates],
        "total": len(candidates),
        "ready_count": ready_count,
        "stats": {
            "avg_confidence": round(sum(c.confidence for c in candidates) / len(candidates), 2) if candidates else 0,
            "avg_validations": round(sum(c.validation_count for c in candidates) / len(candidates), 1) if candidates else 0,
            "by_type": {
                "law": sum(1 for c in candidates if c.suggested_type == "law"),
                "pattern": sum(1 for c in candidates if c.suggested_type == "pattern"),
                "skill": sum(1 for c in candidates if c.suggested_type == "skill"),
            }
        }
    }


@router.post("/promotions/promote")
async def promote_decision(request: PromoteRequest) -> Dict[str, Any]:
    """
    Promote a decision to a law or pattern in a project constitution.
    """
    import yaml
    import random
    import string

    CONSTITUTIONS_DIR = Path.home() / ".agent" / "constitutions"

    # Load the decision
    decision_file = DECISIONS_DIR / f"{request.decision_id}.json"
    if not decision_file.exists():
        raise HTTPException(status_code=404, detail=f"Decision not found: {request.decision_id}")

    with open(decision_file, "r", encoding="utf-8") as f:
        decision_data = json.load(f)

    data = decision_data.get("data", decision_data)
    decision_text = data.get("decision", "")
    rationale = data.get("rationale", "Promoted from validated decision")
    tags = decision_data.get("tags", [])

    # Load constitution
    const_path = CONSTITUTIONS_DIR / f"{request.project_id}.yaml"
    if not const_path.exists():
        raise HTTPException(status_code=404, detail=f"Constitution not found: {request.project_id}")

    with open(const_path, "r", encoding="utf-8") as f:
        const = yaml.safe_load(f) or {}

    # Generate ID if not provided
    if not request.law_id:
        suffix = ''.join(random.choices(string.ascii_lowercase, k=4))
        if request.target_type == "law":
            request.law_id = f"law.promoted.{suffix}"
        else:
            request.law_id = f"pattern.promoted.{suffix}"

    now = datetime.now(timezone.utc)

    if request.target_type == "law":
        new_law = {
            "id": request.law_id,
            "rule": decision_text,
            "strength": request.strength,
            "applies_to": tags[:3] if tags else ["general"],
            "rationale": rationale,
            "provenance": [request.decision_id],
            "last_verified": now.strftime("%Y-%m-%d")
        }

        if "laws" not in const:
            const["laws"] = []
        const["laws"].append(new_law)

        result = {"type": "law", "created": new_law}

    elif request.target_type == "pattern":
        new_pattern = {
            "id": request.law_id,
            "pattern": decision_text,
            "when": "Based on validated experience",
            "value": rationale,
            "provenance": [request.decision_id]
        }

        if "patterns_top" not in const:
            const["patterns_top"] = []
        const["patterns_top"].append(new_pattern)

        result = {"type": "pattern", "created": new_pattern}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown target type: {request.target_type}")

    # Update constitution version
    version_parts = const.get("version", "0.1.0").split(".")
    version_parts[-1] = str(int(version_parts[-1]) + 1)
    const["version"] = ".".join(version_parts)
    const["updated_at"] = now.isoformat() + "Z"

    # Save constitution
    with open(const_path, "w", encoding="utf-8") as f:
        yaml.dump(const, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Mark decision as promoted
    data["promoted_to"] = {
        "type": request.target_type,
        "id": request.law_id,
        "project": request.project_id,
        "promoted_at": now.isoformat() + "Z"
    }
    decision_data["data"] = data
    decision_data["updated_at"] = now.isoformat() + "Z"

    with open(decision_file, "w", encoding="utf-8") as f:
        json.dump(decision_data, f, indent=2)

    return {
        "success": True,
        "message": f"Promoted to {request.target_type} in {request.project_id}",
        **result
    }


@router.get("/promotions/stats")
async def get_promotion_stats() -> Dict[str, Any]:
    """Get summary statistics for promotion pipeline."""
    conn = get_db_connection()

    # Count decisions by status
    total_decisions = conn.execute("SELECT COUNT(*) FROM artifacts WHERE type = 'decision'").fetchone()[0]

    # Count validations
    total_validations = conn.execute("SELECT COUNT(*) FROM artifacts WHERE type = 'decision_validation'").fetchone()[0]

    # Get candidates (simplified query)
    candidates_result = await get_promotion_candidates(min_confidence=0.7, min_validations=1, limit=100)

    return {
        "total_decisions": total_decisions,
        "total_validations": total_validations,
        "promotion_candidates": candidates_result["total"],
        "ready_for_promotion": candidates_result["ready_count"],
        "by_suggested_type": candidates_result["stats"]["by_type"],
        "avg_confidence": candidates_result["stats"]["avg_confidence"],
        "avg_validations": candidates_result["stats"]["avg_validations"],
    }
