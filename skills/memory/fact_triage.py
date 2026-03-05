"""
Skill: fact_triage
Description: Batch-triage unverified facts by verification priority
Version: 1.0.0
Tier: tested
"""

import time
from collections import Counter
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta


SKILL_META = {
    "name": "fact_triage",
    "description": "Batch-triage unverified facts by verification priority",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Reflective layer roadmap (Greg Eisenberg x Internet Vin podcast)",
    "validated": "2026-02-25",
    "triggers": ["triage", "verify facts", "fact priority", "unverified", "verification queue"],
    "keywords": [
        "triage", "fact", "verify", "unverified", "priority", "blast radius",
        "confidence", "mismatch", "quick win", "maintenance", "trust",
        "critical", "queue", "batch", "verification"
    ],
    "phase": "4.0",
}

DEFAULT_CONFIG = {
    "limit": 50,
    "sort_by": "priority",
    "include_low": False,
    "max_facts_scan": 500,
}

REQUIRES = ["query_memory"]

DEFAULT_TIMEOUT = 60

CRITICAL_TAGS = {
    "security", "auth", "authentication", "authorization", "encryption",
    "credentials", "secrets", "api-key", "token", "oauth", "ssl", "tls",
    "production", "prod", "deploy", "deployment", "live", "release",
    "architecture", "infrastructure", "database", "migration", "schema",
    "payment", "billing", "stripe", "financial", "money",
    "data-loss", "backup", "recovery", "disaster",
}

HIGH_TAGS = {
    "api", "endpoint", "server", "hosting", "dns", "domain",
    "performance", "scaling", "cache", "cdn", "load-balancer",
    "ci", "cd", "pipeline", "docker", "kubernetes", "k8s",
    "config", "configuration", "environment", "env",
    "dependency", "version", "upgrade", "breaking-change",
    "user-facing", "ux", "onboarding", "workflow",
}

MEDIUM_TAGS = {
    "design", "ui", "component", "layout", "typography", "color",
    "process", "methodology", "approach", "strategy",
    "tool", "tooling", "editor", "ide", "cli",
    "testing", "test", "coverage", "quality",
    "documentation", "docs", "readme",
}


@dataclass
class TriagedFact:
    """A fact scored and categorized for verification priority."""
    fact_id: str
    claim: str
    tags: List[str]
    confidence: float
    verification_state: str
    created_at: str
    reinforcement_count: int
    has_sources: bool
    source_urls: List[str]

    blast_radius_score: float = 0.0
    age_score: float = 0.0
    usage_score: float = 0.0
    source_ease_score: float = 0.0
    confidence_mismatch_score: float = 0.0

    priority_score: float = 0.0
    tier: str = "low"
    reason: str = ""
    is_quick_win: bool = False


def parse_date(timestamp: str) -> datetime:
    """Parse a timestamp string into a datetime object."""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(timestamp[:26], fmt)
        except (ValueError, TypeError):
            continue
    return datetime.min


def extract_claim(fact: Dict) -> str:
    """Extract the claim text from a fact artifact."""
    if "data" in fact:
        data = fact["data"]
        claim = data.get("claim", "") or data.get("message", "") or data.get("title", "")
        if claim:
            return str(claim)
    for key in ("claim", "title", "message"):
        val = fact.get(key, "")
        if val:
            return str(val)
    return ""


def extract_tags(fact: Dict) -> List[str]:
    """Extract tags from a fact artifact."""
    return fact.get("tags", []) or []


def extract_confidence(fact: Dict) -> float:
    """Extract confidence score from a fact artifact."""
    conf = fact.get("confidence", None)
    if conf is not None:
        try:
            return float(conf)
        except (ValueError, TypeError):
            pass
    if "data" in fact:
        conf = fact["data"].get("confidence", None)
        if conf is not None:
            try:
                return float(conf)
            except (ValueError, TypeError):
                pass
    return 0.5


def extract_verification_state(fact: Dict) -> str:
    """Extract verification state from a fact artifact."""
    state = fact.get("verification_state", "")
    if not state and "data" in fact:
        state = fact["data"].get("verification_state", "")
    return state or "unverified"


def extract_timestamp(fact: Dict) -> str:
    """Extract created_at timestamp from a fact artifact."""
    return fact.get("created_at", "") or fact.get("timestamp", "") or ""


