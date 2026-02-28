"""Emergence API - Orphan detection, drift reports, and idea generation."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .stats import get_db_connection

router = APIRouter()

MEMORY_DIR = Path.home() / ".agent" / "memory"
FACTS_DIR = MEMORY_DIR / "facts"
DECISIONS_DIR = MEMORY_DIR / "decisions"
RULES_DIR = MEMORY_DIR / "rules"


def load_artifact_file(file_path: str) -> dict | None:
    """Load artifact JSON file safely."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


@router.get("/emergence/orphans")
async def get_orphan_artifacts(
    min_connections: int = Query(1, ge=0, le=5),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """
    Get under-connected artifacts (orphans).

    Orphans are artifacts with fewer than min_connections relationships,
    indicating they may be isolated knowledge that needs linking or removal.
    """
    conn = get_db_connection()

    # Query artifacts with low connection counts
    # We'll check file contents for references
    cursor = conn.execute("""
        SELECT id, type, title, created_at, file_path, tags
        FROM artifacts
        WHERE file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 500
    """)

    orphans = []
    for row in cursor.fetchall():
        content = load_artifact_file(row["file_path"])
        if not content:
            continue

        data = content.get("data", {})

        # Count connections based on metadata
        connection_count = 0

        # Check for links to other artifacts
        if data.get("linked_decisions"):
            connection_count += len(data.get("linked_decisions", []))
        if data.get("linked_episodes"):
            connection_count += len(data.get("linked_episodes", []))
        if data.get("related_artifacts"):
            connection_count += len(data.get("related_artifacts", []))
        if data.get("source_urls"):
            connection_count += len(data.get("source_urls", []))
        if data.get("superseded_by") or data.get("supersedes"):
            connection_count += 1

        # If artifact has low connections, it's an orphan
        if connection_count < min_connections:
            orphans.append({
                "id": row["id"],
                "title": row["title"] or data.get("claim", data.get("decision", ""))[:50],
                "type": row["type"],
                "connection_count": connection_count,
                "created_at": row["created_at"],
                "tags": row["tags"].split(",") if row["tags"] else [],
            })

    # Sort by connection count (lowest first)
    orphans.sort(key=lambda x: x["connection_count"])
    orphans = orphans[:limit]

    return {
        "artifacts": orphans,
        "total": len(orphans),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/emergence/drift")
async def get_drift_report(
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """
    Get drift report - discrepancies between stated rules and observed behavior.

    Compares rules/decisions to recent activity to find gaps.
    """
    conn = get_db_connection()

    drift_items = []

    # Load rules
    if RULES_DIR.exists():
        for rule_file in RULES_DIR.glob("*.json"):
            try:
                with open(rule_file, "r", encoding="utf-8") as f:
                    rule_data = json.load(f)
                    rule = rule_data.get("data", {})

                    # Check if rule has been triggered recently
                    trigger_count = rule.get("trigger_count", 0)
                    last_triggered = rule.get("last_triggered")

                    # Rules that exist but never trigger might indicate drift
                    if trigger_count == 0 and rule.get("condition"):
                        drift_items.append({
                            "stated": rule.get("name", "Unknown rule"),
                            "observed": "Never triggered - may be unreachable or obsolete",
                            "severity": "low",
                            "type": "unused_rule",
                            "id": rule_data.get("id"),
                        })
            except (json.JSONDecodeError, OSError):
                continue

    # Check for decisions that were reversed (indicates drift from original decision)
    cursor = conn.execute("""
        SELECT id, title, file_path
        FROM artifacts
        WHERE type = 'decision' AND file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 100
    """)

    for row in cursor.fetchall():
        content = load_artifact_file(row["file_path"])
        if not content:
            continue

        data = content.get("data", {})
        outcome_status = data.get("outcome_status")

        if outcome_status == "reversed":
            drift_items.append({
                "stated": data.get("decision", row["title"])[:80],
                "observed": "Decision was reversed - outcome differed from expectation",
                "severity": "medium",
                "type": "reversed_decision",
                "id": row["id"],
            })
        elif outcome_status == "partial":
            drift_items.append({
                "stated": data.get("decision", row["title"])[:80],
                "observed": "Partial success - results didn't fully match expectations",
                "severity": "low",
                "type": "partial_outcome",
                "id": row["id"],
            })

    # Check for superseded facts (knowledge that was corrected)
    cursor = conn.execute("""
        SELECT id, title, file_path
        FROM artifacts
        WHERE type = 'fact' AND file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 200
    """)

    for row in cursor.fetchall():
        content = load_artifact_file(row["file_path"])
        if not content:
            continue

        data = content.get("data", {})

        if data.get("superseded_by"):
            drift_items.append({
                "stated": data.get("claim", row["title"])[:80],
                "observed": f"Superseded by newer knowledge",
                "severity": "low",
                "type": "superseded_fact",
                "id": row["id"],
            })
        elif data.get("verification_state") == "disputed":
            drift_items.append({
                "stated": data.get("claim", row["title"])[:80],
                "observed": "Disputed - conflicting evidence found",
                "severity": "high",
                "type": "disputed_fact",
                "id": row["id"],
            })

    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    drift_items.sort(key=lambda x: severity_order.get(x["severity"], 3))
    drift_items = drift_items[:limit]

    return {
        "items": drift_items,
        "total": len(drift_items),
        "by_severity": {
            "high": len([i for i in drift_items if i["severity"] == "high"]),
            "medium": len([i for i in drift_items if i["severity"] == "medium"]),
            "low": len([i for i in drift_items if i["severity"] == "low"]),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/emergence/ideas")
async def get_generated_ideas(
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """
    Get AI-generated ideas from cross-domain pattern analysis.

    Ideas are derived from:
    - Cross-referencing different project domains
    - Episode failure analysis
    - Skill composition opportunities
    """
    conn = get_db_connection()

    ideas = []

    # Generate ideas from episode patterns
    cursor = conn.execute("""
        SELECT id, title, file_path
        FROM artifacts
        WHERE type = 'episode' AND file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 50
    """)

    # Track domain combinations seen
    domain_combinations = {}
    failed_episodes = []

    for row in cursor.fetchall():
        content = load_artifact_file(row["file_path"])
        if not content:
            continue

        data = content.get("data", {})
        tags = data.get("tags", [])
        result = data.get("result")

        # Track domains
        domain = data.get("context", {}).get("domain", "general")

        # Track failed episodes for pattern analysis
        if result == "failed":
            failed_episodes.append({
                "goal": data.get("goal", ""),
                "domain": domain,
                "tags": tags,
            })

    # Generate ideas from failed episode patterns
    if len(failed_episodes) >= 2:
        # Find common failure patterns
        common_tags = {}
        for ep in failed_episodes:
            for tag in ep.get("tags", []):
                common_tags[tag] = common_tags.get(tag, 0) + 1

        recurring_failures = [t for t, count in common_tags.items() if count >= 2]
        if recurring_failures:
            ideas.append({
                "id": f"idea_failures_{hash(tuple(recurring_failures)) % 10000}",
                "title": f"Address recurring failures in: {', '.join(recurring_failures[:3])}",
                "description": f"Multiple episodes failed with similar tags. Consider creating safeguards or improving processes for these areas.",
                "source": "episode_analysis",
                "potential": min(0.9, 0.5 + len(recurring_failures) * 0.1),
                "evidence_count": len(failed_episodes),
            })

    # Look for skill composition opportunities
    cursor = conn.execute("""
        SELECT id, title, file_path
        FROM artifacts
        WHERE type = 'skill_stats' AND file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 30
    """)

    high_success_skills = []
    for row in cursor.fetchall():
        content = load_artifact_file(row["file_path"])
        if not content:
            continue

        data = content.get("data", {})
        success_rate = data.get("success_rate", 0)

        if success_rate >= 0.8:
            high_success_skills.append(data.get("skill_name", row["id"]))

    if len(high_success_skills) >= 2:
        ideas.append({
            "id": f"idea_compose_{hash(tuple(high_success_skills)) % 10000}",
            "title": f"Compose high-success skills into workflow",
            "description": f"Skills with high success rates ({', '.join(high_success_skills[:4])}) could be combined into a compound workflow for greater effectiveness.",
            "source": "skill_analysis",
            "potential": 0.75,
            "evidence_count": len(high_success_skills),
        })

    # Cross-domain connection ideas from facts
    cursor = conn.execute("""
        SELECT id, title, tags, file_path
        FROM artifacts
        WHERE type = 'fact' AND file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 100
    """)

    domain_facts = {}
    for row in cursor.fetchall():
        content = load_artifact_file(row["file_path"])
        if not content:
            continue

        data = content.get("data", {})
        tags = data.get("tags", [])

        for tag in tags:
            if tag not in domain_facts:
                domain_facts[tag] = []
            domain_facts[tag].append({
                "id": row["id"],
                "claim": data.get("claim", "")[:50],
            })

    # Find overlapping domains
    sorted_domains = sorted(domain_facts.items(), key=lambda x: len(x[1]), reverse=True)
    if len(sorted_domains) >= 2:
        top_domains = sorted_domains[:5]
        for i, (domain1, facts1) in enumerate(top_domains):
            for domain2, facts2 in top_domains[i+1:]:
                if len(facts1) >= 3 and len(facts2) >= 3:
                    ideas.append({
                        "id": f"idea_cross_{hash(domain1 + domain2) % 10000}",
                        "title": f"Connect {domain1} with {domain2}",
                        "description": f"Both domains have significant knowledge ({len(facts1)} and {len(facts2)} facts). Look for patterns that apply across both.",
                        "source": "cross_domain",
                        "potential": 0.6,
                        "evidence_count": len(facts1) + len(facts2),
                    })

    # Sort by potential
    ideas.sort(key=lambda x: -x["potential"])
    ideas = ideas[:limit]

    return {
        "items": ideas,
        "total": len(ideas),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/emergence/connections")
async def get_cross_connections(
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """
    Get discovered cross-domain connections.

    Surfaces patterns that span multiple project domains.
    """
    conn = get_db_connection()

    connections = []

    # Analyze tag co-occurrence across artifacts
    cursor = conn.execute("""
        SELECT id, type, tags, file_path
        FROM artifacts
        WHERE tags IS NOT NULL AND tags != ''
        ORDER BY created_at DESC
        LIMIT 500
    """)

    # Build co-occurrence matrix
    co_occurrence = {}
    tag_counts = {}

    for row in cursor.fetchall():
        tags = [t.strip() for t in row["tags"].split(",") if t.strip()]

        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Track pairs
        for i, tag1 in enumerate(tags):
            for tag2 in tags[i+1:]:
                pair = tuple(sorted([tag1, tag2]))
                co_occurrence[pair] = co_occurrence.get(pair, 0) + 1

    # Find strong connections (tags that appear together frequently)
    for (tag1, tag2), count in co_occurrence.items():
        if count >= 3:  # At least 3 co-occurrences
            # Calculate connection strength
            # Jaccard-like similarity
            tag1_count = tag_counts.get(tag1, 1)
            tag2_count = tag_counts.get(tag2, 1)
            strength = count / (tag1_count + tag2_count - count)

            if strength >= 0.2:  # At least 20% overlap
                connections.append({
                    "from_domain": tag1,
                    "to_domain": tag2,
                    "concept": f"Co-occurs in {count} artifacts",
                    "strength": round(strength, 2),
                    "occurrence_count": count,
                })

    # Sort by strength
    connections.sort(key=lambda x: -x["strength"])
    connections = connections[:limit]

    return {
        "items": connections,
        "total": len(connections),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
