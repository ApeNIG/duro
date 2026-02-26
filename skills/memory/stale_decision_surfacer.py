"""
Skill: stale_decision_surfacer
Description: Surface stale decisions that need attention before they rot
Version: 1.0.0
Tier: tested

Decisions must not be allowed to rot. This skill is the foreman that:
1. Finds unreviewed decisions older than N days
2. Finds reviewed decisions with no follow-through
3. Finds contradictions (said X, did Y)
4. Creates actionable tasks to validate/supersede/link each stale decision

Run this at session start or as step 0 in daily_synthesis.

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict


SKILL_META = {
    "name": "stale_decision_surfacer",
    "description": "Surface stale decisions that need attention before they rot",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Feedback loop discipline - decisions without validation = dead weight",
    "validated": "2026-02-26",
    "triggers": [
        "stale decisions", "decision rot", "unreviewed decisions",
        "decision surfacer", "decision audit"
    ],
    "keywords": [
        "decisions", "stale", "surfacer", "review", "validation",
        "follow-through", "accountability", "rot", "foreman"
    ],
    "phase": "4.0",
}

DEFAULT_CONFIG = {
    "stale_days": 7,           # Decisions older than this need attention
    "max_items": 20,           # Max decisions to surface
    "auto_log_tasks": True,    # Log a task per stale decision
    "include_contradictions": True,  # Also surface contradicted decisions
    "exclude_tags": ["smoke-test", "auto-outcome", "generated", "test"],
}

REQUIRES = ["query_memory"]  # log_task is optional

DEFAULT_TIMEOUT = 60


def parse_date(timestamp: str) -> Optional[datetime]:
    """Parse ISO timestamp to datetime."""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(timestamp[:26], fmt)
        except (ValueError, TypeError):
            continue
    return None


def extract_decision_text(artifact: Dict) -> str:
    """Extract decision text from artifact."""
    # Index entry format
    title = artifact.get("title", "")
    if title:
        return str(title)
    # Full artifact format
    if "data" in artifact:
        return artifact["data"].get("decision", "") or ""
    return artifact.get("decision", "") or ""


def extract_timestamp(artifact: Dict) -> str:
    """Extract timestamp from artifact."""
    return (
        artifact.get("created_at", "") or
        artifact.get("timestamp", "") or
        (artifact.get("data", {}) or {}).get("created_at", "") or
        ""
    )


def extract_tags(artifact: Dict) -> List[str]:
    """Extract tags from artifact."""
    return artifact.get("tags", []) or []


def extract_status(artifact: Dict) -> str:
    """Extract validation status from artifact."""
    if "data" in artifact:
        return artifact["data"].get("status", "unverified")
    return artifact.get("status", "unverified")


def extract_confidence(artifact: Dict) -> float:
    """Extract confidence from artifact."""
    if "data" in artifact:
        conf = artifact["data"].get("confidence")
    else:
        conf = artifact.get("confidence")
    try:
        return float(conf) if conf is not None else 0.5
    except (ValueError, TypeError):
        return 0.5


def format_report(
    stale_unreviewed: List[Dict],
    stale_validated: List[Dict],
    contradicted: List[Dict],
    tasks_logged: int,
    stale_days: int,
) -> str:
    """Generate markdown report."""
    lines = []
    lines.append("# Stale Decision Report")
    lines.append(f"*Threshold: {stale_days} days | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC*")
    lines.append("")

    total_stale = len(stale_unreviewed) + len(stale_validated) + len(contradicted)
    lines.append(f"**Total stale decisions:** {total_stale}")
    lines.append(f"**Tasks logged:** {tasks_logged}")
    lines.append("")

    # Section 1: Never reviewed
    if stale_unreviewed:
        lines.append(f"## Never Reviewed ({len(stale_unreviewed)})")
        lines.append("*Decisions made but never validated - action: validate or supersede*")
        lines.append("")
        for d in stale_unreviewed[:10]:
            age = d.get("days_since", 0)
            text = d.get("decision_text", "")[:100]
            decision_id = d.get("decision_id", "")
            confidence = d.get("confidence", 0.5)
            lines.append(f"- **{age}d ago** (conf: {confidence:.0%}): {text}")
            lines.append(f"  `{decision_id}`")
        lines.append("")

    # Section 2: Validated but no follow-through
    if stale_validated:
        lines.append(f"## Validated Without Follow-Through ({len(stale_validated)})")
        lines.append("*Reviewed but no linked work - action: link to episode or mark superseded*")
        lines.append("")
        for d in stale_validated[:10]:
            age = d.get("days_since", 0)
            text = d.get("decision_text", "")[:100]
            decision_id = d.get("decision_id", "")
            lines.append(f"- **{age}d ago**: {text}")
            lines.append(f"  `{decision_id}`")
        lines.append("")

    # Section 3: Contradictions
    if contradicted:
        lines.append(f"## Potential Contradictions ({len(contradicted)})")
        lines.append("*Decisions with activity that contradicts them - action: supersede or clarify*")
        lines.append("")
        for d in contradicted[:5]:
            text = d.get("decision_text", "")[:100]
            decision_id = d.get("decision_id", "")
            signals = d.get("contradiction_signals", [])
            lines.append(f"- {text}")
            lines.append(f"  Signals: {', '.join(signals[:3])}")
            lines.append(f"  `{decision_id}`")
        lines.append("")

    # No stale decisions
    if total_stale == 0:
        lines.append("All decisions are current. No rot detected.")
        lines.append("")

    # Quick actions
    lines.append("## Quick Actions")
    if stale_unreviewed:
        top = stale_unreviewed[0]
        lines.append(f"1. Review oldest: `duro_review_decision(decision_id=\"{top['decision_id']}\")`")
    if contradicted:
        top = contradicted[0]
        lines.append(f"2. Resolve contradiction: `duro_validate_decision(decision_id=\"{top['decision_id']}\", status=\"superseded\")`")
    if not stale_unreviewed and not contradicted:
        lines.append("- No urgent actions needed")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            stale_days: int (default 7) - Decisions older than this need attention
            max_items: int (default 20) - Max decisions to surface
            auto_log_tasks: bool (default True) - Log a task per stale decision
            include_contradictions: bool (default True) - Also check for contradictions
            exclude_tags: List[str] - Tags to exclude (smoke-test, generated, etc.)
        }
        tools: {
            query_memory: callable - Query artifacts
            semantic_search: callable - For contradiction detection (optional)
            log_task: callable - Log tasks for stale decisions
        }
        context: {run_id, timeout}

    Returns:
        {
            success: bool,
            report: str - Markdown report
            stale_count: int
            tasks_logged: int
            stale_unreviewed: List[Dict]
            stale_validated: List[Dict]
            contradicted: List[Dict]
            elapsed_seconds: float
        }
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    # Parse args
    stale_days = args.get("stale_days", DEFAULT_CONFIG["stale_days"])
    max_items = args.get("max_items", DEFAULT_CONFIG["max_items"])
    auto_log_tasks = args.get("auto_log_tasks", DEFAULT_CONFIG["auto_log_tasks"])
    include_contradictions = args.get("include_contradictions", DEFAULT_CONFIG["include_contradictions"])
    exclude_tags = set(args.get("exclude_tags", DEFAULT_CONFIG["exclude_tags"]))

    query_memory = tools.get("query_memory")
    semantic_search = tools.get("semantic_search")
    log_task = tools.get("log_task")

    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    now = datetime.utcnow()
    cutoff_date = now - timedelta(days=stale_days)

    # ==============================
    # Step 1: Load all decisions
    # ==============================
    try:
        result = query_memory(artifact_type="decision", limit=200)
        decisions = []
        if isinstance(result, list):
            decisions = result
        elif isinstance(result, dict):
            decisions = result.get("results", result.get("artifacts", []))
    except Exception as e:
        return {"success": False, "error": f"Failed to query decisions: {e}"}

    if not decisions:
        return {
            "success": True,
            "report": "No decisions found in memory.",
            "stale_count": 0,
            "tasks_logged": 0,
            "stale_unreviewed": [],
            "stale_validated": [],
            "contradicted": [],
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    # ==============================
    # Step 2: Load validation events to check which decisions are validated
    # ==============================
    validated_decision_ids = set()
    validation_dates = {}  # decision_id -> last validation date

    try:
        validations = query_memory(artifact_type="decision_validation", limit=500)
        val_list = []
        if isinstance(validations, list):
            val_list = validations
        elif isinstance(validations, dict):
            val_list = validations.get("results", validations.get("artifacts", []))

        import re
        for v in val_list:
            data = v.get("data", v)
            decision_ref = data.get("decision_id", "") or data.get("message", "")
            match = re.search(r'(decision_\d{8}_\d{6}_\w+)', str(decision_ref))
            if match:
                decision_id = match.group(1)
                validated_decision_ids.add(decision_id)
                # Track validation date
                val_date = extract_timestamp(v)
                if val_date:
                    validation_dates[decision_id] = val_date
    except Exception:
        pass

    # ==============================
    # Step 3: Load episodes to check for linked work
    # ==============================
    linked_decision_ids = set()

    try:
        episodes = query_memory(artifact_type="episode", limit=200)
        ep_list = []
        if isinstance(episodes, list):
            ep_list = episodes
        elif isinstance(episodes, dict):
            ep_list = episodes.get("results", episodes.get("artifacts", []))

        import re
        for ep in ep_list:
            data = ep.get("data", ep)
            links = data.get("links", {}) or {}
            decisions_used = links.get("decisions_used", []) or []
            decisions_created = links.get("decisions_created", []) or []
            for d_id in decisions_used + decisions_created:
                if d_id:
                    linked_decision_ids.add(d_id)
    except Exception:
        pass

    # ==============================
    # Step 4: Classify decisions
    # ==============================
    stale_unreviewed = []  # Never validated
    stale_validated = []   # Validated but no linked work
    contradicted = []      # Has contradiction signals

    for decision in decisions:
        decision_id = decision.get("id", "")
        decision_text = extract_decision_text(decision)
        timestamp = extract_timestamp(decision)
        tags = extract_tags(decision)
        confidence = extract_confidence(decision)

        # Skip excluded tags
        if any(t.lower() in exclude_tags for t in tags):
            continue

        # Skip if no decision text
        if not decision_text or len(decision_text.strip()) < 10:
            continue

        # Calculate age
        decision_date = parse_date(timestamp)
        if not decision_date:
            continue

        days_since = (now - decision_date).days

        # Skip if not stale yet
        if days_since < stale_days:
            continue

        decision_info = {
            "decision_id": decision_id,
            "decision_text": decision_text[:200],
            "decision_date": timestamp,
            "days_since": days_since,
            "tags": tags,
            "confidence": confidence,
            "is_validated": decision_id in validated_decision_ids,
            "is_linked": decision_id in linked_decision_ids,
        }

        # Classify
        if decision_id not in validated_decision_ids:
            # Never reviewed
            stale_unreviewed.append(decision_info)
        elif decision_id not in linked_decision_ids:
            # Validated but no follow-through
            stale_validated.append(decision_info)

    # Sort by age (oldest first)
    stale_unreviewed.sort(key=lambda x: x["days_since"], reverse=True)
    stale_validated.sort(key=lambda x: x["days_since"], reverse=True)

    # Limit results
    stale_unreviewed = stale_unreviewed[:max_items]
    stale_validated = stale_validated[:max_items // 2]

    # ==============================
    # Step 5: Contradiction detection (optional)
    # ==============================
    if include_contradictions and semantic_search and time.time() - start_time < timeout * 0.7:
        # Check a sample of decisions for contradictions
        import re
        CONTRADICTION_PATTERNS = [
            r'\bnot\b', r'\bno longer\b', r'\binstead\b', r'\brevert',
            r'\bundo\b', r'\babandoned?\b', r'\bdropped?\b', r'\breplac',
            r'\boverrid', r'\brolled?\s*back\b', r'\bremoved?\b',
        ]

        for decision in decisions[:20]:  # Sample first 20
            if time.time() - start_time >= timeout * 0.8:
                break

            decision_id = decision.get("id", "")
            decision_text = extract_decision_text(decision)

            if not decision_text or len(decision_text) < 20:
                continue

            # Skip if already in stale lists
            if any(d["decision_id"] == decision_id for d in stale_unreviewed + stale_validated):
                continue

            try:
                result = semantic_search(query=decision_text[:150], limit=5)
                items = []
                if isinstance(result, dict):
                    items = result.get("results", [])
                elif isinstance(result, list):
                    items = result

                contradiction_signals = []

                for item in items:
                    item_id = item.get("id", "")
                    item_type = item.get("artifact_type", item.get("type", ""))

                    # Skip self and decisions
                    if item_id == decision_id or item_type == "decision":
                        continue

                    item_text = item.get("title", "") or ""
                    if "data" in item:
                        item_text = item["data"].get("message", "") or item_text

                    # Check for contradiction patterns
                    item_lower = item_text.lower()
                    for pattern in CONTRADICTION_PATTERNS:
                        if re.search(pattern, item_lower):
                            # Check topic overlap
                            decision_words = set(re.findall(r'[a-zA-Z]{4,}', decision_text.lower()))
                            overlap = sum(1 for w in decision_words if w in item_lower)
                            if overlap >= 2:
                                contradiction_signals.append(re.sub(r'\\b|\\s\*', '', pattern))

                if contradiction_signals:
                    contradicted.append({
                        "decision_id": decision_id,
                        "decision_text": decision_text[:200],
                        "contradiction_signals": list(set(contradiction_signals))[:5],
                    })

            except Exception:
                pass

    contradicted = contradicted[:5]  # Limit contradictions

    # ==============================
    # Step 6: Auto-log tasks (optional - only if log_task available)
    # ==============================
    tasks_logged = 0

    if auto_log_tasks and log_task is not None:
        # Log tasks for unreviewed decisions
        for d in stale_unreviewed[:5]:
            try:
                task_desc = f"Validate decision: {d['decision_text'][:80]}..."
                outcome = f"Decision ID: {d['decision_id']} | {d['days_since']} days old"
                log_task(task=task_desc, outcome=outcome)
                tasks_logged += 1
            except Exception:
                pass

        # Log tasks for contradictions
        for d in contradicted[:3]:
            try:
                task_desc = f"Resolve contradiction: {d['decision_text'][:80]}..."
                outcome = f"Decision ID: {d['decision_id']} | Signals: {', '.join(d['contradiction_signals'][:2])}"
                log_task(task=task_desc, outcome=outcome)
                tasks_logged += 1
            except Exception:
                pass

    # ==============================
    # Step 7: Generate report
    # ==============================
    report = format_report(
        stale_unreviewed,
        stale_validated,
        contradicted,
        tasks_logged,
        stale_days,
    )

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "report": report,
        "stale_count": len(stale_unreviewed) + len(stale_validated) + len(contradicted),
        "tasks_logged": tasks_logged,
        "stale_unreviewed": stale_unreviewed,
        "stale_validated": stale_validated,
        "contradicted": contradicted,
        "elapsed_seconds": elapsed,
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("stale_decision_surfacer Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Surfaces:")
    print("  1. Unreviewed decisions older than N days")
    print("  2. Validated decisions with no linked work")
    print("  3. Potential contradictions (said X, did Y)")
    print()
    print("Actions:")
    print("  - Auto-logs tasks for stale decisions")
    print("  - Generates markdown report")
    print()
    print("Default config:")
    for k, v in DEFAULT_CONFIG.items():
        print(f"  {k}: {v}")