def extract_reinforcement_count(fact: Dict) -> int:
    """Extract reinforcement/reference count from a fact artifact."""
    count = fact.get("reinforcement_count", None)
    if count is not None:
        try:
            return int(count)
        except (ValueError, TypeError):
            pass
    if "data" in fact:
        count = fact["data"].get("reinforcement_count", None)
        if count is None:
            count = fact["data"].get("reinforcements", None)
        if count is not None:
            try:
                return int(count)
            except (ValueError, TypeError):
                pass
    return 0


def extract_source_urls(fact: Dict) -> List[str]:
    """Extract source URLs from a fact artifact."""
    urls = fact.get("source_urls", [])
    if not urls and "data" in fact:
        urls = fact["data"].get("source_urls", [])
    if not urls and "data" in fact:
        urls = fact["data"].get("sources", [])
    return urls if isinstance(urls, list) else []


def score_blast_radius(tags: List[str]) -> Tuple[float, str]:
    """Score the blast radius of a fact based on its tags."""
    tag_set = {t.lower().strip() for t in tags}

    critical_hits = tag_set & CRITICAL_TAGS
    high_hits = tag_set & HIGH_TAGS
    medium_hits = tag_set & MEDIUM_TAGS

    if critical_hits:
        reason = f"touches critical domain: {', '.join(sorted(critical_hits)[:3])}"
        return min(1.0, 0.7 + len(critical_hits) * 0.1), reason
    elif high_hits:
        reason = f"touches high-impact domain: {', '.join(sorted(high_hits)[:3])}"
        return min(0.7, 0.4 + len(high_hits) * 0.1), reason
    elif medium_hits:
        reason = f"touches: {', '.join(sorted(medium_hits)[:3])}"
        return min(0.4, 0.15 + len(medium_hits) * 0.05), reason
    else:
        return 0.05, "no high-impact tags"


def score_age(created_at: str, now: datetime) -> Tuple[float, str]:
    """Score based on age. Older unverified facts are higher priority."""
    dt = parse_date(created_at)
    if dt == datetime.min:
        return 0.3, "unknown age (assumed moderate)"

    age_days = (now - dt).days

    if age_days > 90:
        return 1.0, f"{age_days} days old (>90 days, long-trusted)"
    elif age_days > 30:
        return 0.7, f"{age_days} days old (>30 days)"
    elif age_days > 14:
        return 0.4, f"{age_days} days old (>2 weeks)"
    elif age_days > 7:
        return 0.2, f"{age_days} days old (>1 week)"
    else:
        return 0.05, f"{age_days} days old (recent)"


def score_usage(reinforcement_count: int) -> Tuple[float, str]:
    """Score based on how often the fact has been reinforced/referenced."""
    if reinforcement_count >= 10:
        return 1.0, f"heavily referenced ({reinforcement_count} reinforcements)"
    elif reinforcement_count >= 5:
        return 0.7, f"frequently referenced ({reinforcement_count} reinforcements)"
    elif reinforcement_count >= 2:
        return 0.4, f"referenced {reinforcement_count} times"
    elif reinforcement_count == 1:
        return 0.15, "referenced once"
    else:
        return 0.0, "never referenced"


def score_source_ease(source_urls: List[str]) -> Tuple[float, bool, str]:
    """Score how easy the fact is to verify based on available sources."""
    if source_urls:
        return 0.0, True, f"has {len(source_urls)} source URL(s) - quick win"
    return 0.0, False, "no source URLs"


def score_confidence_mismatch(confidence: float) -> Tuple[float, str]:
    """Score the danger of a confidence mismatch."""
    if confidence >= 0.9:
        return 1.0, f"very high confidence ({confidence:.0%}) but unverified - dangerous trust"
    elif confidence >= 0.7:
        return 0.7, f"high confidence ({confidence:.0%}) but unverified"
    elif confidence >= 0.5:
        return 0.3, f"moderate confidence ({confidence:.0%})"
    else:
        return 0.05, f"low confidence ({confidence:.0%}) - already distrusted"


def compute_priority_score(fact: TriagedFact) -> float:
    """Compute the aggregate priority score from individual dimension scores."""
    score = (
        fact.blast_radius_score * 0.30 +
        fact.confidence_mismatch_score * 0.25 +
        fact.age_score * 0.20 +
        fact.usage_score * 0.20 +
        (0.05 if fact.is_quick_win else 0.0)
    )
    return round(min(1.0, score), 3)


def assign_tier(score: float) -> str:
    """Assign a triage tier based on priority score."""
    if score >= 0.65:
        return "critical"
    elif score >= 0.45:
        return "high"
    elif score >= 0.25:
        return "medium"
    else:
        return "low"


