"""Quick action endpoints for creating artifacts from the dashboard."""

import sys
import sqlite3
import json
import uuid
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

DURO_DB_PATH = Path.home() / ".agent" / "memory" / "index.db"


class LearningRequest(BaseModel):
    learning: str
    category: str = "General"


class FactRequest(BaseModel):
    claim: str
    confidence: float = 0.5


class EpisodeRequest(BaseModel):
    goal: str
    plan: Optional[list[str]] = None


class ActionResponse(BaseModel):
    success: bool
    artifact_id: str
    message: str


def insert_artifact(artifact: dict) -> str:
    """Insert an artifact into the database."""
    conn = sqlite3.connect(str(DURO_DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO artifacts (id, type, created_at, title, sensitivity, tags, data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        artifact["id"],
        artifact["type"],
        artifact["created_at"],
        artifact["title"],
        artifact.get("sensitivity", "internal"),
        json.dumps(artifact.get("tags", [])),
        json.dumps(artifact)
    ))

    conn.commit()
    conn.close()
    return artifact["id"]


@router.post("/learning", response_model=ActionResponse)
async def save_learning(request: LearningRequest):
    """Save a learning/insight to memory."""
    try:
        # Try to use Duro MCP tools directly
        try:
            from src.tools.memory_tools import save_learning
            result = await save_learning(
                learning=request.learning,
                category=request.category
            )
            return ActionResponse(
                success=True,
                artifact_id=result.get("id", "unknown"),
                message="Learning saved via Duro MCP"
            )
        except ImportError:
            # Fallback: Insert directly into database
            artifact_id = f"learning_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            artifact = {
                "id": artifact_id,
                "type": "log",
                "created_at": now,
                "title": f"Learning: {request.learning[:50]}...",
                "sensitivity": "internal",
                "workflow": "dashboard",
                "tags": ["learning", request.category.lower().replace(" ", "-")],
                "content": request.learning,
                "category": request.category,
                "source": "dashboard-quick-action",
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
        # Try to use Duro MCP tools directly
        try:
            from src.tools.fact_tools import store_fact
            result = await store_fact(
                claim=request.claim,
                confidence=request.confidence
            )
            return ActionResponse(
                success=True,
                artifact_id=result.get("id", "unknown"),
                message="Fact stored via Duro MCP"
            )
        except ImportError:
            # Fallback: Insert directly into database
            artifact_id = f"fact_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            artifact = {
                "id": artifact_id,
                "type": "fact",
                "created_at": now,
                "title": request.claim[:100],
                "sensitivity": "internal",
                "workflow": "dashboard",
                "tags": ["dashboard-fact"],
                "claim": request.claim,
                "confidence": request.confidence,
                "provenance": "user",
                "evidence_type": "none",
                "source": "dashboard-quick-action",
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
        # Try to use Duro MCP tools directly
        try:
            from src.tools.episode_tools import create_episode
            result = await create_episode(
                goal=request.goal,
                plan=request.plan
            )
            return ActionResponse(
                success=True,
                artifact_id=result.get("id", "unknown"),
                message="Episode started via Duro MCP"
            )
        except ImportError:
            # Fallback: Insert directly into database
            artifact_id = f"episode_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            artifact = {
                "id": artifact_id,
                "type": "episode",
                "created_at": now,
                "title": f"Episode: {request.goal[:50]}",
                "sensitivity": "internal",
                "workflow": "dashboard",
                "tags": ["active-episode"],
                "goal": request.goal,
                "plan": request.plan or [],
                "status": "open",
                "started_at": now,
                "actions": [],
                "source": "dashboard-quick-action",
            }

            insert_artifact(artifact)

            return ActionResponse(
                success=True,
                artifact_id=artifact_id,
                message="Episode started"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
