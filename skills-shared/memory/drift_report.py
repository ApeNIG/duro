"""
Skill: drift_report
Description: Compare stated intentions (decisions) vs actual behavior (episodes, logs)
Version: 1.0.0
Tier: tested

The accountability tool. Surfaces:
- Decisions with no follow-up activity (stated but never acted on)
- Decisions with contradicting follow-up (said X, did Y)
- Active themes in logs/episodes that have no corresponding decision (doing without deciding)
- Stale decisions (old, never validated or revisited)

This closes the say-do gap by holding a mirror up to the user's
decision-making vs actual behavior.

Flow:
1. Load all decisions within the time window
2. For each decision, search for follow-up activity (logs, episodes)
3. Score follow-through: none, partial, full, contradicted
4. Scan logs/episodes for themes with no parent decision
5. Report with accountability metrics

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import re
import time
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


SKILL_META = {
    "name": "drift_report",
    "description": "Compare stated intentions (decisions) vs actual behavior (episodes, logs)",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Reflective layer roadmap (Greg Eisenberg x Internet Vin podcast)",
    "validated": "2026-02-24",
    "triggers": ["drift", "accountability", "follow-through", "say vs do", "decisions vs actions"],
    "keywords": [
        "drift", "accountability", "follow-through", "decisions", "actions",
        "intention", "behavior", "stale", "contradiction", "gap"
    ],
    "phase": "4.0",
}

DEFAULT_CONFIG = {
    "days_back": 30,
    "max_decisions": 100,
    "follow_up_search_limit": 10,
    "stale_threshold_days": 14,     # Decision with no activity for this long = stale
    "min_followup_similarity": 0.3, # Minimum relevance to count as follow-up
}

REQUIRES = ["query_memory", "semantic_search"]

DEFAULT_TIMEOUT = 60


class FollowThrough(Enum):
    """How well a decision was followed through."""
    NONE = "none"               # No related activity found
    PARTIAL = "partial"         # Some activity, but incomplete signals
    FULL = "full"               # Clear follow-up activity
    CONTRADICTED = "contradicted"  # Activity that reverses the decision


@dataclass
class DecisionTrace:
    """A decision with its follow-up analysis."""
    decision_id: str
    decision_text: str
    decision_date: str
    tags: List[str]
    confidence: Optional[float] = None
    follow_through: FollowThrough = FollowThrough.NONE
    follow_up_count: int = 0
    follow_up_artifacts: List[Dict] = field(default_factory=list)
    days_since: int = 0
    is_stale: bool = False
    is_validated: bool = False
    contradiction_signals: List[str] = field(default_factory=list)
    score: float = 0.0  # 0 = worst drift, 1 = perfect follow-through


@dataclass
class UndecidedTheme:
    """Activity happening without a corresponding decision."""
    theme: str
    log_count: int
    sample_text: str
    date_range: str
    tags: List[str]


def extract_text(artifact: Dict) -> str:
    # Index entries from query_memory have 'title' at top level
    title = artifact.get("title", "")
    if title:
        return str(title)
    if "data" in artifact:
        data = artifact["data"]
        parts = []
        for key in ("decision", "rationale", "message", "claim", "title"):
            val = data.get(key, "")
            if val:
                parts.append(str(val))
        return " ".join(parts) if parts else ""
    for key in ("decision", "message", "claim"):
        val = artifact.get(key, "")
        if val:
            return str(val)
    return ""


def extract_decision_text(artifact: Dict) -> str:
    """Extract the core decision statement.

    query_memory returns index entries with 'title' (not full artifact with data.decision).
    Semantic search may return full artifacts. Handle both.
    """
    # Index entry format (from query_memory)
    title = artifact.get("title", "")
    if title:
        return str(title)
    # Full artifact format (from semantic search or file read)
    if "data" in artifact:
        return artifact["data"].get("decision", "") or artifact["data"].get("message", "") or ""
    return artifact.get("decision", "") or artifact.get("message", "") or ""


def extract_timestamp(artifact: Dict) -> str:
    return (
        artifact.get("created_at", "") or
        artifact.get("timestamp", "") or
        (artifact.get("data", {}) or {}).get("created_at", "") or
        ""
    )


def extract_tags(artifact: Dict) -> List[str]:
    return artifact.get("tags", []) or []


def extract_confidence(artifact: Dict) -> Optional[float]:
    if "data" in artifact:
        conf = artifact["data"].get("confidence")
    else:
        conf = artifact.get("confidence")
    if conf is not None:
        try:
            return float(conf)
        except (ValueError, TypeError):
            pass
    return None


def parse_date(timestamp: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f",
                 "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(timestamp[:26], fmt)
        except (ValueError, TypeError):
            continue
    return None


CONTRADICTION_PATTERNS = [
    r'\bnot\b', r'\bno longer\b', r'\binstead\b', r'\brevert',
    r'\bundo\b', r'\babandoned?\b', r'\bdropped?\b', r'\breplac',
    r'\boverrid', r'\brolled?\s*back\b', r'\bremoved?\b',
    r'\bdisabled?\b', r'\bwrong\b', r'\bmistake\b',
]


def check_contradiction(decision_text: str, followup_text: str) -> List[str]:
    """Check if follow-up text contradicts the decision."""
    signals = []
    followup_lower = followup_text.lower()

    # Extract key nouns/verbs from decision for context
    decision_words = set(re.findall(r'[a-zA-Z]{4,}', decision_text.lower()))

    # Only flag contradictions if the follow-up is actually about the same topic
    overlap = sum(1 for w in decision_words if w in followup_lower)
    if overlap < 2:
        return []

    for pattern in CONTRADICTION_PATTERNS:
        if re.search(pattern, followup_lower):
            signals.append(re.sub(r'\\b|\\s\*', '', pattern))

    return signals


def score_follow_through(trace: DecisionTrace) -> float:
    """Score a decision's follow-through from 0 (worst) to 1 (best)."""
    if trace.follow_through == FollowThrough.FULL:
        return 1.0
    elif trace.follow_through == FollowThrough.PARTIAL:
        return 0.5
    elif trace.follow_through == FollowThrough.CONTRADICTED:
        return 0.1
    else:  # NONE
        # Newer decisions get more grace period
        if trace.days_since <= 3:
            return 0.6  # Too soon to judge
        elif trace.days_since <= 7:
            return 0.3
        else:
            return 0.0


