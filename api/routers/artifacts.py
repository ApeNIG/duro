"""
Artifacts router - the core backend.

Handles CRUD for all artifact types + append-only events.
Events are the source of truth; current_state is derived.
"""

import json
import uuid
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

# Add Duro src to path
DURO_SRC = Path.home() / ".agent" / "src"
if str(DURO_SRC) not in sys.path:
    sys.path.insert(0, str(DURO_SRC))

from models import (
    ArtifactCreate, ArtifactResponse, ArtifactSummary, ArtifactListResponse,
    EventCreate, EventResponse, ArtifactType, EventType, Provenance, CurrentState
)

router = APIRouter()


def get_state():
    from main import state
    return state


def generate_artifact_id(artifact_type: str) -> str:
    """Generate a unique artifact ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{artifact_type}_{timestamp}_{suffix}"


def artifact_to_response(artifact: dict, events: list = None) -> ArtifactResponse:
    """Convert stored artifact to response model."""
    # Build current state from events
    state = CurrentState(
        status=artifact.get("outcome", {}).get("status", "active") if isinstance(artifact.get("outcome"), dict) else "active",
        confidence=artifact.get("confidence", artifact.get("outcome", {}).get("confidence", 0.5) if isinstance(artifact.get("outcome"), dict) else 0.5),
        event_count=len(events) if events else 0,
        validation_count=sum(1 for e in (events or []) if e.get("event") in ("validated", "reversed")),
    )

    if events:
        state.last_event_at = events[-1].get("created_at")

    # Build provenance
    provenance = Provenance(
        source=artifact.get("source", {}).get("workflow", "unknown") if isinstance(artifact.get("source"), dict) else "unknown",
        actor=artifact.get("source", {}).get("actor") if isinstance(artifact.get("source"), dict) else None,
        created_at=artifact.get("created_at"),
    )

    # Extract title (different fields depending on type)
    title = artifact.get("title") or artifact.get("data", {}).get("decision") or artifact.get("data", {}).get("claim") or artifact.get("data", {}).get("goal") or artifact.get("id", "")[:50]

    return ArtifactResponse(
        id=artifact["id"],
        type=artifact["type"],
        title=title[:500],
        confidence=state.confidence,
        tags=artifact.get("tags", []),
        provenance=provenance,
        payload=artifact.get("data", artifact.get("payload", {})),
        state=state,
        created_at=artifact.get("created_at"),
        updated_at=artifact.get("updated_at"),
    )


def artifact_to_summary(artifact: dict) -> ArtifactSummary:
    """Convert stored artifact to summary model."""
    title = artifact.get("title") or artifact.get("data", {}).get("decision") or artifact.get("data", {}).get("claim") or artifact.get("data", {}).get("goal") or artifact.get("id", "")[:50]

    # Get status
    status = "active"
    if isinstance(artifact.get("outcome"), dict):
        status = artifact["outcome"].get("status", "active")
    elif artifact.get("state", {}).get("status"):
        status = artifact["state"]["status"]

    return ArtifactSummary(
        id=artifact["id"],
        type=artifact["type"],
        title=title[:500],
        confidence=artifact.get("confidence", 0.5),
        tags=artifact.get("tags", []),
        created_at=artifact.get("created_at"),
        state_status=status,
    )


# =============================================================================
# Create Artifact
# =============================================================================

@router.post("/artifacts", response_model=ArtifactResponse)
async def create_artifact(artifact: ArtifactCreate):
    """
    Create a new artifact.

    The artifact envelope is shared across all types:
    - type: fact, decision, episode, etc.
    - title: human-readable primary string
    - confidence: 0.0 to 1.0
    - tags: list of strings
    - provenance: origin tracking
    - payload: type-specific data
    """
    state = get_state()

    if not state.artifact_store:
        raise HTTPException(status_code=503, detail="Artifact store not initialized")

    # Generate ID
    artifact_id = generate_artifact_id(artifact.type.value)

    # Build artifact in Duro's internal format
    now = datetime.now(timezone.utc).isoformat()

    # Map to internal structure based on type
    internal_artifact = {
        "id": artifact_id,
        "type": artifact.type.value,
        "version": "1.0",
        "created_at": now,
        "updated_at": None,
        "sensitivity": "internal",
        "tags": artifact.tags,
        "title": artifact.title,
        "source": {
            "workflow": artifact.provenance.source if artifact.provenance else "api",
            "actor": artifact.provenance.actor if artifact.provenance else None,
            "run_id": None,
            "tool_trace_path": None,
        },
        "data": artifact.payload,
        "outcome": {
            "status": "active",
            "confidence": artifact.confidence,
            "verified_at": None,
            "evidence": [],
        },
    }

    # Add type-specific fields expected by Duro
    if artifact.type == ArtifactType.fact:
        internal_artifact["data"]["claim"] = artifact.payload.get("claim", artifact.title)
        internal_artifact["data"]["confidence"] = artifact.confidence
        internal_artifact["data"]["provenance"] = artifact.provenance.source if artifact.provenance else "api"

    elif artifact.type == ArtifactType.decision:
        internal_artifact["data"]["decision"] = artifact.payload.get("decision", artifact.title)
        internal_artifact["data"]["rationale"] = artifact.payload.get("rationale", "")
        internal_artifact["data"]["alternatives"] = artifact.payload.get("alternatives", [])
        internal_artifact["data"]["outcome"] = internal_artifact["outcome"]

    elif artifact.type == ArtifactType.episode:
        internal_artifact["data"]["goal"] = artifact.payload.get("goal", artifact.title)
        internal_artifact["data"]["plan"] = artifact.payload.get("plan", [])
        internal_artifact["data"]["actions"] = []
        internal_artifact["data"]["status"] = "open"

    # Store using Duro's artifact store
    try:
        state.artifact_store._store_artifact(internal_artifact)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store artifact: {e}")

    return artifact_to_response(internal_artifact, events=[])


# =============================================================================
# List Artifacts
# =============================================================================

@router.get("/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    type: Optional[ArtifactType] = Query(None, description="Filter by type"),
    tag: Optional[str] = Query(None, description="Filter by tag (any match)"),
    status: Optional[str] = Query(None, description="Filter by state status"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="asc or desc"),
):
    """
    List artifacts with filtering and pagination.
    """
    state = get_state()

    if not state.index:
        raise HTTPException(status_code=503, detail="Index not initialized")

    # Query the index
    try:
        # Build query params for Duro's index
        artifacts = state.index.query(
            limit=limit + offset,  # Get enough to handle offset
            artifact_type=type.value if type else None,
        )

        # Apply additional filters
        filtered = []
        for a in artifacts:
            # Tag filter
            if tag and tag not in a.get("tags", []):
                continue

            # Confidence filter
            conf = a.get("confidence", a.get("outcome", {}).get("confidence", 0.5) if isinstance(a.get("outcome"), dict) else 0.5)
            if conf < min_confidence:
                continue

            # Status filter
            if status:
                a_status = a.get("outcome", {}).get("status", "active") if isinstance(a.get("outcome"), dict) else "active"
                if a_status != status:
                    continue

            filtered.append(a)

        # Apply offset and limit
        total = len(filtered)
        paginated = filtered[offset:offset + limit]

        # Convert to summaries
        summaries = [artifact_to_summary(a) for a in paginated]

        return ArtifactListResponse(
            artifacts=summaries,
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(paginated) < total,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list artifacts: {e}")


# =============================================================================
# Get Single Artifact
# =============================================================================

@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(artifact_id: str):
    """
    Get a single artifact by ID with full details.
    """
    state = get_state()

    if not state.artifact_store:
        raise HTTPException(status_code=503, detail="Artifact store not initialized")

    try:
        artifact = state.artifact_store.get_artifact(artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")

        # Get events for this artifact
        events = get_artifact_events(artifact_id)

        return artifact_to_response(artifact, events)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get artifact: {e}")


# =============================================================================
# Delete Artifact
# =============================================================================

@router.delete("/artifacts/{artifact_id}")
async def delete_artifact(artifact_id: str):
    """
    Delete an artifact by ID.
    """
    state = get_state()

    if not state.artifact_store:
        raise HTTPException(status_code=503, detail="Artifact store not initialized")

    try:
        # Check if artifact exists first
        artifact = state.artifact_store.get_artifact(artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")

        # Delete using Duro's method
        result = state.artifact_store.delete_artifact(
            artifact_id=artifact_id,
            reason="Deleted via REST API",
            force=False,
        )

        return {
            "success": True,
            "deleted_id": artifact_id,
            "type": artifact.get("type"),
            "title": artifact.get("title"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete artifact: {e}")


# =============================================================================
# Events (append-only)
# =============================================================================

EVENTS_DIR = Path.home() / ".agent" / "memory" / "events"


def get_artifact_events(artifact_id: str) -> list[dict]:
    """Get all events for an artifact."""
    events_file = EVENTS_DIR / f"{artifact_id}.jsonl"
    if not events_file.exists():
        return []

    events = []
    with open(events_file, "r") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    return sorted(events, key=lambda e: e.get("created_at", ""))


def append_event(artifact_id: str, event: dict):
    """Append an event to the artifact's event log."""
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    events_file = EVENTS_DIR / f"{artifact_id}.jsonl"

    with open(events_file, "a") as f:
        f.write(json.dumps(event) + "\n")


