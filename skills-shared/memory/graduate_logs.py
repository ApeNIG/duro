"""
Skill: graduate_logs
Description: Mine log artifacts for latent facts, decisions, and insights worth promoting
Version: 1.0.0
Tier: tested

Inspired by the "Graduate" pattern from the Obsidian + Claude Code workflow:
Daily logs accumulate ideas, insights, and learnings that never get promoted
to permanent, searchable artifacts. This skill scans log artifacts in the
Duro database, classifies candidates by type and graduation potential,
cross-references against existing artifacts to avoid duplicates, and
presents ranked candidates for user approval.

Unlike promote_learnings.py (which parses markdown files for tagged learnings),
this skill mines the full artifact database using semantic analysis to find
latent signal that was never explicitly tagged.

Flow:
1. Query recent log artifacts from database
2. Classify each log's content into candidate types (fact, decision, insight)
3. Score candidates by graduation potential (specificity, novelty, actionability)
4. Cross-reference against existing facts/decisions to detect duplicates
5. Present ranked candidates grouped by type
6. Optionally promote approved candidates with provenance links

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import re
import hashlib
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


# Skill metadata
SKILL_META = {
    "name": "graduate_logs",
    "description": "Mine log artifacts for latent facts, decisions, and insights worth promoting",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Obsidian + Claude Code 'Graduate' pattern (Greg Eisenberg x Internet Vin podcast)",
    "validated": "2026-02-24",
    "triggers": ["graduate", "promote", "mine logs", "extract insights", "log review"],
    "keywords": [
        "graduate", "promote", "logs", "insights", "facts", "decisions",
        "extract", "mine", "review", "latent", "patterns", "reflection"
    ],
    "phase": "4.0",
}

# Default configuration
DEFAULT_CONFIG = {
    "days_back": 7,
    "max_logs": 200,
    "min_message_length": 40,
    "max_candidates": 20,
    "duplicate_threshold": 0.7,
    "min_graduation_score": 0.25,
}

# Required capabilities
REQUIRES = ["query_memory", "semantic_search"]

# Default timeout
DEFAULT_TIMEOUT = 60


class CandidateType(Enum):
    """Types of artifacts a log can graduate into."""
    FACT = "fact"
    DECISION = "decision"
    INSIGHT = "insight"  # Stored as fact with insight tag
    PATTERN = "pattern"  # Stored as fact with pattern tag


@dataclass
class GraduationCandidate:
    """A log artifact identified as worth promoting."""
    log_id: str
    message: str
    event_type: str
    tags: List[str]
    created_at: str
    candidate_type: CandidateType
    graduation_score: float
    suggested_claim: str
    suggested_tags: List[str]
    suggested_confidence: float
    reasoning: str
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None

    @property
    def content_hash(self) -> str:
        return hashlib.md5(self.message.encode()).hexdigest()[:12]


# --- Classification Heuristics ---

# Signal words that indicate factual claims
FACT_SIGNALS = [
    r'\bis\b.*\bnot\b', r'\bdoesn\'t\b', r'\bcan\'t\b', r'\brequires?\b',
    r'\bneeds?\b', r'\bworks?\b', r'\bfails?\b', r'\bcauses?\b',
    r'\bprevents?\b', r'\benables?\b', r'\bsupports?\b',
    r'\bmust\b', r'\balways\b', r'\bnever\b',
    r'\bdefault\b', r'\bformat\b', r'\bversion\b', r'\bpath\b',
    r'\bconfig\b', r'\bport\b', r'\bAPI\b', r'\bendpoint\b',
]

# Signal words that indicate decisions
DECISION_SIGNALS = [
    r'\bchose\b', r'\bdecided\b', r'\bselected\b', r'\bpicked\b',
    r'\bswitched\b', r'\bmigrat', r'\badopted\b', r'\bprefer\b',
    r'\binstead of\b', r'\brather than\b', r'\bover\b.*\bbecause\b',
    r'\bgoing with\b', r'\bwent with\b', r'\busing\b.*\binstead\b',
    r'\bapproach\b', r'\bstrategy\b', r'\bpattern\b.*\bbest\b',
]

# Signal words that indicate insights / design thinking
INSIGHT_SIGNALS = [
    r'\binsight\b', r'\brealization\b', r'\bdiscovered?\b',
    r'\blearned?\b', r'\bturns? out\b', r'\binteresting\b',
    r'\bsurprising\b', r'\bcounter-?intuitive\b', r'\bkey\b.*\btakeaway\b',
    r'\bfundamental\b', r'\bprinciple\b', r'\bphilosoph',
    r'\bhierarchy\b', r'\bmetaphor\b', r'\bparadigm\b',
]

# Signal words that indicate recurring patterns
PATTERN_SIGNALS = [
    r'\bpattern\b', r'\brecurring\b', r'\bconsistently\b',
    r'\bevery time\b', r'\balways happens\b', r'\bcommon\b.*\bissue\b',
    r'\banti-?pattern\b', r'\bbest practice\b', r'\brule of thumb\b',
    r'\btend to\b', r'\busually\b', r'\btypically\b',
]

# Low-value log indicators (these rarely graduate)
LOW_VALUE_SIGNALS = [
    r'^(pushed|committed|merged|deployed|created|deleted|updated)\s',
    r'\brevert', r'\bclean\s?up', r'\btest artifact',
    r'\breinforced?\b.*\bfacts?\b', r'\bbulk\b.*\bdelete\b',
    r'\bsync\b.*\b(script|remote|repo)\b',
]


def count_signal_matches(text: str, patterns: List[str]) -> int:
    """Count how many signal patterns match in the text."""
    text_lower = text.lower()
    return sum(1 for p in patterns if re.search(p, text_lower, re.IGNORECASE))


def classify_log(message: str, event_type: str, tags: List[str]) -> Tuple[CandidateType, float]:
    """
    Classify a log message into a candidate type with confidence.

    Returns (candidate_type, type_confidence) where type_confidence
    indicates how strongly the log matches that type.
    """
    fact_score = count_signal_matches(message, FACT_SIGNALS)
    decision_score = count_signal_matches(message, DECISION_SIGNALS)
    insight_score = count_signal_matches(message, INSIGHT_SIGNALS)
    pattern_score = count_signal_matches(message, PATTERN_SIGNALS)

    # Boost based on event_type
    if event_type == "learning":
        insight_score += 2
    elif event_type == "decision":
        decision_score += 3
    elif event_type == "task_complete":
        fact_score += 1

    # Boost based on tags
    tag_str = " ".join(tags).lower()
    if any(t in tag_str for t in ["design", "philosophy", "strategy"]):
        insight_score += 1
    if any(t in tag_str for t in ["technical", "infrastructure", "process"]):
        fact_score += 1

    scores = {
        CandidateType.FACT: fact_score,
        CandidateType.DECISION: decision_score,
        CandidateType.INSIGHT: insight_score,
        CandidateType.PATTERN: pattern_score,
    }

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    total = sum(scores.values()) or 1

    # Normalize to 0-1 confidence
    type_confidence = min(1.0, best_score / max(total, 1))

    # Default to insight if no strong signal
    if best_score == 0:
        best_type = CandidateType.INSIGHT
        type_confidence = 0.3

    return best_type, round(type_confidence, 2)


def calculate_graduation_score(
    message: str,
    event_type: str,
    tags: List[str],
    type_confidence: float
) -> float:
    """
    Calculate how worthy a log is of graduating to a permanent artifact.

    Factors:
    - Specificity: Contains concrete details (names, numbers, paths, versions)
    - Actionability: Contains implications for future work
    - Novelty signals: Uses language suggesting new discovery
    - Length: Longer messages tend to have more substance
    - Low-value penalty: Routine operations score lower
    """
    score = 0.0

    # --- Specificity (0-0.3) ---
    specificity = 0.0
    # Contains paths, versions, numbers
    if re.search(r'[/\\][\w.-]+\.\w+', message):  # File paths
        specificity += 0.1
    if re.search(r'v?\d+\.\d+', message):  # Version numbers (e.g., v1.2)
        specificity += 0.05
    if re.search(r'\bV\d+\b', message):  # Design version markers (e.g., V2, V8)
        specificity += 0.05
    if re.search(r'\b\d{3,}\b', message):  # Large numbers (ports, counts)
        specificity += 0.05
    # Contains proper nouns / specific names (capitalized words mid-sentence)
    proper_nouns = re.findall(r'(?<!\. )[A-Z][a-z]+(?:[-_][A-Z][a-z]+)*', message)
    specificity += min(0.1, len(proper_nouns) * 0.02)
    score += min(0.3, specificity)

    # --- Actionability (0-0.25) ---
    actionability = 0.0
    action_words = [
        r'\bshould\b', r'\bneed to\b', r'\bmust\b', r'\bconsider\b',
        r'\bbetter\b.*\bto\b', r'\brecommend', r'\bnext step\b',
        r'\btodo\b', r'\bfollow.?up\b',
    ]
    actionability = min(0.25, count_signal_matches(message, action_words) * 0.08)
    score += actionability

    # --- Novelty (0-0.2) ---
    novelty = 0.0
    novelty_words = [
        r'\bfirst time\b', r'\bnew\b.*\bapproach\b', r'\bdiscovered\b',
        r'\brealized\b', r'\bturns out\b', r'\bsurprising',
        r'\bbreakthrough\b', r'\bgame.?chang',
    ]
    novelty = min(0.2, count_signal_matches(message, novelty_words) * 0.07)
    score += novelty

    # --- Length bonus (0-0.15) ---
    word_count = len(message.split())
    if word_count >= 30:
        score += 0.15
    elif word_count >= 20:
        score += 0.10
    elif word_count >= 10:
        score += 0.05

    # --- Type confidence bonus (0-0.1) ---
    score += type_confidence * 0.1

    # --- Low-value penalty (-0.3) ---
    low_value = count_signal_matches(message, LOW_VALUE_SIGNALS)
    if low_value > 0:
        score -= 0.3

    # --- Event type bonus ---
    if event_type == "learning":
        score += 0.12  # Learnings are already self-identified as valuable
    elif event_type == "decision":
        score += 0.05

    return round(max(0.0, min(1.0, score)), 2)


def extract_suggested_claim(message: str, candidate_type: CandidateType) -> str:
    """
    Clean up a log message into a concise claim suitable for a fact or decision.
    Removes meta-prefixes, trims to essential content.
    """
    claim = message.strip()

    # Remove common prefixes from log messages
    prefixes_to_strip = [
        r'^(?:Learned|Discovered|Realized|Found out|Noticed|Insight):\s*',
        r'^(?:Session note|Note|Log|Update|Status):\s*',
        r'^(?:Task complete|Done|Finished|Completed):\s*',
    ]
    for prefix in prefixes_to_strip:
        claim = re.sub(prefix, '', claim, flags=re.IGNORECASE)

    # For decisions, try to extract the core choice
    if candidate_type == CandidateType.DECISION:
        # Look for "chose X over Y" or "going with X" patterns
        choice_match = re.search(
            r'(?:chose|selected|going with|went with|using)\s+(.+?)(?:\s+(?:over|instead of|rather than)\s+|$)',
            claim, re.IGNORECASE
        )
        if choice_match:
            # Keep the full message but it's good context
            pass

    # Cap length at ~300 chars for readability
    if len(claim) > 300:
        # Try to break at sentence boundary
        sentences = claim[:320].split('. ')
        if len(sentences) > 1:
            claim = '. '.join(sentences[:-1]) + '.'
        else:
            claim = claim[:297] + '...'

    return claim


def generate_suggested_tags(
    message: str,
    existing_tags: List[str],
    candidate_type: CandidateType
) -> List[str]:
    """Generate suggested tags for the graduated artifact."""
    tags = list(existing_tags)  # Keep original tags

    # Add type tag
    tags.append(f"graduated-{candidate_type.value}")
    tags.append("auto-graduated")

    # Domain detection
    msg_lower = message.lower()
    domain_tags = {
        "design": ["design", "ui", "ux", "layout", "typography", "color", "visual"],
        "infrastructure": ["server", "droplet", "deploy", "docker", "sync", "remote"],
        "duro": ["duro", "mcp", "artifact", "skill", "memory", "fact"],
        "process": ["workflow", "pipeline", "approach", "methodology"],
        "content": ["linkedin", "carousel", "post", "copy", "content"],
    }

    for domain, keywords in domain_tags.items():
        if any(kw in msg_lower for kw in keywords):
            if domain not in tags:
                tags.append(domain)

    return list(set(tags))  # Deduplicate


def suggest_confidence(candidate_type: CandidateType, graduation_score: float) -> float:
    """Suggest a confidence level for the graduated artifact."""
    base = {
        CandidateType.FACT: 0.7,       # Facts from logs are experiential
        CandidateType.DECISION: 0.8,    # Decisions were actually made
        CandidateType.INSIGHT: 0.6,     # Insights are subjective
        CandidateType.PATTERN: 0.5,     # Patterns need more data to confirm
    }
    # Adjust by graduation score
    confidence = base[candidate_type] + (graduation_score * 0.15)
    return round(min(0.9, confidence), 2)


def check_duplicate(
    candidate: GraduationCandidate,
    existing_artifacts: List[Dict],
    threshold: float = 0.7
) -> Tuple[bool, Optional[str]]:
    """
    Check if a candidate is a duplicate of an existing artifact.

    Uses a hybrid approach:
    - Jaccard similarity (symmetric overlap)
    - Containment (what % of existing words appear in candidate)

    Containment catches cases where a longer log message contains
    the essence of an existing shorter fact.
    """
    candidate_words = set(candidate.message.lower().split())
    if not candidate_words:
        return False, None

    for artifact in existing_artifacts:
        # Check claim field (facts) or title/message (decisions)
        existing_text = (
            artifact.get("data", {}).get("claim", "") or
            artifact.get("data", {}).get("message", "") or
            artifact.get("data", {}).get("title", "") or
            ""
        )
        if not existing_text:
            continue

        existing_words = set(existing_text.lower().split())
        if not existing_words:
            continue

        intersection = len(candidate_words & existing_words)
        union = len(candidate_words | existing_words)

        # Jaccard similarity (symmetric)
        jaccard = intersection / union if union > 0 else 0

        # Containment: what % of the shorter text's words appear in the longer
        containment = intersection / min(len(candidate_words), len(existing_words))

        # Duplicate if either metric exceeds threshold
        if jaccard >= threshold or containment >= threshold:
            artifact_id = artifact.get("id", "unknown")
            return True, artifact_id

    return False, None


def format_report(
    candidates: List[GraduationCandidate],
    total_logs_scanned: int,
    days_back: int
) -> str:
    """Format the graduation report for display."""
    lines = []
    lines.append(f"## Graduate Logs Report")
    lines.append(f"")
    lines.append(f"**Scanned:** {total_logs_scanned} logs from last {days_back} days")

    # Separate by type
    by_type = {}
    for c in candidates:
        if c.is_duplicate:
            continue
        type_name = c.candidate_type.value
        if type_name not in by_type:
            by_type[type_name] = []
        by_type[type_name].append(c)

    duplicates = [c for c in candidates if c.is_duplicate]

    total_promotable = sum(len(v) for v in by_type.values())
    lines.append(f"**Candidates found:** {total_promotable} promotable, {len(duplicates)} duplicates skipped")
    lines.append("")

    type_order = ["fact", "decision", "insight", "pattern"]
    type_emoji = {"fact": "F", "decision": "D", "insight": "I", "pattern": "P"}

    for type_name in type_order:
        group = by_type.get(type_name, [])
        if not group:
            continue

        lines.append(f"### {type_name.title()}s ({len(group)})")
        lines.append("")

        for i, c in enumerate(group, 1):
            lines.append(f"**{i}. [{type_emoji[type_name]}:{c.graduation_score:.0%}]** {c.suggested_claim[:120]}")
            lines.append(f"   Source: `{c.log_id}` | Confidence: {c.suggested_confidence} | Tags: {', '.join(c.suggested_tags[:5])}")
            if c.reasoning:
                lines.append(f"   Why: {c.reasoning}")
            lines.append("")

    if duplicates:
        lines.append(f"### Skipped Duplicates ({len(duplicates)})")
        lines.append("")
        for c in duplicates:
            lines.append(f"- {c.message[:80]}... (dup of `{c.duplicate_of}`)")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            days_back: int (default 7) - How many days of logs to scan
            max_logs: int (default 200) - Maximum logs to process
            max_candidates: int (default 20) - Maximum candidates to return
            min_score: float (default 0.4) - Minimum graduation score
            types: List[str] (optional) - Filter to specific candidate types
            auto_promote: bool (default False) - Auto-promote candidates (respects strict separation by default)
            dry_run: bool (default True) - Preview mode, no changes
            include_duplicates: bool (default False) - Include duplicate candidates in results
        }
        tools: {
            query_memory: callable - Query artifacts from database
            semantic_search: callable - Search for similar artifacts
            store_fact: callable (optional) - Store graduated facts
            store_decision: callable (optional) - Store graduated decisions
        }
        context: {run_id, timeout}

    Returns:
        {
            success: bool,
            report: str - Formatted report
            candidates: List[dict] - Candidate details
            total_scanned: int
            promoted_count: int
            duplicate_count: int
            elapsed_seconds: float
        }
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    # Parse args with defaults
    days_back = args.get("days_back", DEFAULT_CONFIG["days_back"])
    max_logs = args.get("max_logs", DEFAULT_CONFIG["max_logs"])
    max_candidates = args.get("max_candidates", DEFAULT_CONFIG["max_candidates"])
    min_score = args.get("min_score", DEFAULT_CONFIG["min_graduation_score"])
    type_filter = args.get("types", None)
    auto_promote = args.get("auto_promote", False)
    dry_run = args.get("dry_run", True)
    include_duplicates = args.get("include_duplicates", False)
    min_message_length = DEFAULT_CONFIG["min_message_length"]

    query_memory = tools.get("query_memory")
    semantic_search = tools.get("semantic_search")
    store_fact = tools.get("store_fact")
    store_decision = tools.get("store_decision")

    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    # --- Step 1: Query recent logs ---
    from datetime import datetime, timedelta
    since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    try:
        logs_result = query_memory(
            artifact_type="log",
            since=since_date,
            limit=max_logs
        )
    except Exception as e:
        return {"success": False, "error": f"Failed to query logs: {str(e)}"}

    # Parse results - handle both list and dict formats
    logs = []
    if isinstance(logs_result, list):
        logs = logs_result
    elif isinstance(logs_result, dict):
        logs = logs_result.get("results", logs_result.get("artifacts", []))

    if not logs:
        return {
            "success": True,
            "report": f"No logs found in last {days_back} days.",
            "candidates": [],
            "total_scanned": 0,
            "promoted_count": 0,
            "duplicate_count": 0,
            "elapsed_seconds": round(time.time() - start_time, 2)
        }

    # --- Step 2: Fetch existing facts and decisions for dedup ---
    existing_artifacts = []
    try:
        facts = query_memory(artifact_type="fact", limit=500)
        if isinstance(facts, list):
            existing_artifacts.extend(facts)
        elif isinstance(facts, dict):
            existing_artifacts.extend(facts.get("results", []))
    except Exception:
        pass  # Continue without full dedup

    try:
        decisions = query_memory(artifact_type="decision", limit=200)
        if isinstance(decisions, list):
            existing_artifacts.extend(decisions)
        elif isinstance(decisions, dict):
            existing_artifacts.extend(decisions.get("results", []))
    except Exception:
        pass

    # --- Step 3: Classify and score each log ---
    candidates = []

    for log_entry in logs:
        # Check timeout
        if time.time() - start_time >= timeout:
            break

        # Extract fields - handle both flat and nested formats
        log_id = log_entry.get("id", "unknown")

        if "data" in log_entry:
            data = log_entry["data"]
            message = data.get("message", "")
            event_type = data.get("event_type", "unknown")
        else:
            message = log_entry.get("message", log_entry.get("title", ""))
            event_type = log_entry.get("event_type", "unknown")

        tags = log_entry.get("tags", [])
        created_at = log_entry.get("created_at", "")

        # Skip short/empty messages
        if not message or len(message.strip()) < min_message_length:
            continue

        # Classify
        candidate_type, type_confidence = classify_log(message, event_type, tags)

        # Apply type filter
        if type_filter and candidate_type.value not in type_filter:
            continue

        # Score
        graduation_score = calculate_graduation_score(
            message, event_type, tags, type_confidence
        )

        # Skip below threshold
        if graduation_score < min_score:
            continue

        # Build candidate
        suggested_claim = extract_suggested_claim(message, candidate_type)
        suggested_tags = generate_suggested_tags(message, tags, candidate_type)
        suggested_confidence = suggest_confidence(candidate_type, graduation_score)

        # Generate reasoning
        reasons = []
        if graduation_score >= 0.6:
            reasons.append("high specificity")
        if type_confidence >= 0.5:
            reasons.append(f"strong {candidate_type.value} signal")
        if event_type == "learning":
            reasons.append("self-identified as learning")
        if len(message.split()) >= 25:
            reasons.append("substantial content")
        reasoning = "; ".join(reasons) if reasons else "meets graduation threshold"

        candidate = GraduationCandidate(
            log_id=log_id,
            message=message,
            event_type=event_type,
            tags=tags,
            created_at=created_at,
            candidate_type=candidate_type,
            graduation_score=graduation_score,
            suggested_claim=suggested_claim,
            suggested_tags=suggested_tags,
            suggested_confidence=suggested_confidence,
            reasoning=reasoning,
        )

        # Check duplicates
        is_dup, dup_of = check_duplicate(candidate, existing_artifacts)
        candidate.is_duplicate = is_dup
        candidate.duplicate_of = dup_of

        candidates.append(candidate)

    # --- Step 4: Rank and trim ---
    candidates.sort(key=lambda c: (not c.is_duplicate, c.graduation_score), reverse=True)
    candidates = candidates[:max_candidates]

    # --- Step 5: Optional auto-promote ---
    promoted_count = 0
    errors = []
    if auto_promote and not dry_run:
        for candidate in candidates:
            if candidate.is_duplicate:
                continue

            if time.time() - start_time >= timeout:
                break

            try:
                promote_tags = candidate.suggested_tags + [f"source-log:{candidate.log_id}"]
                if candidate.candidate_type in (
                    CandidateType.FACT, CandidateType.INSIGHT, CandidateType.PATTERN
                ) and store_fact:
                    result = store_fact(
                        claim=candidate.suggested_claim,
                        confidence=candidate.suggested_confidence,
                        tags=promote_tags,
                        workflow="graduate_logs"
                    )
                    if result and result.get("success"):
                        promoted_count += 1
                    else:
                        errors.append(f"store_fact failed for {candidate.log_id}: {result}")
                elif candidate.candidate_type == CandidateType.DECISION and store_decision:
                    result = store_decision(
                        decision=candidate.suggested_claim[:120],
                        rationale=candidate.message,
                        tags=promote_tags,
                        workflow="graduate_logs"
                    )
                    if result and result.get("success"):
                        promoted_count += 1
                    else:
                        errors.append(f"store_decision failed for {candidate.log_id}: {result}")
            except Exception as e:
                errors.append(f"Exception promoting {candidate.log_id}: {str(e)}")
                continue

    # --- Step 6: Build report ---
    duplicate_count = sum(1 for c in candidates if c.is_duplicate)

    report = format_report(candidates, len(logs), days_back)

    # Serialize candidates for output
    candidates_output = []
    for c in candidates:
        if c.is_duplicate and not include_duplicates:
            continue
        candidates_output.append({
            "log_id": c.log_id,
            "type": c.candidate_type.value,
            "score": c.graduation_score,
            "claim": c.suggested_claim,
            "tags": c.suggested_tags,
            "confidence": c.suggested_confidence,
            "reasoning": c.reasoning,
            "is_duplicate": c.is_duplicate,
            "duplicate_of": c.duplicate_of,
            "created_at": c.created_at,
        })

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "report": report,
        "candidates": candidates_output,
        "total_scanned": len(logs),
        "candidate_count": len(candidates_output),
        "promoted_count": promoted_count,
        "duplicate_count": duplicate_count,
        "dry_run": dry_run,
        "errors": errors,
        "elapsed_seconds": elapsed,
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("graduate_logs Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Classification types:")
    for ct in CandidateType:
        print(f"  - {ct.value}")
    print()
    print("Scoring factors:")
    print("  - Specificity (0-0.3): paths, versions, proper nouns")
    print("  - Actionability (0-0.25): should, need to, must")
    print("  - Novelty (0-0.2): first time, discovered, turns out")
    print("  - Length (0-0.15): word count bonus")
    print("  - Type confidence (0-0.1): classification strength")
    print("  - Low-value penalty (-0.3): routine operations")
    print()
    print("Default config:")
    for k, v in DEFAULT_CONFIG.items():
        print(f"  {k}: {v}")
    print()
    print("Usage via MCP:")
    print("  result = run({'days_back': 7, 'dry_run': True}, tools, ctx)")
    print("  print(result['report'])")