def build_reason(fact: TriagedFact) -> str:
    """Build a human-readable reason string from the top contributing factors."""
    factors = []

    contributions = [
        (fact.blast_radius_score * 0.30, "blast_radius"),
        (fact.confidence_mismatch_score * 0.25, "confidence_mismatch"),
        (fact.age_score * 0.20, "age"),
        (fact.usage_score * 0.20, "usage"),
    ]
    contributions.sort(key=lambda x: -x[0])

    for contrib, name in contributions[:3]:
        if contrib < 0.02:
            continue
        if name == "blast_radius":
            tag_set = {t.lower().strip() for t in fact.tags}
            hits = tag_set & (CRITICAL_TAGS | HIGH_TAGS)
            if hits:
                factors.append(f"blast radius ({', '.join(sorted(hits)[:2])})")
            else:
                factors.append("blast radius")
        elif name == "confidence_mismatch":
            factors.append(f"confidence {fact.confidence:.0%} but unverified")
        elif name == "age":
            dt = parse_date(fact.created_at)
            if dt != datetime.min:
                days = (datetime.utcnow() - dt).days
                factors.append(f"{days}d old")
            else:
                factors.append("unknown age")
        elif name == "usage":
            if fact.reinforcement_count > 0:
                factors.append(f"referenced {fact.reinforcement_count}x")

    if fact.is_quick_win:
        factors.append("quick win (has sources)")

    return "; ".join(factors) if factors else "low overall risk"


def query_facts(query_memory, limit: int = 500) -> List[Dict]:
    """Query fact artifacts from the knowledge base."""
    try:
        result = query_memory(artifact_type="fact", limit=limit)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return result.get("results", result.get("artifacts", []))
    except Exception:
        pass
    return []


def format_report(
    triaged: List[TriagedFact],
    stats: Dict[str, int],
    total_facts: int,
    include_low: bool,
) -> str:
    """Format the triage report as markdown."""
    lines = []
    lines.append("## Fact Triage Report")
    lines.append("")
    lines.append(f"**Total facts:** {total_facts}")
    lines.append(f"**Unverified:** {stats['total_unverified']}")
    lines.append(f"**Verified/skipped:** {total_facts - stats['total_unverified']}")
    lines.append("")

    lines.append("### Tier Breakdown")
    lines.append("")
    lines.append(f"| Tier | Count | Action |")
    lines.append(f"|------|-------|--------|")
    lines.append(f"| Critical | {stats['critical']} | Verify now |")
    lines.append(f"| High | {stats['high']} | Verify this week |")
    lines.append(f"| Medium | {stats['medium']} | Verify when convenient |")
    lines.append(f"| Low | {stats['low']} | Probably fine |")
    lines.append(f"| **Quick Wins** | {stats['quick_wins']} | Has sources - easy to check |")
    lines.append("")

    verify_first = [f for f in triaged if f.tier in ("critical", "high")]
    if not verify_first:
        verify_first = [f for f in triaged if f.tier == "medium"]

    top_n = verify_first[:10]
    if top_n:
        lines.append("### Top Facts to Verify")
        lines.append("")
        for i, fact in enumerate(top_n, 1):
            claim_preview = fact.claim[:120]
            if len(fact.claim) > 120:
                claim_preview += "..."
            qw_marker = " [QUICK WIN]" if fact.is_quick_win else ""
            lines.append(f"**{i}. [{fact.tier.upper()}] (score: {fact.priority_score:.0%}){qw_marker}**")
            lines.append(f"   `{fact.fact_id}`")
            lines.append(f"   {claim_preview}")
            lines.append(f"   Confidence: {fact.confidence:.0%} | Reason: {fact.reason}")
            lines.append("")

    quick_wins = [f for f in triaged if f.is_quick_win]
    if quick_wins:
        lines.append("### Quick Wins (have source URLs)")
        lines.append("")
        for fact in quick_wins[:5]:
            claim_preview = fact.claim[:100]
            lines.append(f"- [{fact.tier}] `{fact.fact_id}`: {claim_preview}")
            urls_preview = ", ".join(fact.source_urls[:2])
            if len(fact.source_urls) > 2:
                urls_preview += f" (+{len(fact.source_urls) - 2} more)"
            lines.append(f"  Sources: {urls_preview}")
        lines.append("")

    return "\n".join(lines)


