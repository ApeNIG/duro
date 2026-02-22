"""Relationship Graph endpoint - extracts connections between artifacts."""

import json
from pathlib import Path
from typing import Any
from collections import defaultdict
from itertools import combinations

from fastapi import APIRouter, Query

from .stats import get_db_connection

router = APIRouter()

MEMORY_DIR = Path.home() / ".agent" / "memory"


def extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text."""
    if not text:
        return set()

    # Clean punctuation and normalize
    import re
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    words = text.split()

    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
        "be", "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "this", "that", "these",
        "those", "it", "its", "i", "we", "you", "they", "he", "she", "what", "which",
        "who", "when", "where", "why", "how", "not", "no", "yes", "if", "then",
        "than", "so", "just", "only", "also", "more", "most", "some", "any", "all",
        "using", "used", "use", "make", "made", "get", "set", "new", "one", "two"
    }
    return {w for w in words if len(w) > 3 and w not in stopwords and w.isalpha()}


def load_artifact_file(file_path: str) -> dict | None:
    """Load artifact JSON file safely."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def extract_relationships(artifact_id: str, content: dict) -> list[dict]:
    """Extract relationships from artifact content."""
    relationships = []
    data = content.get("data", {})
    artifact_type = content.get("type", "")

    # Episode links
    if artifact_type == "episode":
        links = data.get("links", {})

        # Decisions used
        for dec_id in links.get("decisions_used", []):
            relationships.append({
                "source": artifact_id,
                "target": dec_id,
                "type": "used_decision"
            })

        # Skills used
        for skill_id in links.get("skills_used", []):
            relationships.append({
                "source": artifact_id,
                "target": skill_id,
                "type": "used_skill"
            })

        # Facts created
        for fact_id in links.get("facts_created", []):
            relationships.append({
                "source": artifact_id,
                "target": fact_id,
                "type": "created_fact"
            })

        # Decisions created
        for dec_id in links.get("decisions_created", []):
            relationships.append({
                "source": artifact_id,
                "target": dec_id,
                "type": "created_decision"
            })

    # Decision linked episodes
    elif artifact_type == "decision":
        for ep_id in data.get("linked_episodes", []):
            relationships.append({
                "source": artifact_id,
                "target": ep_id,
                "type": "tested_in"
            })

    # Decision validation links
    elif artifact_type == "decision_validation":
        dec_id = data.get("decision_id")
        if dec_id:
            relationships.append({
                "source": artifact_id,
                "target": dec_id,
                "type": "validates"
            })

        ep_id = data.get("episode_id")
        if ep_id:
            relationships.append({
                "source": artifact_id,
                "target": ep_id,
                "type": "evidence_from"
            })

    # Evaluation links
    elif artifact_type == "evaluation":
        ep_id = data.get("episode_id")
        if ep_id:
            relationships.append({
                "source": artifact_id,
                "target": ep_id,
                "type": "evaluates"
            })

    # Incident links
    elif artifact_type == "incident_rca":
        for change_id in data.get("related_recent_changes", []):
            relationships.append({
                "source": artifact_id,
                "target": change_id,
                "type": "caused_by"
            })

    # Fact supersession
    elif artifact_type == "fact":
        superseded_by = data.get("superseded_by")
        if superseded_by:
            relationships.append({
                "source": artifact_id,
                "target": superseded_by,
                "type": "superseded_by"
            })

    return relationships


