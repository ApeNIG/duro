"""
Duro REST API - Pydantic Models

Shared artifact envelope + type-specific payloads.
Events are append-only; current_state is derived.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class ArtifactType(str, Enum):
    fact = "fact"
    decision = "decision"
    episode = "episode"
    evaluation = "evaluation"
    incident = "incident_rca"
    change = "recent_change"
    log = "log"
    checklist = "checklist_template"
    decision_validation = "decision_validation"
    design_ref = "design_reference"
    skill_stats = "skill_stats"


class EventType(str, Enum):
    validated = "validated"
    reversed = "reversed"
    reinforced = "reinforced"
    superseded = "superseded"
    contested = "contested"
    updated = "updated"


class EpisodeResult(str, Enum):
    success = "success"
    partial = "partial"
    failed = "failed"


# =============================================================================
# Provenance (shared across all artifacts)
# =============================================================================

class Provenance(BaseModel):
    """Origin tracking for any artifact."""
    source: str = Field(default="api", description="Where this came from: api, mcp, import, user")
    actor: Optional[str] = Field(default=None, description="Who/what created this")
    external_id: Optional[str] = Field(default=None, description="ID in external system")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")


# =============================================================================
# Type-Specific Payloads
# =============================================================================

class FactPayload(BaseModel):
    """Fact-specific fields."""
    claim: str = Field(..., description="The factual claim")
    evidence_type: str = Field(default="none", description="quote, paraphrase, inference, none")
    source_urls: list[str] = Field(default_factory=list)
    snippet: Optional[str] = Field(default=None, description="Supporting text excerpt")


class DecisionPayload(BaseModel):
    """Decision-specific fields."""
    decision: str = Field(..., description="What was decided")
    rationale: str = Field(..., description="Why this decision was made")
    alternatives: list[str] = Field(default_factory=list)
    context: Optional[str] = Field(default=None)
    reversible: bool = Field(default=True)


class EpisodePayload(BaseModel):
    """Episode-specific fields."""
    goal: str = Field(..., description="What this episode aims to achieve")
    plan: list[str] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list, description="Action refs (tool, summary, run_id)")
    result: Optional[EpisodeResult] = Field(default=None)
    result_summary: Optional[str] = Field(default=None)


# =============================================================================
# Current State (derived from events)
# =============================================================================

class CurrentState(BaseModel):
    """Derived snapshot for fast reads. Updated by event reducer."""
    status: str = Field(default="active", description="active, validated, reversed, superseded")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    last_event_at: Optional[str] = Field(default=None)  # ISO string
    event_count: int = Field(default=0)
    validation_count: int = Field(default=0)


# =============================================================================
# Artifact Envelope (the unified schema)
# =============================================================================

class ArtifactCreate(BaseModel):
    """Create a new artifact. Shared envelope + type-specific payload."""
    type: ArtifactType
    title: str = Field(..., min_length=1, max_length=500, description="Human-readable primary string")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    provenance: Optional[Provenance] = Field(default=None)
    payload: dict = Field(..., description="Type-specific data (fact, decision, episode fields)")


class ArtifactResponse(BaseModel):
    """Full artifact response."""
    id: str
    type: ArtifactType
    title: str
    confidence: float
    tags: list[str]
    provenance: Provenance
    payload: dict
    state: CurrentState
    created_at: Optional[str] = None  # ISO string
    updated_at: Optional[str] = None


class ArtifactSummary(BaseModel):
    """Lightweight artifact for list responses."""
    id: str
    type: ArtifactType
    title: str
    confidence: float
    tags: list[str]
    created_at: Optional[str] = None  # ISO string, flexible parsing
    state_status: str = Field(description="Current status from state")


# =============================================================================
# Events (append-only audit log)
# =============================================================================

class EventCreate(BaseModel):
    """Add an event to an artifact's timeline."""
    event: EventType
    confidence_delta: float = Field(default=0.0, ge=-1.0, le=1.0, description="Change to confidence")
    note: Optional[str] = Field(default=None, max_length=2000)
    evidence: list[str] = Field(default_factory=list, description="URLs or artifact IDs")
    actor: Optional[str] = Field(default=None, description="Who triggered this event")


class EventResponse(BaseModel):
    """Event in the timeline."""
    id: str
    artifact_id: str
    event: EventType
    confidence_delta: float
    note: Optional[str]
    evidence: list[str]
    actor: Optional[str]
    created_at: Optional[str] = None  # ISO string


# =============================================================================
# Search
# =============================================================================

class SearchQuery(BaseModel):
    """Complex search query (POST)."""
    query: str = Field(..., min_length=1, description="Search text")
    types: list[ArtifactType] = Field(default_factory=list, description="Filter by types")
    tags: list[str] = Field(default_factory=list, description="Filter by tags (any match)")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=20, ge=1, le=100)
    include_highlights: bool = Field(default=True)
    semantic_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="Weight for semantic vs keyword")


class SearchHit(BaseModel):
    """Single search result with scoring breakdown."""
    artifact: ArtifactSummary
    semantic_score: float = Field(description="Vector similarity score")
    keyword_score: float = Field(description="FTS match score")
    recency_score: float = Field(default=0.0, description="Time-based boost")
    final_score: float = Field(description="Weighted combination")
    highlights: list[str] = Field(default_factory=list, description="Matched text snippets")


class SearchResponse(BaseModel):
    """Search results with metadata."""
    query: str
    hits: list[SearchHit]
    total: int
    took_ms: float


# =============================================================================
# List/Filter
# =============================================================================

class ArtifactListParams(BaseModel):
    """Query params for listing artifacts."""
    type: Optional[ArtifactType] = None
    tags: list[str] = Field(default_factory=list)
    status: Optional[str] = Field(default=None, description="Filter by state.status")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort: str = Field(default="created_at", description="Sort field")
    order: str = Field(default="desc", description="asc or desc")


class ArtifactListResponse(BaseModel):
    """Paginated artifact list."""
    artifacts: list[ArtifactSummary]
    total: int
    limit: int
    offset: int
    has_more: bool


# =============================================================================
# Health
# =============================================================================

class HealthResponse(BaseModel):
    """Rich health check response."""
    status: str = Field(description="healthy, degraded, unhealthy")
    version: str
    git_commit: Optional[str] = None
    index: dict = Field(description="Index status: loaded, artifact_count, last_updated")
    embeddings: dict = Field(description="Embedding status: available, model, vector_count")
    storage: dict = Field(description="Storage status: path, writable")
    uptime_seconds: float


# =============================================================================
# Errors
# =============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
