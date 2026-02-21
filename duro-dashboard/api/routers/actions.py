"""Quick action endpoints for creating artifacts from the dashboard."""

import sqlite3
import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

DURO_DB_PATH = Path.home() / ".agent" / "memory" / "index.db"
ARTIFACTS_DIR = Path.home() / ".agent" / "memory" / "artifacts"


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class LearningRequest(BaseModel):
    learning: str
    category: str = "General"


class FactRequest(BaseModel):
    claim: str
    confidence: float = 0.5
    source_urls: Optional[list[str]] = None
    tags: Optional[list[str]] = None


class DecisionRequest(BaseModel):
    decision: str
    rationale: str
    alternatives: Optional[list[str]] = None
    context: Optional[str] = None
    tags: Optional[list[str]] = None


class EpisodeRequest(BaseModel):
    goal: str
    plan: Optional[list[str]] = None


class ActionResponse(BaseModel):
    success: bool
    artifact_id: str
    message: str


def insert_artifact(artifact: dict) -> str:
    """Insert an artifact into the database and save to file."""
    # Ensure artifacts directory exists
    type_dir = ARTIFACTS_DIR / artifact["type"]
    type_dir.mkdir(parents=True, exist_ok=True)

    # Save artifact to JSON file
    file_path = type_dir / f"{artifact['id']}.json"
    content_str = json.dumps(artifact, sort_keys=True, default=str)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content_str)

    # Compute content hash
    content_hash = compute_hash(content_str)

    # Insert into database with WAL mode and timeout for concurrent access
    conn = sqlite3.connect(str(DURO_DB_PATH), timeout=10.0)
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO artifacts (id, type, created_at, title, sensitivity, tags, file_path, source_workflow, hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        artifact["id"],
        artifact["type"],
        artifact["created_at"],
        artifact["title"],
        artifact.get("sensitivity", "internal"),
        json.dumps(artifact.get("tags", [])),
        str(file_path),
        artifact.get("source_workflow", "dashboard"),
        content_hash
    ))

    conn.commit()
    conn.close()
    return artifact["id"]


@router.post("/learning", response_model=ActionResponse)
async def save_learning(request: LearningRequest):
    """Save a learning/insight to memory."""
    try:
        artifact_id = f"learning_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()

        artifact = {
            "id": artifact_id,
            "type": "log",
            "created_at": now,
            "title": f"Learning: {request.learning[:50]}",
            "sensitivity": "internal",
            "source_workflow": "dashboard",
            "tags": ["learning", "dashboard", request.category.lower().replace(" ", "-")],
            "content": request.learning,
            "category": request.category,
        }

        insert_artifact(artifact)

        return ActionResponse(
            success=True,
            artifact_id=artifact_id,
            message="Learning saved"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fact", response_model=ActionResponse)
async def store_fact(request: FactRequest):
    """Store a fact with confidence level."""
    try:
        artifact_id = f"fact_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()

        tags = request.tags or []
        if "dashboard" not in tags:
            tags.append("dashboard")

        artifact = {
            "id": artifact_id,
            "type": "fact",
            "created_at": now,
            "title": request.claim[:100],
            "sensitivity": "internal",
            "source_workflow": "dashboard",
            "tags": tags,
            "claim": request.claim,
            "confidence": request.confidence,
            "provenance": "user",
            "evidence_type": "quote" if request.source_urls else "none",
            "source_urls": request.source_urls or [],
        }

        insert_artifact(artifact)

        return ActionResponse(
            success=True,
            artifact_id=artifact_id,
            message="Fact stored"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/episode", response_model=ActionResponse)
async def start_episode(request: EpisodeRequest):
    """Start a new episode for goal tracking."""
    try:
        artifact_id = f"episode_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()

        artifact = {
            "id": artifact_id,
            "type": "episode",
            "created_at": now,
            "title": f"Episode: {request.goal[:50]}",
            "sensitivity": "internal",
            "source_workflow": "dashboard",
            "tags": ["dashboard"],
            "goal": request.goal,
            "plan": request.plan or [],
            "status": "open",
            "started_at": now,
            "actions": [],
        }

        insert_artifact(artifact)

        return ActionResponse(
            success=True,
            artifact_id=artifact_id,
            message="Episode started"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decision", response_model=ActionResponse)
async def store_decision(request: DecisionRequest):
    """Store a decision with rationale."""
    try:
        artifact_id = f"decision_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()

        tags = request.tags or []
        if "dashboard" not in tags:
            tags.append("dashboard")

        artifact = {
            "id": artifact_id,
            "type": "decision",
            "created_at": now,
            "title": request.decision[:100],
            "sensitivity": "internal",
            "source_workflow": "dashboard",
            "tags": tags,
            "decision": request.decision,
            "rationale": request.rationale,
            "alternatives": request.alternatives or [],
            "context": request.context or "",
            "outcome_status": "pending",
            "confidence": 0.5,
            "reversible": True,
        }

        insert_artifact(artifact)

        return ActionResponse(
            success=True,
            artifact_id=artifact_id,
            message="Decision stored"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
