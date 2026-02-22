"""Relationship Graph endpoint - extracts connections between artifacts."""

import json
from pathlib import Path
from typing import Any

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


@router.get("/relationships")
async def get_relationships(
    limit: int = Query(200, ge=1, le=500),
    types: str = Query(None, description="Comma-separated types to include"),
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

    # Filter edges to only include nodes we have (should be all now)
    valid_edges = [
        e for e in all_edges
        if e["source"] in node_ids and e["target"] in node_ids
    ]

    # Get edge type counts
    edge_type_counts = {}
    for e in valid_edges:
        edge_type_counts[e["type"]] = edge_type_counts.get(e["type"], 0) + 1

    return {
        "nodes": nodes,
        "edges": valid_edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(valid_edges),
            "edge_types": edge_type_counts,
        }
    }
