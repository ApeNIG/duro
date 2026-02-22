"""Auto-link Suggestions endpoint - surfaces potential connections between artifacts."""

import json
from pathlib import Path
from typing import Any
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import APIRouter, Query

from .stats import get_db_connection

router = APIRouter()

MEMORY_DIR = Path.home() / ".agent" / "memory"


def load_artifact_file(file_path: str) -> dict | None:
    """Load artifact JSON file safely."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text."""
    if not text:
        return set()

    # Simple keyword extraction - split and filter
    words = text.lower().replace("-", " ").replace("_", " ").split()
    # Filter out common words and short words
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
        "be", "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "this", "that", "these",
        "those", "it", "its", "i", "we", "you", "they", "he", "she", "what", "which",
        "who", "when", "where", "why", "how", "not", "no", "yes", "if", "then",
        "than", "so", "just", "only", "also", "more", "most", "some", "any", "all",
        "each", "every", "both", "few", "many", "much", "such", "very", "too",
        "use", "using", "used", "make", "made", "get", "got", "set", "add", "new"
    }
    return {w for w in words if len(w) > 3 and w not in stopwords}


def calculate_similarity(tags1: list, tags2: list, keywords1: set, keywords2: set) -> float:
    """Calculate similarity score between two artifacts."""
    score = 0.0

    # Tag overlap (weighted higher)
    if tags1 and tags2:
        tag_set1 = set(t.lower() for t in tags1)
        tag_set2 = set(t.lower() for t in tags2)
        common_tags = tag_set1 & tag_set2
        if common_tags:
            score += len(common_tags) * 0.3

    # Keyword overlap
    common_keywords = keywords1 & keywords2
    if common_keywords:
        score += len(common_keywords) * 0.1

    return min(score, 1.0)  # Cap at 1.0


