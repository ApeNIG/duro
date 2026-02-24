"""
Skill: briefing
Description: Consolidated daily briefing - surfaces key insights via direct artifact analysis
Version: 1.1.0
Tier: tested

The "last mile" for frictionless insight surfacing. Instead of invoking 7 skills
manually, run one briefing that performs lightweight analysis across all artifact types.

Design:
- Uses query_memory and semantic_search (available tools)
- Extracts highlights directly from artifacts
- Lightweight analysis inspired by reflective skills
- Prioritized, scannable output

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple


# Skill metadata
SKILL_META = {
    "name": "briefing",
    "description": "Consolidated daily briefing - surfaces key insights via direct artifact analysis",
    "tier": "tested",
    "version": "1.1.0",
    "author": "duro",
    "origin": "Mac handoff - frictionless insight surfacing",
    "validated": "2026-02-24",
    "triggers": ["briefing", "brief me", "what do I need to know", "morning brief", "daily brief"],
    "keywords": [
        "briefing", "brief", "summary", "insights", "daily", "morning",
        "consolidated", "overview", "what's new", "catchup"
    ],
    "phase": "4.0",
}

# Default configuration
DEFAULT_CONFIG = {
    "days_back": 7,              # Scan last N days
    "max_per_section": 3,        # Max highlights per section
    "max_artifacts": 200,        # Max artifacts to scan
}

# Required capabilities (available in Duro skill executor)
REQUIRES = ["query_memory", "semantic_search"]

# Default timeout
DEFAULT_TIMEOUT = 90


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def extract_text(artifact: Dict) -> str:
    """Extract main text from artifact."""
    data = artifact.get("data", artifact)
    return (
        data.get("claim", "") or
        data.get("decision", "") or
        data.get("message", "") or
        data.get("rationale", "") or
        data.get("title", "") or
        ""
    )


def extract_tags(artifact: Dict) -> List[str]:
    """Extract tags from artifact."""
    return artifact.get("tags", []) or []


def truncate(text: str, length: int = 80) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= length:
        return text
    return text[:length-3] + "..."


# ============================================================
# Section: Decisions Needing Review
# ============================================================
def analyze_decisions(artifacts: List[Dict], max_items: int) -> Tuple[List[str], Dict]:
    """Find decisions that need attention."""
    highlights = []
    stats = {"total": 0, "unverified": 0, "old_unverified": 0}

    now = utc_now()
    cutoff_days = 14

    for art in artifacts:
        if art.get("type") != "decision" and art.get("artifact_type") != "decision":
            continue

        stats["total"] += 1
        data = art.get("data", art)
        outcome = data.get("outcome", {})
        status = outcome.get("status", "unverified")

        if status == "unverified":
            stats["unverified"] += 1

            # Check age
            created_str = art.get("created_at", "")
            if created_str:
                try:
                    created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    age_days = (now - created).days
                    if age_days >= cutoff_days:
                        stats["old_unverified"] += 1
                        decision_text = data.get("decision", "")[:60]
                        if len(highlights) < max_items:
                            highlights.append(f"**{age_days}d old**: {truncate(decision_text)}")
                except (ValueError, TypeError):
                    pass

    return highlights, stats


# ============================================================
# Section: Emerging Patterns (simplified emerge)
# ============================================================
def analyze_patterns(artifacts: List[Dict], max_items: int) -> Tuple[List[str], Dict]:
    """Find recurring themes (simplified emerge)."""
    highlights = []

    # Build tag frequency by type
    tag_by_type = defaultdict(lambda: defaultdict(int))

    for art in artifacts:
        art_type = art.get("type") or art.get("artifact_type", "unknown")
        for tag in extract_tags(art):
            tag_lower = tag.lower().strip()
            if tag_lower and len(tag_lower) > 2:
                tag_by_type[tag_lower][art_type] += 1

    # Find tags heavy in logs but light in facts/decisions
    unarticulated = []
    for tag, type_counts in tag_by_type.items():
        log_count = type_counts.get("log", 0)
        fact_count = type_counts.get("fact", 0)
        decision_count = type_counts.get("decision", 0)
        structured = fact_count + decision_count
        total = log_count + structured

        if log_count >= 3 and total > 0:
            ratio = log_count / total
            if ratio > 0.7:
                unarticulated.append((tag, log_count, ratio))

    unarticulated.sort(key=lambda x: (-x[2], -x[1]))

    for tag, count, ratio in unarticulated[:max_items]:
        highlights.append(f"**{tag}**: {ratio:.0%} unarticulated ({count} in logs)")

    stats = {"unique_tags": len(tag_by_type), "unarticulated": len(unarticulated)}
    return highlights, stats


# ============================================================
# Section: Stale/Orphan Artifacts (simplified orphan_detection)
# ============================================================
def analyze_maintenance(artifacts: List[Dict], max_items: int) -> Tuple[List[str], Dict]:
    """Find maintenance issues."""
    highlights = []
    stats = {"untagged": 0, "stale": 0}

    now = utc_now()
    stale_days = 21
    untagged_items = []
    stale_items = []

    for art in artifacts:
        art_type = art.get("type") or art.get("artifact_type", "unknown")
        art_id = art.get("id", "")
        tags = extract_tags(art)

        # Skip logs and evaluations
        if art_type in ("log", "evaluation", "skill_stats"):
            continue

        # Check untagged
        if not tags:
            stats["untagged"] += 1
            untagged_items.append((art_type, art_id))

        # Check stale
        updated_str = art.get("updated_at") or art.get("created_at", "")
        if updated_str:
            try:
                updated = datetime.fromisoformat(str(updated_str).replace("Z", "+00:00"))
                age_days = (now - updated).days
                if age_days >= stale_days:
                    stats["stale"] += 1
                    if art_type in ("fact", "decision"):
                        stale_items.append((art_type, age_days, art_id))
            except (ValueError, TypeError):
                pass

    if stats["untagged"] > 0:
        highlights.append(f"{stats['untagged']} artifacts have no tags")

    if stats["stale"] > 0:
        highlights.append(f"{stats['stale']} artifacts are stale (21+ days)")

    # Show oldest stale items
    stale_items.sort(key=lambda x: -x[1])
    for art_type, age, art_id in stale_items[:max(0, max_items - len(highlights))]:
        highlights.append(f"Stale {art_type}: {age}d old")

    return highlights, stats


# ============================================================
# Section: Recent Activity Summary
# ============================================================
def analyze_activity(artifacts: List[Dict], max_items: int) -> Tuple[List[str], Dict]:
    """Summarize recent activity."""
    highlights = []

    now = utc_now()
    today = now.date()
    yesterday = today - timedelta(days=1)

    # Count by type and day
    today_counts = Counter()
    yesterday_counts = Counter()

    for art in artifacts:
        art_type = art.get("type") or art.get("artifact_type", "unknown")
        created_str = art.get("created_at", "")

        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                if created.date() == today:
                    today_counts[art_type] += 1
                elif created.date() == yesterday:
                    yesterday_counts[art_type] += 1
            except (ValueError, TypeError):
                pass

    # Format activity
    if today_counts:
        items = [f"{c} {t}s" for t, c in today_counts.most_common(4)]
        highlights.append(f"**Today**: {', '.join(items)}")

    if yesterday_counts:
        items = [f"{c} {t}s" for t, c in yesterday_counts.most_common(4)]
        highlights.append(f"**Yesterday**: {', '.join(items)}")

    stats = {"today": sum(today_counts.values()), "yesterday": sum(yesterday_counts.values())}
    return highlights, stats


# ============================================================
# Section: Key Facts (recent high-confidence)
# ============================================================
def analyze_facts(artifacts: List[Dict], max_items: int) -> Tuple[List[str], Dict]:
    """Surface important recent facts."""
    highlights = []

    now = utc_now()
    recent_facts = []

    for art in artifacts:
        if art.get("type") != "fact" and art.get("artifact_type") != "fact":
            continue

        data = art.get("data", art)
        confidence = data.get("confidence", 0.5)
        claim = data.get("claim", "")

        # Only high-confidence facts
        if confidence >= 0.7 and claim:
            created_str = art.get("created_at", "")
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                age_hours = (now - created).total_seconds() / 3600
                if age_hours <= 48:  # Last 48 hours
                    recent_facts.append((confidence, age_hours, claim))
            except (ValueError, TypeError):
                pass

    recent_facts.sort(key=lambda x: (-x[0], x[1]))  # Highest confidence, most recent

    for conf, age, claim in recent_facts[:max_items]:
        age_str = f"{int(age)}h" if age < 24 else f"{int(age/24)}d"
        highlights.append(f"[{conf:.0%}] {truncate(claim, 70)} ({age_str} ago)")

    stats = {"recent_high_conf": len(recent_facts)}
    return highlights, stats


# ============================================================
# Main Execution
# ============================================================
def format_briefing(sections: List[Tuple[str, List[str], Dict]], elapsed: float) -> str:
    """Format the briefing report."""
    lines = []
    lines.append("# Daily Briefing")
    lines.append("")
    lines.append(f"*Generated: {utc_now().strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append("")

    sections_shown = 0

    for title, highlights, stats in sections:
        if not highlights:
            continue

        lines.append(f"## {title}")
        lines.append("")
        for h in highlights:
            lines.append(f"- {h}")
        lines.append("")
        sections_shown += 1

    if sections_shown == 0:
        lines.append("*No significant insights to surface. All systems nominal.*")
        lines.append("")

    lines.append("---")
    lines.append(f"*{sections_shown} sections | {elapsed:.1f}s*")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            days_back: int (default 7)
            max_per_section: int (default 3)
        }
        tools: {
            query_memory: callable
            semantic_search: callable (optional)
        }
        context: {run_id, timeout}

    Returns:
        {
            success: bool,
            report: str,
            sections: list,
            elapsed_seconds: float,
        }
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    # Parse args
    days_back = args.get("days_back", DEFAULT_CONFIG["days_back"])
    max_per_section = args.get("max_per_section", DEFAULT_CONFIG["max_per_section"])
    max_artifacts = args.get("max_artifacts", DEFAULT_CONFIG["max_artifacts"])

    query_memory = tools.get("query_memory")
    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    # Collect artifacts
    since_date = (utc_now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    all_artifacts = []

    for art_type in ["fact", "decision", "log", "episode", "incident_rca"]:
        if time.time() - start_time >= timeout * 0.8:
            break
        try:
            result = query_memory(artifact_type=art_type, since=since_date, limit=max_artifacts)
            items = result if isinstance(result, list) else result.get("results", [])
            for item in items:
                if "artifact_type" not in item:
                    item["artifact_type"] = art_type
                all_artifacts.append(item)
        except Exception:
            continue

    if not all_artifacts:
        return {
            "success": True,
            "report": "# Daily Briefing\n\n*No artifacts found in the last {days_back} days.*",
            "sections": [],
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    # Run analyses
    sections = []

    # 1. Recent Activity
    highlights, stats = analyze_activity(all_artifacts, max_per_section)
    sections.append(("Recent Activity", highlights, stats))

    # 2. Decisions Needing Review
    highlights, stats = analyze_decisions(all_artifacts, max_per_section)
    sections.append(("Decisions to Review", highlights, stats))

    # 3. Emerging Patterns
    highlights, stats = analyze_patterns(all_artifacts, max_per_section)
    sections.append(("Emerging Patterns", highlights, stats))

    # 4. Key Facts
    highlights, stats = analyze_facts(all_artifacts, max_per_section)
    sections.append(("Recent High-Confidence Facts", highlights, stats))

    # 5. Maintenance
    highlights, stats = analyze_maintenance(all_artifacts, max_per_section)
    sections.append(("Maintenance", highlights, stats))

    # Format
    elapsed = round(time.time() - start_time, 2)
    report = format_briefing(sections, elapsed)

    sections_output = [
        {"title": title, "highlights": highlights, "stats": stats}
        for title, highlights, stats in sections
        if highlights
    ]

    return {
        "success": True,
        "report": report,
        "sections": sections_output,
        "total_artifacts": len(all_artifacts),
        "sections_shown": len(sections_output),
        "elapsed_seconds": elapsed,
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("briefing Skill v1.1.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Sections:")
    print("  1. Recent Activity - what happened today/yesterday")
    print("  2. Decisions to Review - old unverified decisions")
    print("  3. Emerging Patterns - unarticulated themes")
    print("  4. Recent High-Confidence Facts - new learnings")
    print("  5. Maintenance - stale/orphan artifacts")
    print()
    print("Default config:")
    for k, v in DEFAULT_CONFIG.items():
        print(f"  {k}: {v}")
