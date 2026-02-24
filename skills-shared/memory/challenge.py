"""
Skill: challenge
Description: Pressure test beliefs and decisions against documented experience
Version: 1.0.0
Tier: tested

Devil's advocate mode - finds contradicting evidence in the user's own
artifact history to challenge current thinking.

Inspired by: Podcast discussion of /challenge command for Obsidian + Claude

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

from typing import Dict, List, Any, Tuple
from datetime import datetime, timezone, timedelta


# Skill metadata
SKILL_META = {
    "name": "challenge",
    "description": "Pressure test beliefs and decisions against documented experience",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Podcast - Obsidian + Claude Code integration",
    "validated": "2026-02-24",
    "triggers": ["challenge", "pressure test", "devil's advocate", "counterarguments"],
    "keywords": [
        "challenge", "pressure", "test", "contradict", "counterargument",
        "devil", "advocate", "bias", "assumption", "belief", "validate"
    ],
    "phase": "4.0",
}

# Required capabilities
REQUIRES = ["query_memory", "semantic_search"]

# Default configuration
DEFAULT_CONFIG = {
    "max_artifacts": 50,
    "min_contradiction_score": 0.3,
}


def find_contradictions(
    belief: str,
    artifacts: List[Dict],
    semantic_search
) -> List[Dict]:
    """Find artifacts that might contradict the belief."""

    contradictions = []

    # Search for opposite/contrary terms
    contrary_searches = [
        f"problem with {belief}",
        f"failed {belief}",
        f"against {belief}",
        f"instead of {belief}",
        f"not {belief}",
    ]

    seen_ids = set()

    for search_query in contrary_searches:
        try:
            results = semantic_search(query=search_query, limit=5)
            items = results.get("results", []) if isinstance(results, dict) else results

            for item in items:
                item_id = item.get("id", "")
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    contradictions.append({
                        "artifact": item,
                        "search_query": search_query,
                    })
        except Exception:
            continue

    return contradictions


def find_past_failures(
    belief: str,
    artifacts: List[Dict]
) -> List[Dict]:
    """Find incidents or failed decisions related to the belief."""

    failures = []
    belief_lower = belief.lower()

    for art in artifacts:
        art_type = art.get("type") or art.get("artifact_type", "")
        data = art.get("data", art)

        # Check incidents
        if art_type == "incident_rca":
            symptom = data.get("symptom", "").lower()
            actual_cause = data.get("actual_cause", "").lower()

            # Check if incident relates to the belief
            if any(word in symptom or word in actual_cause
                   for word in belief_lower.split() if len(word) > 3):
                failures.append({
                    "type": "incident",
                    "summary": data.get("symptom", "")[:80],
                    "lesson": data.get("prevention", ""),
                })

        # Check reversed decisions
        elif art_type == "decision":
            outcome = data.get("outcome", {})
            if outcome.get("status") == "reversed":
                decision_text = data.get("decision", "").lower()
                if any(word in decision_text
                       for word in belief_lower.split() if len(word) > 3):
                    failures.append({
                        "type": "reversed_decision",
                        "summary": data.get("decision", "")[:80],
                        "reason": outcome.get("notes", "Unknown"),
                    })

    return failures


def find_assumption_gaps(
    belief: str,
    artifacts: List[Dict]
) -> List[str]:
    """Identify unstated assumptions in the belief."""

    gaps = []

    # Common assumption patterns
    assumption_triggers = [
        ("always", "What if this isn't always true?"),
        ("never", "Are there exceptions?"),
        ("should", "Says who? What's the basis?"),
        ("must", "Is this actually required?"),
        ("best", "Best for what criteria?"),
        ("only", "Are there other options?"),
        ("simple", "What hidden complexity exists?"),
        ("easy", "Easy for whom?"),
        ("fast", "Fast compared to what?"),
        ("better", "Better by what measure?"),
    ]

    belief_lower = belief.lower()

    for trigger, question in assumption_triggers:
        if trigger in belief_lower:
            gaps.append(f"**'{trigger}'** detected: {question}")

    # Check for missing context
    if "because" not in belief_lower and "since" not in belief_lower:
        gaps.append("**No rationale stated**: Why do you believe this?")

    if "when" not in belief_lower and "if" not in belief_lower:
        gaps.append("**No conditions stated**: When does this apply?")

    return gaps


def format_challenge_report(
    belief: str,
    contradictions: List[Dict],
    failures: List[Dict],
    gaps: List[str]
) -> str:
    """Format the challenge report."""

    lines = []
    lines.append("# Challenge Report")
    lines.append("")
    lines.append(f"**Belief under examination**: {belief}")
    lines.append("")

    # Assumption gaps
    if gaps:
        lines.append("## Unstated Assumptions")
        lines.append("")
        for gap in gaps:
            lines.append(f"- {gap}")
        lines.append("")

    # Past failures
    if failures:
        lines.append("## Relevant Past Failures")
        lines.append("")
        for failure in failures[:5]:
            if failure["type"] == "incident":
                lines.append(f"- **Incident**: {failure['summary']}")
                if failure.get("lesson"):
                    lines.append(f"  - Lesson: {failure['lesson'][:60]}...")
            elif failure["type"] == "reversed_decision":
                lines.append(f"- **Reversed Decision**: {failure['summary']}")
                lines.append(f"  - Why reversed: {failure['reason'][:60]}...")
        lines.append("")

    # Contradicting evidence
    if contradictions:
        lines.append("## Potentially Contradicting Evidence")
        lines.append("")
        for contra in contradictions[:5]:
            art = contra["artifact"]
            data = art.get("data", art)
            text = (data.get("claim", "") or
                    data.get("decision", "") or
                    data.get("symptom", ""))[:80]
            lines.append(f"- {text}...")
        lines.append("")

    # Summary
    challenge_strength = "weak"
    if len(gaps) >= 2 or len(failures) >= 1:
        challenge_strength = "moderate"
    if len(failures) >= 2 or (len(gaps) >= 2 and len(contradictions) >= 2):
        challenge_strength = "strong"

    lines.append("---")
    lines.append(f"**Challenge strength**: {challenge_strength}")
    lines.append("")

    if challenge_strength == "strong":
        lines.append("*This belief may need revisiting. Consider the evidence above.*")
    elif challenge_strength == "moderate":
        lines.append("*Some concerns identified. Worth a second look.*")
    else:
        lines.append("*No strong counterevidence found. Belief appears reasonable.*")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            belief: str - The belief or decision to challenge
            domain: str (optional) - Focus on a specific domain
        }
        tools: {
            query_memory: callable
            semantic_search: callable
        }
        context: {run_id, timeout}

    Returns:
        {
            success: bool,
            report: str,
            challenge_strength: str,
            evidence: dict,
        }
    """
    belief = args.get("belief", "")
    domain = args.get("domain")

    if not belief:
        return {"success": False, "error": "Belief/decision to challenge is required"}

    query_memory = tools.get("query_memory")
    semantic_search = tools.get("semantic_search")

    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    # Gather artifacts
    all_artifacts = []

    for art_type in ["decision", "incident_rca", "fact"]:
        try:
            results = query_memory(artifact_type=art_type, limit=DEFAULT_CONFIG["max_artifacts"])
            if isinstance(results, list):
                for r in results:
                    r["artifact_type"] = art_type
                all_artifacts.extend(results)
        except Exception:
            continue

    # Find contradictions via semantic search
    contradictions = []
    if semantic_search:
        contradictions = find_contradictions(belief, all_artifacts, semantic_search)

    # Find past failures
    failures = find_past_failures(belief, all_artifacts)

    # Identify assumption gaps
    gaps = find_assumption_gaps(belief, all_artifacts)

    # Format report
    report = format_challenge_report(belief, contradictions, failures, gaps)

    # Determine challenge strength
    challenge_strength = "weak"
    if len(gaps) >= 2 or len(failures) >= 1:
        challenge_strength = "moderate"
    if len(failures) >= 2 or (len(gaps) >= 2 and len(contradictions) >= 2):
        challenge_strength = "strong"

    return {
        "success": True,
        "report": report,
        "challenge_strength": challenge_strength,
        "evidence": {
            "assumption_gaps": len(gaps),
            "past_failures": len(failures),
            "contradictions": len(contradictions),
        },
        "total_artifacts_scanned": len(all_artifacts),
    }


# CLI mode
if __name__ == "__main__":
    print("challenge Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Purpose: Devil's advocate mode - pressure tests beliefs")
    print("against your own documented experience and biases.")
    print()
    print("Usage:")
    print("  Run via MCP: duro_run_skill('challenge', {belief: '...'})")
    print()
    print("Example beliefs to challenge:")
    print("  - We should always use TypeScript")
    print("  - Microservices are better than monoliths")
    print("  - Tests are never worth skipping")
    print("  - This refactor will be simple")