def run(params: dict, tools: dict, context: dict = None) -> dict:
    """Main skill execution function."""
    start_time = time.time()

    limit = params.get("limit", DEFAULT_CONFIG["limit"])
    sort_by = params.get("sort_by", DEFAULT_CONFIG["sort_by"])
    include_low = params.get("include_low", DEFAULT_CONFIG["include_low"])
    max_scan = params.get("max_facts_scan", DEFAULT_CONFIG["max_facts_scan"])

    query_memory = tools.get("query_memory")
    if not query_memory:
        return {"report": "ERROR: query_memory tool is required", "stats": {}, "triage": []}

    all_facts = query_facts(query_memory, limit=max_scan)

    if not all_facts:
        return {
            "report": "No facts found in the knowledge base.",
            "stats": {
                "total_unverified": 0, "critical": 0, "high": 0,
                "medium": 0, "low": 0, "quick_wins": 0,
            },
            "triage": [],
        }

    total_facts = len(all_facts)
    now = datetime.utcnow()

    unverified_facts = []
    for fact in all_facts:
        state = extract_verification_state(fact)
        if state in ("verified", "confirmed", "refuted"):
            continue
        unverified_facts.append(fact)

    if not unverified_facts:
        return {
            "report": f"All {total_facts} facts are verified. Nothing to triage.",
            "stats": {
                "total_unverified": 0, "critical": 0, "high": 0,
                "medium": 0, "low": 0, "quick_wins": 0,
            },
            "triage": [],
        }

    triaged: List[TriagedFact] = []

    for fact in unverified_facts:
        fact_id = fact.get("id", "unknown")
        claim = extract_claim(fact)
        tags = extract_tags(fact)
        confidence = extract_confidence(fact)
        created_at = extract_timestamp(fact)
        reinforcement_count = extract_reinforcement_count(fact)
        source_urls = extract_source_urls(fact)
        has_sources = len(source_urls) > 0

        if not claim or len(claim.strip()) < 5:
            continue

        tf = TriagedFact(
            fact_id=fact_id,
            claim=claim,
            tags=tags,
            confidence=confidence,
            verification_state=extract_verification_state(fact),
            created_at=created_at,
            reinforcement_count=reinforcement_count,
            has_sources=has_sources,
            source_urls=source_urls,
        )

        tf.blast_radius_score, _ = score_blast_radius(tags)
        tf.age_score, _ = score_age(created_at, now)
        tf.usage_score, _ = score_usage(reinforcement_count)
        _, tf.is_quick_win, _ = score_source_ease(source_urls)
        tf.confidence_mismatch_score, _ = score_confidence_mismatch(confidence)

        tf.priority_score = compute_priority_score(tf)
        tf.tier = assign_tier(tf.priority_score)
        tf.reason = build_reason(tf)

        triaged.append(tf)

    if sort_by == "age":
        triaged.sort(key=lambda f: parse_date(f.created_at))
    elif sort_by == "confidence":
        triaged.sort(key=lambda f: -f.confidence)
    else:
        triaged.sort(key=lambda f: -f.priority_score)

    tier_counts = Counter(f.tier for f in triaged)
    quick_win_count = sum(1 for f in triaged if f.is_quick_win)

    stats = {
        "total_unverified": len(triaged),
        "critical": tier_counts.get("critical", 0),
        "high": tier_counts.get("high", 0),
        "medium": tier_counts.get("medium", 0),
        "low": tier_counts.get("low", 0),
        "quick_wins": quick_win_count,
    }

    if not include_low:
        triaged_output = [f for f in triaged if f.tier != "low"]
    else:
        triaged_output = triaged

    triaged_output = triaged_output[:limit]

    report = format_report(triaged_output, stats, total_facts, include_low)

    triage_list = [
        {
            "fact_id": f.fact_id,
            "claim": f.claim[:300],
            "tier": f.tier,
            "score": f.priority_score,
            "reason": f.reason,
            "confidence": f.confidence,
            "is_quick_win": f.is_quick_win,
            "reinforcement_count": f.reinforcement_count,
            "tags": f.tags[:10],
        }
        for f in triaged_output
    ]

    elapsed = round(time.time() - start_time, 2)

    return {
        "report": report,
        "stats": stats,
        "triage": triage_list,
        "total_facts": total_facts,
        "elapsed_seconds": elapsed,
    }


if __name__ == "__main__":
    print("fact_triage Skill v1.0.0")
    print("Triage tiers: critical, high, medium, low")
    print("Priority weights: blast_radius 30%, confidence_mismatch 25%, age 20%, usage 20%, quick_win 5%")