def parse_iso_date(date_str: str) -> datetime | None:
    """Parse ISO date string."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


@router.get("/suggestions/links")
async def get_link_suggestions(
    min_score: float = Query(0.2, ge=0.0, le=1.0),
    limit: int = Query(30, ge=1, le=100),
) -> dict[str, Any]:
    """
    Get suggested links between artifacts that aren't currently connected.

    Uses tag overlap, keyword matching, and temporal proximity to suggest
    potential relationships.

    Suggestion types:
    - decision_episode: Decisions that should be linked to episodes
    - episode_decision: Episodes that might have used a decision
    - fact_decision: Facts that support a decision
    - incident_change: Incidents that might be related to changes
    """
    conn = get_db_connection()

    # Load all decisions
    decisions_query = """
        SELECT id, type, title, created_at, file_path
        FROM artifacts
        WHERE type = 'decision' AND file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 200
    """
    decisions = conn.execute(decisions_query).fetchall()

    # Load all episodes
    episodes_query = """
        SELECT id, type, title, created_at, file_path
        FROM artifacts
        WHERE type = 'episode' AND file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 200
    """
    episodes = conn.execute(episodes_query).fetchall()

    # Load all facts
    facts_query = """
        SELECT id, type, title, created_at, file_path
        FROM artifacts
        WHERE type = 'fact' AND file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 200
    """
    facts = conn.execute(facts_query).fetchall()

    # Build artifact data with tags and keywords
    decision_data = {}
    for row in decisions:
        content = load_artifact_file(row["file_path"])
        if content:
            data = content.get("data", {})
            decision_data[row["id"]] = {
                "id": row["id"],
                "title": row["title"] or data.get("decision", "")[:50],
                "tags": data.get("tags", []),
                "keywords": extract_keywords((data.get("decision") or "") + " " + (data.get("rationale") or "")),
                "linked_episodes": set(data.get("linked_episodes", [])),
                "created_at": row["created_at"],
            }

    episode_data = {}
    for row in episodes:
        content = load_artifact_file(row["file_path"])
        if content:
            data = content.get("data", {})
            links = data.get("links", {})
            episode_data[row["id"]] = {
                "id": row["id"],
                "title": row["title"] or data.get("goal", "")[:50],
                "tags": data.get("tags", []),
                "keywords": extract_keywords((data.get("goal") or "") + " " + (data.get("result_summary") or "")),
                "decisions_used": set(links.get("decisions_used", [])),
                "created_at": row["created_at"],
            }

    fact_data = {}
    for row in facts:
        content = load_artifact_file(row["file_path"])
        if content:
            data = content.get("data", {})
            fact_data[row["id"]] = {
                "id": row["id"],
                "title": row["title"] or data.get("claim", "")[:50],
                "tags": data.get("tags", []),
                "keywords": extract_keywords(data.get("claim", "")),
                "created_at": row["created_at"],
            }

    suggestions = []

    # Find decision-episode suggestions
    for dec_id, dec in decision_data.items():
        for ep_id, ep in episode_data.items():
            # Skip if already linked
            if ep_id in dec["linked_episodes"] or dec_id in ep["decisions_used"]:
                continue

            # Calculate similarity
            score = calculate_similarity(dec["tags"], ep["tags"], dec["keywords"], ep["keywords"])

            # Temporal boost: episodes shortly after decisions might be testing them
            dec_date = parse_iso_date(dec["created_at"])
            ep_date = parse_iso_date(ep["created_at"])
            if dec_date and ep_date:
                days_diff = abs((ep_date - dec_date).days)
                if days_diff <= 7:
                    score += 0.15
                elif days_diff <= 14:
                    score += 0.05

            if score >= min_score:
                # Determine reason
                common_tags = set(t.lower() for t in dec["tags"]) & set(t.lower() for t in ep["tags"])
                common_keywords = dec["keywords"] & ep["keywords"]

                reason_parts = []
                if common_tags:
                    reason_parts.append(f"shared tags: {', '.join(list(common_tags)[:3])}")
                if common_keywords:
                    reason_parts.append(f"shared concepts: {', '.join(list(common_keywords)[:3])}")
                if dec_date and ep_date and abs((ep_date - dec_date).days) <= 7:
                    reason_parts.append("close in time")

                suggestions.append({
                    "type": "decision_episode",
                    "source": {
                        "id": dec_id,
                        "type": "decision",
                        "title": dec["title"],
                    },
                    "target": {
                        "id": ep_id,
                        "type": "episode",
                        "title": ep["title"],
                    },
                    "score": round(score, 2),
                    "reason": "; ".join(reason_parts) if reason_parts else "potential relationship",
                    "suggested_link": "tested_in",
                })

    # Find fact-decision suggestions
    for fact_id, fact in fact_data.items():
        for dec_id, dec in decision_data.items():
            # Calculate similarity
            score = calculate_similarity(fact["tags"], dec["tags"], fact["keywords"], dec["keywords"])

            if score >= min_score:
                common_tags = set(t.lower() for t in fact["tags"]) & set(t.lower() for t in dec["tags"])
                common_keywords = fact["keywords"] & dec["keywords"]

                reason_parts = []
                if common_tags:
                    reason_parts.append(f"shared tags: {', '.join(list(common_tags)[:3])}")
                if common_keywords:
                    reason_parts.append(f"shared concepts: {', '.join(list(common_keywords)[:3])}")

                suggestions.append({
                    "type": "fact_decision",
                    "source": {
                        "id": fact_id,
                        "type": "fact",
                        "title": fact["title"],
                    },
                    "target": {
                        "id": dec_id,
                        "type": "decision",
                        "title": dec["title"],
                    },
                    "score": round(score, 2),
                    "reason": "; ".join(reason_parts) if reason_parts else "potential relationship",
                    "suggested_link": "supports",
                })

    # Sort by score descending and limit
    suggestions.sort(key=lambda x: x["score"], reverse=True)
    suggestions = suggestions[:limit]

    # Stats
    type_counts = defaultdict(int)
    for s in suggestions:
        type_counts[s["type"]] += 1

    return {
        "suggestions": suggestions,
        "total": len(suggestions),
        "by_type": dict(type_counts),
        "stats": {
            "decisions_analyzed": len(decision_data),
            "episodes_analyzed": len(episode_data),
            "facts_analyzed": len(fact_data),
        }
    }


@router.post("/suggestions/apply")
async def apply_suggestion(
    source_id: str,
    target_id: str,
    link_type: str,
) -> dict[str, Any]:
    """
    Apply a suggested link by updating the source artifact.

    For decisions: adds episode to linked_episodes
    For episodes: adds decision to decisions_used
    """
    conn = get_db_connection()

    # Get source artifact
    cursor = conn.execute(
        "SELECT id, type, file_path FROM artifacts WHERE id = ?",
        (source_id,)
    )
    source = cursor.fetchone()
    if not source or not source["file_path"]:
        return {"success": False, "error": "Source artifact not found"}

    # Load and update the artifact
    content = load_artifact_file(source["file_path"])
    if not content:
        return {"success": False, "error": "Could not load source artifact"}

    data = content.get("data", {})
    updated = False

    if source["type"] == "decision" and link_type == "tested_in":
        # Add to linked_episodes
        linked_episodes = data.get("linked_episodes", [])
        if target_id not in linked_episodes:
            linked_episodes.append(target_id)
            data["linked_episodes"] = linked_episodes
            updated = True

    elif source["type"] == "episode" and link_type == "used_decision":
        # Add to links.decisions_used
        links = data.get("links", {})
        decisions_used = links.get("decisions_used", [])
        if target_id not in decisions_used:
            decisions_used.append(target_id)
            links["decisions_used"] = decisions_used
            data["links"] = links
            updated = True

    if not updated:
        return {"success": False, "error": "Link type not applicable or already exists"}

    # Save the artifact
    content["data"] = data
    try:
        with open(source["file_path"], "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
        return {
            "success": True,
            "source_id": source_id,
            "target_id": target_id,
            "link_type": link_type,
        }
    except OSError as e:
        return {"success": False, "error": str(e)}


@router.post("/suggestions/dismiss")
async def dismiss_suggestion(
    source_id: str,
    target_id: str,
) -> dict[str, Any]:
    """
    Dismiss a suggestion (mark as not relevant).

    This stores the dismissal so it won't be suggested again.
    """
    # For now, just return success - we could store dismissals in SQLite
    # in a future iteration
    return {
        "success": True,
        "dismissed": {
            "source_id": source_id,
            "target_id": target_id,
        },
        "note": "Dismissals are not persisted in this version"
    }
