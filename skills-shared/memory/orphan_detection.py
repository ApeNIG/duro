"""
Skill: orphan_detection
Description: Find under-connected, stale, and orphaned artifacts in the knowledge base
Version: 1.0.0
Tier: tested

Maintenance tool that surfaces artifacts needing attention:
- Orphans: artifacts with zero or very few tags (under-connected)
- Stale: artifacts not reinforced or updated in a long time
- Lonely: artifacts whose tags appear nowhere else (isolated concepts)
- Duplicates: artifacts with near-identical titles (potential consolidation)

Designed to run periodically as part of knowledge base hygiene.

Flow:
1. Load all artifacts
2. Score each on connectedness (tag count, tag co-occurrence)
3. Detect staleness (age without reinforcement)
4. Find duplicate titles
5. Report with prioritized cleanup recommendations

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import re
import time
from collections import defaultdict, Counter
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta


SKILL_META = {
    "name": "orphan_detection",
    "description": "Find under-connected, stale, and orphaned artifacts in the knowledge base",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Reflective layer roadmap (Greg Eisenberg x Internet Vin podcast)",
    "validated": "2026-02-24",
    "triggers": ["orphans", "stale", "cleanup", "maintenance", "hygiene", "duplicates"],
    "keywords": [
        "orphan", "stale", "duplicate", "cleanup", "maintenance",
        "hygiene", "under-connected", "lonely", "consolidate", "prune"
    ],
    "phase": "4.0",
}

DEFAULT_CONFIG = {
    "max_artifacts": 500,
    "stale_days": 21,           # Days without update = stale
    "min_tags_for_connected": 2, # Fewer tags than this = under-connected
    "duplicate_threshold": 0.8,  # Jaccard similarity for title duplicate detection
    "max_orphans": 20,
    "max_stale": 20,
    "max_duplicates": 10,
}

REQUIRES = ["query_memory"]

DEFAULT_TIMEOUT = 60


@dataclass
class OrphanArtifact:
    """An artifact flagged as orphaned or under-connected."""
    artifact_id: str
    artifact_type: str
    title: str
    timestamp: str
    tags: List[str]
    issue: str                  # "no_tags", "rare_tags", "stale", "duplicate"
    severity: float = 0.0       # 0-1, higher = more urgent
    detail: str = ""


def extract_text(artifact: Dict) -> str:
    title = artifact.get("title", "")
    if title:
        return str(title)
    if "data" in artifact:
        data = artifact["data"]
        for key in ("message", "claim", "decision", "title"):
            val = data.get(key, "")
            if val:
                return str(val)
    return ""


def extract_tags(artifact: Dict) -> List[str]:
    return artifact.get("tags", []) or []


def extract_timestamp(artifact: Dict) -> str:
    return artifact.get("created_at", "") or artifact.get("timestamp", "") or ""


def extract_updated(artifact: Dict) -> str:
    return artifact.get("updated_at", "") or extract_timestamp(artifact)


def parse_date(timestamp: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f",
                 "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(timestamp[:26], fmt)
        except (ValueError, TypeError):
            continue
    return datetime.min


def jaccard_similarity(a: str, b: str) -> float:
    """Jaccard similarity between two title strings."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union if union > 0 else 0.0


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    max_artifacts = args.get("max_artifacts", DEFAULT_CONFIG["max_artifacts"])
    stale_days = args.get("stale_days", DEFAULT_CONFIG["stale_days"])
    min_tags = args.get("min_tags_for_connected", DEFAULT_CONFIG["min_tags_for_connected"])
    dup_threshold = args.get("duplicate_threshold", DEFAULT_CONFIG["duplicate_threshold"])
    max_orphans = args.get("max_orphans", DEFAULT_CONFIG["max_orphans"])
    max_stale = args.get("max_stale", DEFAULT_CONFIG["max_stale"])
    max_duplicates = args.get("max_duplicates", DEFAULT_CONFIG["max_duplicates"])
    # Which types to scan (skip logs/evaluations — they're high-volume and expected to be transient)
    scan_types = args.get("types", ["fact", "decision", "episode", "incident_rca", "design_reference"])

    query_memory = tools.get("query_memory")
    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    now = datetime.utcnow()
    stale_cutoff = now - timedelta(days=stale_days)

    # ==============================
    # Step 1: Load artifacts
    # ==============================
    all_artifacts = []
    for art_type in scan_types:
        if time.time() - start_time >= timeout * 0.4:
            break
        try:
            result = query_memory(artifact_type=art_type, limit=max_artifacts)
            items = []
            if isinstance(result, list):
                items = result
            elif isinstance(result, dict):
                items = result.get("results", result.get("artifacts", []))
            for item in items:
                if "artifact_type" not in item:
                    item["artifact_type"] = art_type
                all_artifacts.append(item)
        except Exception:
            continue

    if not all_artifacts:
        return {
            "success": True,
            "report": "No artifacts found to scan.",
            "orphans": [],
            "stale": [],
            "duplicates": [],
            "total_scanned": 0,
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    # ==============================
    # Step 2: Build tag frequency map
    # ==============================
    tag_frequency = Counter()
    for art in all_artifacts:
        for tag in extract_tags(art):
            tag_frequency[tag.lower()] += 1

    # ==============================
    # Step 3: Find orphans (no tags or only rare tags)
    # ==============================
    orphans = []
    for art in all_artifacts:
        art_id = art.get("id", "")
        art_type = art.get("artifact_type", art.get("type", ""))
        title = extract_text(art)
        tags = extract_tags(art)
        ts = extract_timestamp(art)

        if not title or len(title) < 10:
            continue

        # No tags at all
        if len(tags) == 0:
            orphans.append(OrphanArtifact(
                artifact_id=art_id,
                artifact_type=art_type,
                title=title[:150],
                timestamp=ts,
                tags=[],
                issue="no_tags",
                severity=0.8,
                detail="No tags — invisible to tag-based queries and reflective skills",
            ))
            continue

        # Under-connected (fewer than min_tags)
        if len(tags) < min_tags:
            orphans.append(OrphanArtifact(
                artifact_id=art_id,
                artifact_type=art_type,
                title=title[:150],
                timestamp=ts,
                tags=tags,
                issue="few_tags",
                severity=0.4,
                detail=f"Only {len(tags)} tag(s) — may be under-connected",
            ))
            continue

        # Tags exist but are all rare (appear only once)
        tag_lowers = [t.lower() for t in tags]
        max_freq = max(tag_frequency.get(t, 0) for t in tag_lowers) if tag_lowers else 0
        if max_freq <= 1:
            orphans.append(OrphanArtifact(
                artifact_id=art_id,
                artifact_type=art_type,
                title=title[:150],
                timestamp=ts,
                tags=tags,
                issue="rare_tags",
                severity=0.5,
                detail=f"All tags are unique to this artifact — isolated concept",
            ))

    orphans.sort(key=lambda o: -o.severity)
    orphans = orphans[:max_orphans]

    # ==============================
    # Step 4: Find stale artifacts
    # ==============================
    stale = []
    for art in all_artifacts:
        if time.time() - start_time >= timeout * 0.7:
            break

        art_id = art.get("id", "")
        art_type = art.get("artifact_type", art.get("type", ""))
        title = extract_text(art)
        updated = extract_updated(art)

        if not title or len(title) < 10:
            continue

        updated_dt = parse_date(updated)
        if updated_dt < stale_cutoff and updated_dt != datetime.min:
            days_old = (now - updated_dt).days
            stale.append(OrphanArtifact(
                artifact_id=art_id,
                artifact_type=art_type,
                title=title[:150],
                timestamp=updated,
                tags=extract_tags(art),
                issue="stale",
                severity=min(1.0, 0.3 + (days_old / 60)),
                detail=f"Last updated {days_old} days ago",
            ))

    stale.sort(key=lambda s: -s.severity)
    stale = stale[:max_stale]

    # ==============================
    # Step 5: Find potential duplicates
    # ==============================
    duplicates = []

    # Only check facts and decisions for duplicates (most valuable to consolidate)
    dup_candidates = [
        a for a in all_artifacts
        if a.get("artifact_type", a.get("type", "")) in ("fact", "decision")
    ]

    # O(n^2) but capped at max_artifacts
    seen_pairs = set()
    for i in range(len(dup_candidates)):
        if time.time() - start_time >= timeout * 0.85:
            break
        if len(duplicates) >= max_duplicates:
            break

        a = dup_candidates[i]
        title_a = extract_text(a)
        if not title_a or len(title_a) < 20:
            continue

        for j in range(i + 1, len(dup_candidates)):
            b = dup_candidates[j]
            pair_key = (a.get("id", ""), b.get("id", ""))
            if pair_key in seen_pairs:
                continue

            title_b = extract_text(b)
            if not title_b or len(title_b) < 20:
                continue

            sim = jaccard_similarity(title_a, title_b)
            if sim >= dup_threshold:
                seen_pairs.add(pair_key)
                duplicates.append({
                    "artifact_a": a.get("id", ""),
                    "artifact_b": b.get("id", ""),
                    "type": a.get("artifact_type", a.get("type", "")),
                    "title_a": title_a[:120],
                    "title_b": title_b[:120],
                    "similarity": round(sim, 2),
                })

    # ==============================
    # Step 6: Report
    # ==============================
    report = format_report(
        orphans, stale, duplicates,
        len(all_artifacts), len(tag_frequency), stale_days,
    )

    orphans_output = [
        {
            "artifact_id": o.artifact_id,
            "artifact_type": o.artifact_type,
            "title": o.title,
            "issue": o.issue,
            "severity": o.severity,
            "detail": o.detail,
            "tags": o.tags,
        }
        for o in orphans
    ]

    stale_output = [
        {
            "artifact_id": s.artifact_id,
            "artifact_type": s.artifact_type,
            "title": s.title,
            "detail": s.detail,
        }
        for s in stale
    ]

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "report": report,
        "orphans": orphans_output,
        "stale": stale_output,
        "duplicates": duplicates,
        "total_scanned": len(all_artifacts),
        "orphan_count": len(orphans),
        "stale_count": len(stale),
        "duplicate_count": len(duplicates),
        "elapsed_seconds": elapsed,
    }