def reduce_events_to_state(artifact: dict, events: list[dict]) -> dict:
    """
    Reduce events to derive current state.
    Events are source of truth; this updates the artifact's snapshot.
    """
    # Start with base state
    status = "active"
    confidence = artifact.get("confidence", artifact.get("outcome", {}).get("confidence", 0.5) if isinstance(artifact.get("outcome"), dict) else 0.5)

    for event in events:
        event_type = event.get("event")
        delta = event.get("confidence_delta", 0.0)

        # Update confidence
        confidence = max(0.0, min(1.0, confidence + delta))

        # Update status based on event type
        if event_type == "validated":
            status = "validated"
        elif event_type == "reversed":
            status = "reversed"
        elif event_type == "superseded":
            status = "superseded"
        elif event_type == "contested":
            status = "contested"
        elif event_type == "reinforced":
            # Reinforced keeps current status but boosts confidence
            pass

    return {
        "status": status,
        "confidence": confidence,
        "event_count": len(events),
        "last_event_at": events[-1].get("created_at") if events else None,
    }


@router.post("/artifacts/{artifact_id}/events", response_model=EventResponse)
async def add_event(artifact_id: str, event: EventCreate):
    """
    Add an event to an artifact's timeline.

    Events are append-only and form the audit log.
    The artifact's current_state is derived from events.

    Event types:
    - validated: Decision/fact confirmed to be correct
    - reversed: Decision/fact found to be wrong
    - reinforced: Belief strengthened (used in practice)
    - superseded: Replaced by a newer artifact
    - contested: Conflicting evidence found
    """
    state = get_state()

    if not state.artifact_store:
        raise HTTPException(status_code=503, detail="Artifact store not initialized")

    # Verify artifact exists
    artifact = state.artifact_store.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Create event record
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    event_record = {
        "id": event_id,
        "artifact_id": artifact_id,
        "event": event.event.value,
        "confidence_delta": event.confidence_delta,
        "note": event.note,
        "evidence": event.evidence,
        "actor": event.actor,
        "created_at": now,
    }

    # Append to event log (source of truth)
    try:
        append_event(artifact_id, event_record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to append event: {e}")

    # Update artifact's current_state (derived snapshot)
    try:
        all_events = get_artifact_events(artifact_id)
        new_state = reduce_events_to_state(artifact, all_events)

        # Update the artifact's outcome/state in storage
        if isinstance(artifact.get("outcome"), dict):
            artifact["outcome"]["status"] = new_state["status"]
            artifact["outcome"]["confidence"] = new_state["confidence"]
        else:
            artifact["outcome"] = {
                "status": new_state["status"],
                "confidence": new_state["confidence"],
            }

        artifact["updated_at"] = now

        # Re-store the artifact with updated state
        state.artifact_store._store_artifact(artifact)

    except Exception as e:
        # Event was logged, but state update failed - log warning but don't fail
        print(f"Warning: Event logged but state update failed: {e}")

    return EventResponse(
        id=event_id,
        artifact_id=artifact_id,
        event=event.event,
        confidence_delta=event.confidence_delta,
        note=event.note,
        evidence=event.evidence,
        actor=event.actor,
        created_at=now,
    )


@router.get("/artifacts/{artifact_id}/events", response_model=list[EventResponse])
async def list_events(artifact_id: str):
    """
    Get all events for an artifact (the full timeline).
    """
    state = get_state()

    if not state.artifact_store:
        raise HTTPException(status_code=503, detail="Artifact store not initialized")

    # Verify artifact exists
    artifact = state.artifact_store.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    events = get_artifact_events(artifact_id)

    return [
        EventResponse(
            id=e.get("id", ""),
            artifact_id=artifact_id,
            event=e.get("event", "updated"),
            confidence_delta=e.get("confidence_delta", 0.0),
            note=e.get("note"),
            evidence=e.get("evidence", []),
            actor=e.get("actor"),
            created_at=e.get("created_at"),
        )
        for e in events
    ]
