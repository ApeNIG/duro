"""
Search router - GET simple + POST complex.

Returns scoring breakdown (semantic, keyword, final) and highlights.
This is Duro's core value prop - make it transparent.
"""

import time
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

# Add Duro src to path
DURO_SRC = Path.home() / ".agent" / "src"
if str(DURO_SRC) not in sys.path:
    sys.path.insert(0, str(DURO_SRC))

from models import (
    SearchQuery, SearchResponse, SearchHit, ArtifactSummary, ArtifactType
)

router = APIRouter()


def get_state():
    from main import state
    return state


def artifact_to_summary(artifact: dict) -> ArtifactSummary:
    """Convert stored artifact to summary model."""
    title = (
        artifact.get("title") or
        artifact.get("data", {}).get("decision") or
        artifact.get("data", {}).get("claim") or
        artifact.get("data", {}).get("goal") or
        artifact.get("id", "")[:50]
    )

    # Get status
    status = "active"
    if isinstance(artifact.get("outcome"), dict):
        status = artifact["outcome"].get("status", "active")

    return ArtifactSummary(
        id=artifact["id"],
        type=artifact["type"],
        title=title[:500],
        confidence=artifact.get("confidence", artifact.get("outcome", {}).get("confidence", 0.5) if isinstance(artifact.get("outcome"), dict) else 0.5),
        tags=artifact.get("tags", []),
        created_at=artifact.get("created_at"),
        state_status=status,
    )


def extract_highlights(artifact: dict, query: str) -> list[str]:
    """Extract text snippets that match the query."""
    highlights = []
    query_lower = query.lower()
    query_terms = query_lower.split()

    # Fields to search for highlights
    searchable_fields = [
        artifact.get("title", ""),
        artifact.get("data", {}).get("claim", ""),
        artifact.get("data", {}).get("decision", ""),
        artifact.get("data", {}).get("rationale", ""),
        artifact.get("data", {}).get("goal", ""),
    ]

    for field in searchable_fields:
        if not field:
            continue

        field_lower = field.lower()
        for term in query_terms:
            if term in field_lower:
                # Find the position and extract context
                pos = field_lower.find(term)
                start = max(0, pos - 30)
                end = min(len(field), pos + len(term) + 30)
                snippet = field[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(field):
                    snippet = snippet + "..."
                if snippet not in highlights:
                    highlights.append(snippet)
                break

    return highlights[:3]  # Limit to 3 highlights


def compute_recency_score(created_at: str) -> float:
    """Compute a recency boost (0.0 to 0.2)."""
    try:
        from datetime import datetime, timezone
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_days = (now - created).days

        if age_days < 1:
            return 0.2
        elif age_days < 7:
            return 0.15
        elif age_days < 30:
            return 0.1
        elif age_days < 90:
            return 0.05
        else:
            return 0.0
    except Exception:
        return 0.0


# =============================================================================
# Simple Search (GET)
# =============================================================================

@router.get("/search", response_model=SearchResponse)
async def search_simple(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    type: Optional[ArtifactType] = Query(None, description="Filter by type"),
):
    """
    Simple search endpoint.

    Quick search with default settings. For complex filters, use POST.
    """
    # Delegate to complex search with defaults
    query = SearchQuery(
        query=q,
        types=[type] if type else [],
        limit=limit,
        semantic_weight=0.7,
        include_highlights=True,
    )

    return await search_complex(query)


# =============================================================================
# Complex Search (POST)
# =============================================================================

@router.post("/search", response_model=SearchResponse)
async def search_complex(query: SearchQuery):
    """
    Complex search with full control over filters and ranking.

    Returns scoring breakdown for transparency:
    - semantic_score: Vector similarity (0.0 to 1.0)
    - keyword_score: FTS match score (0.0 to 1.0)
    - recency_score: Time-based boost (0.0 to 0.2)
    - final_score: Weighted combination

    The scoring breakdown builds trust - you can see why results rank.
    """
    state = get_state()
    start_time = time.time()

    if not state.index:
        return SearchResponse(
            query=query.query,
            hits=[],
            total=0,
            took_ms=0,
        )

    hits = []

    try:
        # Try to get embedding for semantic search
        query_embedding = None
        try:
            from embeddings import embed_text
            query_embedding = embed_text(query.query)
        except Exception:
            pass

        # Use hybrid search
        search_result = state.index.hybrid_search(
            query=query.query,
            query_embedding=query_embedding,
            artifact_type=query.types[0].value if query.types else None,
            tags=query.tags if query.tags else None,
            limit=query.limit,
            explain=True,
        )

        results = search_result.get("results", [])
        mode = search_result.get("mode", "keyword_only")

        # Process results
        for result in results:
            artifact = result

            # Get full artifact data if needed
            if state.artifact_store and artifact.get("file_path"):
                try:
                    full_artifact = state.artifact_store.get_artifact(artifact["id"])
                    if full_artifact:
                        artifact = full_artifact
                except Exception:
                    pass

            # Apply confidence filter
            conf = artifact.get("confidence", artifact.get("outcome", {}).get("confidence", 0.5) if isinstance(artifact.get("outcome"), dict) else 0.5)
            if conf < query.min_confidence:
                continue

            # Extract scores
            semantic_score = result.get("vec_score", result.get("semantic_score", 0.0))
            keyword_score = result.get("fts_score", result.get("keyword_score", 0.0))
            recency_score = compute_recency_score(artifact.get("created_at", ""))

            # Normalize scores to 0-1
            if semantic_score > 1:
                semantic_score = 1 / (1 + semantic_score)
            if keyword_score > 1:
                keyword_score = min(1.0, keyword_score / 10)

            # Compute final score
            final_score = result.get("final_score", (
                semantic_score * query.semantic_weight +
                keyword_score * (1 - query.semantic_weight) +
                recency_score
            ))

            # Get highlights
            highlights = []
            if query.include_highlights:
                highlights = extract_highlights(artifact, query.query)

            hits.append(SearchHit(
                artifact=artifact_to_summary(artifact),
                semantic_score=round(semantic_score, 4),
                keyword_score=round(keyword_score, 4),
                recency_score=round(recency_score, 4),
                final_score=round(final_score, 4),
                highlights=highlights,
            ))

    except Exception as e:
        print(f"Search error: {e}")
        # Return empty results on error
        pass

    took_ms = (time.time() - start_time) * 1000

    return SearchResponse(
        query=query.query,
        hits=hits,
        total=len(hits),
        took_ms=round(took_ms, 2),
    )