def format_report(
    orphans: List[OrphanArtifact],
    stale: List[OrphanArtifact],
    duplicates: List[Dict],
    total_scanned: int,
    tag_count: int,
    stale_days: int,
) -> str:
    lines = []
    lines.append("## Orphan Detection Report — Knowledge Base Hygiene")
    lines.append("")
    lines.append(f"**Scanned:** {total_scanned} artifacts (facts, decisions, episodes, incidents, design refs)")
    lines.append(f"**Tags:** {tag_count} unique")
    lines.append(f"**Issues found:** {len(orphans)} orphans, {len(stale)} stale, {len(duplicates)} potential duplicates")
    lines.append("")

    if not orphans and not stale and not duplicates:
        lines.append("Knowledge base is clean. No orphans, stale artifacts, or duplicates detected.")
        return "\n".join(lines)

    # --- Orphans ---
    if orphans:
        no_tags = [o for o in orphans if o.issue == "no_tags"]
        few_tags = [o for o in orphans if o.issue == "few_tags"]
        rare_tags = [o for o in orphans if o.issue == "rare_tags"]

        lines.append(f"### Orphaned Artifacts ({len(orphans)})")
        lines.append("")

        if no_tags:
            lines.append(f"**No tags ({len(no_tags)})** — completely invisible to reflective skills:")
            for o in no_tags[:7]:
                lines.append(f"- [{o.artifact_type}] `{o.artifact_id}`: {o.title[:100]}")
            lines.append("")

        if rare_tags:
            lines.append(f"**Isolated concepts ({len(rare_tags)})** — tags appear only on this artifact:")
            for o in rare_tags[:7]:
                lines.append(f"- [{o.artifact_type}] `{o.artifact_id}`: {o.title[:100]}")
                lines.append(f"  Tags: {', '.join(o.tags[:5])}")
            lines.append("")

        if few_tags:
            lines.append(f"**Under-connected ({len(few_tags)})** — fewer than 2 tags:")
            for o in few_tags[:7]:
                lines.append(f"- [{o.artifact_type}] `{o.artifact_id}`: {o.title[:100]}")
            lines.append("")

    # --- Stale ---
    if stale:
        lines.append(f"### Stale Artifacts ({len(stale)})")
        lines.append(f"*Not updated in >{stale_days} days:*")
        lines.append("")
        for s in stale[:10]:
            lines.append(f"- [{s.artifact_type}] `{s.artifact_id}`: {s.title[:100]}")
            lines.append(f"  {s.detail}")
        lines.append("")

    # --- Duplicates ---
    if duplicates:
        lines.append(f"### Potential Duplicates ({len(duplicates)})")
        lines.append("")
        for d in duplicates[:10]:
            lines.append(f"- **{d['similarity']:.0%} similar** [{d['type']}]:")
            lines.append(f"  A: `{d['artifact_a']}` — {d['title_a'][:80]}")
            lines.append(f"  B: `{d['artifact_b']}` — {d['title_b'][:80]}")
        lines.append("")

    return "\n".join(lines)


# --- CLI Mode ---
if __name__ == "__main__":
    print("orphan_detection Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Issue types:")
    print("  - no_tags: zero tags, invisible to reflective skills")
    print("  - few_tags: under-connected (<2 tags)")
    print("  - rare_tags: all tags unique to this artifact")
    print("  - stale: not updated in 21+ days")
    print("  - duplicate: near-identical titles (Jaccard >= 0.8)")