def calculate_similarity_edges(
    artifacts_data: dict[str, dict],
    min_similarity: float = 0.3,
    max_edges: int = 50,
) -> list[dict]:
    """Calculate similarity edges between artifacts based on tag and keyword overlap."""
    similarity_edges = []
    existing_pairs = set()

    # Only consider fact and decision types for similarity
    similarity_types = {"fact", "decision"}
    candidates = [
        (aid, data) for aid, data in artifacts_data.items()
        if data.get("type") in similarity_types
    ]

    # Calculate pairwise similarity
    for (id1, data1), (id2, data2) in combinations(candidates, 2):
        pair_key = tuple(sorted([id1, id2]))
        if pair_key in existing_pairs:
            continue

        tags1 = set(t.lower() for t in data1.get("tags", []))
        tags2 = set(t.lower() for t in data2.get("tags", []))
        keywords1 = data1.get("keywords", set())
        keywords2 = data2.get("keywords", set())

        # Calculate similarity using Jaccard-like score
        score = 0.0

        # Tag similarity (high weight)
        if tags1 or tags2:
            tag_union = tags1 | tags2
            tag_overlap = tags1 & tags2
            if tag_union:
                score += (len(tag_overlap) / len(tag_union)) * 0.5

        # Keyword similarity - use minimum overlap count for relevance
        if keywords1 and keywords2:
            keyword_overlap = keywords1 & keywords2
            overlap_count = len(keyword_overlap)
            # Score based on absolute overlap (at least 3 shared meaningful words)
            if overlap_count >= 3:
                # Normalize by the smaller set size
                min_size = min(len(keywords1), len(keywords2))
                score += min(overlap_count / min_size, 0.5) * 1.0

        if score >= min_similarity:
            existing_pairs.add(pair_key)
            similarity_edges.append({
                "source": id1,
                "target": id2,
                "type": "similar",
                "similarity": round(score, 2),
            })

    # Sort by similarity and limit
    similarity_edges.sort(key=lambda x: -x["similarity"])
    return similarity_edges[:max_edges]