def format_report(
    traces: List[DecisionTrace],
    undecided_themes: List[UndecidedTheme],
    days_back: int,
    total_decisions: int,
) -> str:
    lines = []
    lines.append("## Drift Report — Decisions vs Actions")
    lines.append("")
    lines.append(f"**Window:** last {days_back} days | **Decisions analyzed:** {total_decisions}")

    # Summary metrics
    if traces:
        avg_score = sum(t.score for t in traces) / len(traces)
        full_count = sum(1 for t in traces if t.follow_through == FollowThrough.FULL)
        partial_count = sum(1 for t in traces if t.follow_through == FollowThrough.PARTIAL)
        none_count = sum(1 for t in traces if t.follow_through == FollowThrough.NONE)
        contradicted_count = sum(1 for t in traces if t.follow_through == FollowThrough.CONTRADICTED)
        stale_count = sum(1 for t in traces if t.is_stale)
        validated_count = sum(1 for t in traces if t.is_validated)

        lines.append(f"**Follow-through score:** {avg_score:.0%}")
        lines.append(f"**Breakdown:** {full_count} full, {partial_count} partial, {none_count} none, {contradicted_count} contradicted")
        lines.append(f"**Stale:** {stale_count} | **Validated:** {validated_count}")
    lines.append("")

    # --- Decisions with no follow-up (the drift) ---
    no_followup = [t for t in traces if t.follow_through == FollowThrough.NONE and t.days_since > 3]
    if no_followup:
        no_followup.sort(key=lambda t: t.days_since, reverse=True)
        lines.append(f"### Decisions Without Follow-Up ({len(no_followup)})")
        lines.append("")
        for t in no_followup[:10]:
            stale_marker = " **[STALE]**" if t.is_stale else ""
            lines.append(f"- **{t.decision_date[:10]}** ({t.days_since}d ago){stale_marker}: {t.decision_text[:150]}")
            if t.tags:
                lines.append(f"  Tags: {', '.join(t.tags[:5])}")
        lines.append("")

    # --- Contradictions ---
    contradictions = [t for t in traces if t.follow_through == FollowThrough.CONTRADICTED]
    if contradictions:
        lines.append(f"### Potential Contradictions ({len(contradictions)})")
        lines.append("")
        for t in contradictions[:5]:
            lines.append(f"- **{t.decision_date[:10]}**: {t.decision_text[:120]}")
            lines.append(f"  Signals: {', '.join(t.contradiction_signals[:3])}")
            if t.follow_up_artifacts:
                latest = t.follow_up_artifacts[0]
                lines.append(f"  Contradicting: {latest.get('text', '')[:120]}")
        lines.append("")

    # --- Strong follow-through ---
    followed = [t for t in traces if t.follow_through == FollowThrough.FULL]
    if followed:
        lines.append(f"### Good Follow-Through ({len(followed)})")
        lines.append("")
        for t in followed[:5]:
            lines.append(f"- **{t.decision_date[:10]}**: {t.decision_text[:120]} ({t.follow_up_count} follow-ups)")
        lines.append("")

    # --- Undecided themes ---
    if undecided_themes:
        lines.append(f"### Activity Without Decisions ({len(undecided_themes)})")
        lines.append("*Themes you're actively working on but haven't made a formal decision about:*")
        lines.append("")
        for theme in undecided_themes[:7]:
            lines.append(f"- **{theme.theme}** — {theme.log_count} logs ({theme.date_range})")
            lines.append(f"  Example: {theme.sample_text[:120]}")
        lines.append("")

    if not no_followup and not contradictions and not undecided_themes:
        lines.append("No significant drift detected. Decisions are well-aligned with actions.")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            days_back: int (default 30)
            max_decisions: int (default 100)
            stale_days: int (default 14) - Days before a decision is considered stale
        }
        tools: {
            query_memory: callable
            semantic_search: callable
        }
        context: {run_id, timeout}
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    days_back = args.get("days_back", DEFAULT_CONFIG["days_back"])
    max_decisions = args.get("max_decisions", DEFAULT_CONFIG["max_decisions"])
    stale_days = args.get("stale_days", DEFAULT_CONFIG["stale_threshold_days"])
    followup_limit = args.get("follow_up_search_limit", DEFAULT_CONFIG["follow_up_search_limit"])

    query_memory = tools.get("query_memory")
    semantic_search = tools.get("semantic_search")

    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    now = datetime.utcnow()
    since_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # ==============================
    # Step 1: Load decisions
    # ==============================
    try:
        result = query_memory(artifact_type="decision", since=since_date, limit=max_decisions)
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
            "report": f"No decisions found in last {days_back} days.",
            "traces": [],
            "undecided_themes": [],
            "total_decisions": 0,
            "avg_follow_through": 0,
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    # ==============================
    # Step 2: Load validations to check which decisions are validated
    # ==============================
    validated_decision_ids = set()
    try:
        validations = query_memory(artifact_type="decision_validation", since=since_date, limit=200)
        val_list = []
        if isinstance(validations, list):
            val_list = validations
        elif isinstance(validations, dict):
            val_list = validations.get("results", validations.get("artifacts", []))
        for v in val_list:
            # Extract the decision ID this validation refers to
            data = v.get("data", v)
            decision_ref = data.get("decision_id", "") or data.get("message", "")
            # Try to extract decision ID from message like "Validation: decision_xxx -> validated"
            import re as _re
            match = _re.search(r'(decision_\d{8}_\d{6}_\w+)', str(decision_ref))
            if match:
                validated_decision_ids.add(match.group(1))
    except Exception:
        pass

    # ==============================
    # Step 3: For each decision, search for follow-up activity
    # ==============================
    traces = []
    budget_per_decision = max(1, int((timeout * 0.6) / max(len(decisions), 1)))

    for decision in decisions:
        if time.time() - start_time >= timeout * 0.75:
            break

        decision_id = decision.get("id", "")
        decision_text = extract_decision_text(decision)
        full_text = extract_text(decision)
        timestamp = extract_timestamp(decision)
        tags = extract_tags(decision)
        confidence = extract_confidence(decision)

        if not decision_text or len(decision_text.strip()) < 10:
            continue

        decision_date = parse_date(timestamp)
        days_since = (now - decision_date).days if decision_date else 0

        trace = DecisionTrace(
            decision_id=decision_id,
            decision_text=decision_text[:300],
            decision_date=timestamp,
            tags=tags,
            confidence=confidence,
            days_since=days_since,
            is_stale=days_since >= stale_days,
            is_validated=decision_id in validated_decision_ids,
        )

        # Search for follow-up using semantic search
        follow_ups = []
        if semantic_search:
            try:
                # Build a search query from the decision's key terms
                search_query = decision_text[:200]
                result = semantic_search(query=search_query, limit=followup_limit)
                items = []
                if isinstance(result, dict):
                    items = result.get("results", [])
                elif isinstance(result, list):
                    items = result

                for item in items:
                    item_id = item.get("id", "")
                    item_type = item.get("artifact_type", item.get("type", ""))

                    # Skip the decision itself and other decisions
                    if item_id == decision_id:
                        continue
                    if item_type == "decision":
                        continue
                    # Skip decision validations (they're administrative, not behavioral)
                    if item_type == "decision_validation":
                        continue

                    item_text = extract_text(item)
                    item_date = extract_timestamp(item)

                    # Only count follow-ups that came AFTER the decision
                    item_dt = parse_date(item_date)
                    if decision_date and item_dt and item_dt < decision_date:
                        continue

                    # Check for contradictions
                    contra_signals = check_contradiction(decision_text, item_text)

                    follow_ups.append({
                        "id": item_id,
                        "type": item_type,
                        "text": item_text[:200],
                        "date": item_date,
                        "contradiction_signals": contra_signals,
                    })

            except Exception:
                pass

        # Classify follow-through
        trace.follow_up_count = len(follow_ups)
        trace.follow_up_artifacts = follow_ups[:3]

        has_contradiction = any(fu.get("contradiction_signals") for fu in follow_ups)

        if has_contradiction:
            trace.follow_through = FollowThrough.CONTRADICTED
            trace.contradiction_signals = []
            for fu in follow_ups:
                trace.contradiction_signals.extend(fu.get("contradiction_signals", []))
            trace.contradiction_signals = list(set(trace.contradiction_signals))[:5]
        elif len(follow_ups) >= 3:
            trace.follow_through = FollowThrough.FULL
        elif len(follow_ups) >= 1:
            trace.follow_through = FollowThrough.PARTIAL
        else:
            trace.follow_through = FollowThrough.NONE

        trace.score = score_follow_through(trace)
        traces.append(trace)

    # ==============================
    # Step 4: Find undecided themes (active in logs, no decision)
    # ==============================
    undecided_themes = []

    if time.time() - start_time < timeout * 0.9:
        # Get decision tags to know what's already "decided"
        decided_tags = set()
        for d in decisions:
            decided_tags.update(t.lower() for t in extract_tags(d))

        # Get recent log tags
        try:
            logs = query_memory(artifact_type="log", since=since_date, limit=300)
            log_list = []
            if isinstance(logs, list):
                log_list = logs
            elif isinstance(logs, dict):
                log_list = logs.get("results", logs.get("artifacts", []))

            # Count tag frequency in logs
            log_tag_counts = defaultdict(int)
            log_tag_samples = {}
            log_tag_dates = defaultdict(list)

            for log_entry in log_list:
                tags = extract_tags(log_entry)
                text = extract_text(log_entry)
                ts = extract_timestamp(log_entry)
                for tag in tags:
                    tag_lower = tag.lower()
                    log_tag_counts[tag_lower] += 1
                    if tag_lower not in log_tag_samples:
                        log_tag_samples[tag_lower] = text[:200]
                    if ts:
                        log_tag_dates[tag_lower].append(ts[:10])

            # Find tags active in logs but absent from decisions
            # Skip generic/meta tags
            skip_tags = {
                "auto-graduated", "graduated-fact", "graduated-decision",
                "graduated-insight", "emerged-pattern", "duro", "log",
                "task", "session", "process",
            }

            for tag, count in sorted(log_tag_counts.items(), key=lambda x: -x[1]):
                if count < 3:
                    break
                if tag in decided_tags or tag in skip_tags:
                    continue
                dates = sorted(log_tag_dates.get(tag, []))
                date_range = f"{dates[0]}→{dates[-1]}" if dates else ""
                undecided_themes.append(UndecidedTheme(
                    theme=tag,
                    log_count=count,
                    sample_text=log_tag_samples.get(tag, ""),
                    date_range=date_range,
                    tags=[tag],
                ))
                if len(undecided_themes) >= 10:
                    break

        except Exception:
            pass

    # ==============================
    # Step 5: Report
    # ==============================
    report = format_report(traces, undecided_themes, days_back, len(traces))

    # Serialize
    traces_output = [
        {
            "decision_id": t.decision_id,
            "decision_text": t.decision_text,
            "decision_date": t.decision_date,
            "follow_through": t.follow_through.value,
            "follow_up_count": t.follow_up_count,
            "days_since": t.days_since,
            "is_stale": t.is_stale,
            "is_validated": t.is_validated,
            "score": t.score,
            "contradiction_signals": t.contradiction_signals,
        }
        for t in traces
    ]

    undecided_output = [
        {
            "theme": u.theme,
            "log_count": u.log_count,
            "sample": u.sample_text,
            "date_range": u.date_range,
        }
        for u in undecided_themes
    ]

    avg_score = sum(t.score for t in traces) / len(traces) if traces else 0

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "report": report,
        "traces": traces_output,
        "undecided_themes": undecided_output,
        "total_decisions": len(traces),
        "avg_follow_through": round(avg_score, 2),
        "elapsed_seconds": elapsed,
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("drift_report Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Accountability metrics:")
    print("  - Follow-through: none / partial / full / contradicted")
    print("  - Stale decisions (no activity in 14+ days)")
    print("  - Undecided themes (active in logs, no decision)")
    print()
    print("Default config:")
    for k, v in DEFAULT_CONFIG.items():
        print(f"  {k}: {v}")