@router.get("/relationships")
async def get_relationships(
    limit: int = Query(200, ge=1, le=500),
    types: str = Query(None, description="Comma-separated types to include"),
    include_similarity: bool = Query(False, description="Include semantic similarity edges"),
    min_similarity: float = Query(0.3, ge=0.1, le=0.9),
    max_similarity_edges: int = Query(50, ge=10, le=200),
) -> dict[str, Any]:
    """
    Get artifact nodes and their relationships for graph visualization.

    Extracts real connections:
    - Episodes → decisions used, skills used, artifacts created
    - Decisions → linked episodes
    - Validations → decisions, episodes
    - Evaluations → episodes
    - Incidents → recent changes
    - Facts → superseded_by

    With include_similarity=true, also adds:
    - Similar facts and decisions based on tag/keyword overlap
    """
    conn = get_db_connection()

    # Linking types that create edges - always load ALL of these first
    linking_types = ('decision_validation', 'episode', 'evaluation', 'incident_rca')

    # Build type filter for user-specified types
    type_filter = ""
    if types:
        type_list = [t.strip() for t in types.split(",")]
        placeholders = ",".join(["?" for _ in type_list])
        type_filter = f"AND type IN ({placeholders})"

    # First, load ALL linking artifacts (they create edges)
    linking_query = """
        SELECT id, type, title, created_at, file_path
        FROM artifacts
        WHERE file_path IS NOT NULL
        AND type IN (?, ?, ?, ?)
        ORDER BY created_at DESC
    """
    linking_cursor = conn.execute(linking_query, linking_types)
    linking_rows = linking_cursor.fetchall()

    # Then load additional artifacts up to limit
    remaining_limit = max(0, limit - len(linking_rows))
    query = f"""
        SELECT id, type, title, created_at, file_path
        FROM artifacts
        WHERE file_path IS NOT NULL
        AND type NOT IN (?, ?, ?, ?)
        {type_filter}
        ORDER BY created_at DESC
        LIMIT ?
    """

    params = list(linking_types)
    if types:
        params.extend([t.strip() for t in types.split(",")])
    params.append(remaining_limit)

    cursor = conn.execute(query, params)
    other_rows = cursor.fetchall()

    nodes = []
    all_edges = []
    node_ids = set()
    node_map = {}  # id -> node dict for deduplication
    artifacts_data = {}  # id -> data dict for similarity calculation

    # Process all rows (linking artifacts + other artifacts)
    all_rows = list(linking_rows) + list(other_rows)
    for row in all_rows:
        if row["id"] in node_map:
            continue  # Skip duplicates
        node = {
            "id": row["id"],
            "type": row["type"],
            "title": row["title"] or row["id"][:30],
            "created_at": row["created_at"],
        }
        nodes.append(node)
        node_ids.add(row["id"])
        node_map[row["id"]] = node

        # Load file and extract relationships
        if row["file_path"]:
            content = load_artifact_file(row["file_path"])
            if content:
                edges = extract_relationships(row["id"], content)
                all_edges.extend(edges)

                # Store data for similarity calculation
                if include_similarity:
                    data = content.get("data", {})
                    text_content = ""
                    if row["type"] == "fact":
                        text_content = data.get("claim", "")
                    elif row["type"] == "decision":
                        text_content = (data.get("decision") or "") + " " + (data.get("rationale") or "")

                    artifacts_data[row["id"]] = {
                        "type": row["type"],
                        "tags": data.get("tags", []),
                        "keywords": extract_keywords(text_content),
                    }

    # Collect all referenced IDs that we don't have yet
    missing_ids = set()
    for edge in all_edges:
        if edge["source"] not in node_ids:
            missing_ids.add(edge["source"])
        if edge["target"] not in node_ids:
            missing_ids.add(edge["target"])

    # Load missing referenced artifacts
    if missing_ids:
        placeholders = ",".join(["?" for _ in missing_ids])
        missing_query = f"""
            SELECT id, type, title, created_at, file_path
            FROM artifacts
            WHERE id IN ({placeholders})
        """
        cursor = conn.execute(missing_query, list(missing_ids))
        for row in cursor.fetchall():
            if row["id"] not in node_map:
                node = {
                    "id": row["id"],
                    "type": row["type"],
                    "title": row["title"] or row["id"][:30],
                    "created_at": row["created_at"],
                }
                nodes.append(node)
                node_ids.add(row["id"])
                node_map[row["id"]] = node

                # Also add to artifacts_data for similarity calculation
                if include_similarity and row["file_path"]:
                    content = load_artifact_file(row["file_path"])
                    if content:
                        data = content.get("data", {})
                        text_content = ""
                        if row["type"] == "fact":
                            text_content = data.get("claim", "")
                        elif row["type"] == "decision":
                            text_content = (data.get("decision") or "") + " " + (data.get("rationale") or "")

                        if text_content:  # Only add if we have content to compare
                            artifacts_data[row["id"]] = {
                                "type": row["type"],
                                "tags": data.get("tags", []),
                                "keywords": extract_keywords(text_content),
                            }

    # Filter edges to only include nodes we have (should be all now)
    valid_edges = [
        e for e in all_edges
        if e["source"] in node_ids and e["target"] in node_ids
    ]

    # Calculate similarity edges if requested
    similarity_edges = []
    if include_similarity and artifacts_data:
        similarity_edges = calculate_similarity_edges(
            artifacts_data,
            min_similarity=min_similarity,
            max_edges=max_similarity_edges,
        )
        # Filter to only include nodes we have
        similarity_edges = [
            e for e in similarity_edges
            if e["source"] in node_ids and e["target"] in node_ids
        ]
        valid_edges.extend(similarity_edges)

    # Get edge type counts
    edge_type_counts = {}
    for e in valid_edges:
        edge_type_counts[e["type"]] = edge_type_counts.get(e["type"], 0) + 1

    # Count artifacts eligible for similarity
    similarity_candidate_count = sum(1 for aid, adata in artifacts_data.items() if adata.get("type") in {"fact", "decision"})

    return {
        "nodes": nodes,
        "edges": valid_edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(valid_edges),
            "explicit_edges": len(valid_edges) - len(similarity_edges),
            "similarity_edges": len(similarity_edges),
            "similarity_candidates": similarity_candidate_count,
            "edge_types": edge_type_counts,
        }
    }
