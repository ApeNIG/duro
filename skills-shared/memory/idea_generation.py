"""
Skill: idea_generation
Description: Comprehensive synthesis across all artifacts — generate actionable ideas
Version: 1.0.0
Tier: tested

The capstone reflective skill. Pulls signals from all other reflective skills'
outputs and the full artifact space to generate:
- Tools/skills to build (gaps in the skill library)
- Decisions to revisit (stale, contradicted, or unfollowed)
- Connections to explore (under-connected domains)
- Facts to verify (high-confidence but unverified)
- Patterns to name (recurring themes without structured artifacts)

This skill is a meta-synthesizer — it reads the state of the entire Duro
system and produces prioritized recommendations.

Flow:
1. Census: count artifacts by type, tags, recency, verification state
2. Gap analysis: what's missing or under-represented
3. Staleness scan: old facts, unfollowed decisions, low-reinforcement artifacts
4. Cross-reference: find domains with lots of logs but few facts/decisions
5. Generate ranked ideas with reasoning

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import time
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


SKILL_META = {
    "name": "idea_generation",
    "description": "Comprehensive synthesis across all artifacts — generate actionable ideas",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Reflective layer roadmap (Greg Eisenberg x Internet Vin podcast)",
    "validated": "2026-02-24",
    "triggers": ["ideas", "generate ideas", "what should I build", "suggestions", "synthesis"],
    "keywords": [
        "idea", "generate", "synthesis", "suggest", "build", "create",
        "revisit", "explore", "verify", "gap", "opportunity"
    ],
    "phase": "4.0",
}

DEFAULT_CONFIG = {
    "max_ideas": 15,
    "max_artifacts_per_type": 500,
    "stale_fact_days": 21,
    "min_tag_frequency": 3,
}

REQUIRES = ["query_memory", "semantic_search"]

DEFAULT_TIMEOUT = 60


class IdeaCategory:
    SKILL_TO_BUILD = "skill_to_build"
    DECISION_TO_REVISIT = "decision_to_revisit"
    FACT_TO_VERIFY = "fact_to_verify"
    CONNECTION_TO_EXPLORE = "connection_to_explore"
    PATTERN_TO_NAME = "pattern_to_name"
    KNOWLEDGE_GAP = "knowledge_gap"


@dataclass
class Idea:
    """A generated idea with reasoning."""
    category: str
    title: str
    reasoning: str
    priority: float             # 0-1, higher = more important
    evidence: List[str] = field(default_factory=list)  # Supporting artifact IDs or descriptions
    tags: List[str] = field(default_factory=list)


def extract_text(artifact: Dict) -> str:
    title = artifact.get("title", "")
    if title:
        return str(title)
    if "data" in artifact:
        data = artifact["data"]
        for key in ("message", "claim", "decision", "rationale", "title"):
            val = data.get(key, "")
            if val:
                return str(val)
    for key in ("message", "claim", "decision"):
        val = artifact.get(key, "")
        if val:
            return str(val)
    return ""


def extract_tags(artifact: Dict) -> List[str]:
    return artifact.get("tags", []) or []


def extract_timestamp(artifact: Dict) -> str:
    return artifact.get("created_at", "") or artifact.get("timestamp", "") or ""


def query_type(query_memory, artifact_type: str, limit: int = 500, **kwargs) -> List[Dict]:
    """Query artifacts of a given type, handling response formats."""
    try:
        result = query_memory(artifact_type=artifact_type, limit=limit, **kwargs)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return result.get("results", result.get("artifacts", []))
    except Exception:
        pass
    return []


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    max_ideas = args.get("max_ideas", DEFAULT_CONFIG["max_ideas"])
    max_per_type = args.get("max_artifacts_per_type", DEFAULT_CONFIG["max_artifacts_per_type"])
    stale_days = args.get("stale_fact_days", DEFAULT_CONFIG["stale_fact_days"])
    min_tag_freq = args.get("min_tag_frequency", DEFAULT_CONFIG["min_tag_frequency"])

    query_memory = tools.get("query_memory")
    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    from datetime import datetime, timedelta
    now = datetime.utcnow()
    stale_cutoff = (now - timedelta(days=stale_days)).strftime("%Y-%m-%d")

    ideas = []

    # ==============================
    # Phase 1: Census
    # ==============================
    type_counts = {}
    all_tags = Counter()
    tag_by_type = defaultdict(lambda: defaultdict(int))

    scan_types = ["fact", "decision", "log", "episode", "evaluation",
                   "incident_rca", "design_reference", "checklist_template"]

    artifacts_cache = {}  # type -> list

    for art_type in scan_types:
        if time.time() - start_time >= timeout * 0.4:
            break
        items = query_type(query_memory, art_type, limit=max_per_type)
        artifacts_cache[art_type] = items
        type_counts[art_type] = len(items)
        for item in items:
            for tag in extract_tags(item):
                tag_lower = tag.lower().strip()
                if tag_lower and len(tag_lower) > 1:
                    all_tags[tag_lower] += 1
                    tag_by_type[tag_lower][art_type] += 1

    total_artifacts = sum(type_counts.values())

    # ==============================
    # Phase 2: Unarticulated patterns (high log count, low fact/decision)
    # ==============================
    skip_tags = {
        "auto-graduated", "graduated-fact", "graduated-decision",
        "graduated-insight", "emerged-pattern", "duro", "log",
        "task", "session", "process", "applied", "link", "suggestions",
    }

    for tag, count in all_tags.most_common(50):
        if tag in skip_tags:
            continue
        log_count = tag_by_type[tag].get("log", 0)
        fact_count = tag_by_type[tag].get("fact", 0)
        decision_count = tag_by_type[tag].get("decision", 0)
        structured = fact_count + decision_count

        if log_count >= min_tag_freq and structured == 0:
            ideas.append(Idea(
                category=IdeaCategory.PATTERN_TO_NAME,
                title=f"Name the \"{tag}\" pattern",
                reasoning=f"{log_count} logs reference \"{tag}\" but no facts or decisions capture it. This is latent knowledge worth structuring.",
                priority=min(0.9, 0.5 + (log_count / 50)),
                evidence=[f"{log_count} logs with tag \"{tag}\""],
                tags=[tag],
            ))

    # ==============================
    # Phase 3: Facts to verify (unverified, high-ish confidence)
    # ==============================
    facts = artifacts_cache.get("fact", [])
    unverified_count = 0
    for fact in facts:
        verification = (
            fact.get("verification_state", "") or
            (fact.get("data", {}) or {}).get("verification_state", "") or
            "unverified"
        )
        if verification == "unverified":
            unverified_count += 1

    if unverified_count > 10:
        ideas.append(Idea(
            category=IdeaCategory.FACT_TO_VERIFY,
            title=f"Verify {unverified_count} unverified facts",
            reasoning=f"{unverified_count} of {len(facts)} facts are unverified. Run verify_and_store_fact or batch verification to build trust in the knowledge base.",
            priority=0.7,
            evidence=[f"{unverified_count}/{len(facts)} unverified"],
            tags=["verification", "trust"],
        ))

    # ==============================
    # Phase 4: Stale facts (old, not reinforced)
    # ==============================
    stale_facts = []
    for fact in facts:
        ts = extract_timestamp(fact)
        if ts and ts < stale_cutoff:
            text = extract_text(fact)
            if text:
                stale_facts.append(text[:100])

    if stale_facts:
        ideas.append(Idea(
            category=IdeaCategory.FACT_TO_VERIFY,
            title=f"Review {len(stale_facts)} stale facts (>{stale_days} days old)",
            reasoning=f"Facts older than {stale_days} days may be outdated. Decay or reverify.",
            priority=0.5,
            evidence=stale_facts[:3],
            tags=["maintenance", "decay"],
        ))

    # ==============================
    # Phase 5: Decisions to revisit (old, no validation)
    # ==============================
    decisions = artifacts_cache.get("decision", [])
    validations = artifacts_cache.get("evaluation", [])  # decision_validation
    # Also try decision_validation type
    dv = query_type(query_memory, "decision_validation", limit=200)

    validated_ids = set()
    for v in dv:
        import re
        text = extract_text(v)
        match = re.search(r'(decision_\d{8}_\d{6}_\w+)', text)
        if match:
            validated_ids.add(match.group(1))

    unvalidated_decisions = []
    for d in decisions:
        d_id = d.get("id", "")
        ts = extract_timestamp(d)
        if d_id not in validated_ids and ts and ts < stale_cutoff:
            text = extract_text(d)
            if text:
                unvalidated_decisions.append(text[:120])

    if unvalidated_decisions:
        ideas.append(Idea(
            category=IdeaCategory.DECISION_TO_REVISIT,
            title=f"Revisit {len(unvalidated_decisions)} old unvalidated decisions",
            reasoning=f"Decisions older than {stale_days} days that were never validated. Are they still the right call?",
            priority=0.65,
            evidence=unvalidated_decisions[:3],
            tags=["accountability", "decisions"],
        ))

    # ==============================
    # Phase 6: Cross-domain opportunities
    # ==============================
    # Find top tags that appear in many logs — potential skill/tool ideas
    high_activity_tags = [
        (tag, count) for tag, count in all_tags.most_common(20)
        if count >= 5 and tag not in skip_tags
    ]

    # Look for tag pairs that both have high activity
    if len(high_activity_tags) >= 2:
        tag_list = [t[0] for t in high_activity_tags[:8]]
        for i in range(len(tag_list)):
            for j in range(i + 1, len(tag_list)):
                t1, t2 = tag_list[i], tag_list[j]
                # Check if they co-occur in any artifacts
                co_occur = 0
                for art_type, items in artifacts_cache.items():
                    for item in items:
                        item_tags = {t.lower() for t in extract_tags(item)}
                        if t1 in item_tags and t2 in item_tags:
                            co_occur += 1
                if co_occur == 0 and all_tags[t1] >= 5 and all_tags[t2] >= 5:
                    ideas.append(Idea(
                        category=IdeaCategory.CONNECTION_TO_EXPLORE,
                        title=f"Explore connection: \"{t1}\" ↔ \"{t2}\"",
                        reasoning=f"Both are active domains ({all_tags[t1]} and {all_tags[t2]} artifacts) but never co-occur. Run connect_domains to find hidden bridges.",
                        priority=0.4,
                        evidence=[f"{t1}: {all_tags[t1]} artifacts", f"{t2}: {all_tags[t2]} artifacts"],
                        tags=[t1, t2],
                    ))
                    if len([i for i in ideas if i.category == IdeaCategory.CONNECTION_TO_EXPLORE]) >= 3:
                        break
            if len([i for i in ideas if i.category == IdeaCategory.CONNECTION_TO_EXPLORE]) >= 3:
                break

    # ==============================
    # Phase 7: Skill gaps
    # ==============================
    # Check what types of work happen in logs that could be automated
    log_event_types = Counter()
    logs = artifacts_cache.get("log", [])
    for log_entry in logs:
        event_type = (log_entry.get("data", {}) or {}).get("event_type", "unknown")
        if not event_type:
            event_type = "unknown"
        log_event_types[event_type] += 1

    # Check artifact type ratios for imbalances
    log_count = type_counts.get("log", 0)
    fact_count = type_counts.get("fact", 0)
    decision_count = type_counts.get("decision", 0)
    episode_count = type_counts.get("episode", 0)

    if log_count > 0 and episode_count < log_count * 0.01:
        ideas.append(Idea(
            category=IdeaCategory.KNOWLEDGE_GAP,
            title="Low episode usage — consider structured episode tracking",
            reasoning=f"Only {episode_count} episodes vs {log_count} logs. Episodes capture multi-step workflows with outcomes — valuable for learning from complex tasks.",
            priority=0.45,
            evidence=[f"episodes: {episode_count}", f"logs: {log_count}"],
            tags=["episodes", "workflow"],
        ))

    if fact_count > 0 and fact_count < log_count * 0.15:
        ratio = round(log_count / max(fact_count, 1), 1)
        ideas.append(Idea(
            category=IdeaCategory.KNOWLEDGE_GAP,
            title=f"Log-to-fact ratio is {ratio}:1 — run graduate_logs regularly",
            reasoning=f"{log_count} logs vs {fact_count} facts. Much knowledge is still trapped in logs. Schedule regular graduate_logs runs to promote insights.",
            priority=0.6,
            evidence=[f"ratio: {ratio}:1"],
            tags=["graduate", "maintenance"],
        ))

    # ==============================
    # Phase 8: Rank and report
    # ==============================
    ideas.sort(key=lambda i: -i.priority)
    ideas = ideas[:max_ideas]

    report = format_report(ideas, type_counts, total_artifacts, len(all_tags))

    ideas_output = [
        {
            "category": i.category,
            "title": i.title,
            "reasoning": i.reasoning,
            "priority": i.priority,
            "evidence": i.evidence,
            "tags": i.tags,
        }
        for i in ideas
    ]

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "report": report,
        "ideas": ideas_output,
        "total_artifacts": total_artifacts,
        "ideas_generated": len(ideas),
        "type_counts": type_counts,
        "elapsed_seconds": elapsed,
    }


def format_report(
    ideas: List[Idea],
    type_counts: Dict[str, int],
    total_artifacts: int,
    tag_count: int,
) -> str:
    lines = []
    lines.append("## Idea Generation Report")
    lines.append("")
    lines.append(f"**Artifacts scanned:** {total_artifacts} across {len(type_counts)} types")
    lines.append(f"**Tags analyzed:** {tag_count}")
    lines.append(f"**Ideas generated:** {len(ideas)}")
    lines.append("")

    # Type breakdown
    lines.append("**Artifact census:**")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {t}: {c}")
    lines.append("")

    if not ideas:
        lines.append("No actionable ideas generated. The knowledge base appears well-maintained.")
        return "\n".join(lines)

    # Group by category
    category_labels = {
        IdeaCategory.PATTERN_TO_NAME: "Patterns to Name",
        IdeaCategory.FACT_TO_VERIFY: "Facts to Verify / Review",
        IdeaCategory.DECISION_TO_REVISIT: "Decisions to Revisit",
        IdeaCategory.CONNECTION_TO_EXPLORE: "Connections to Explore",
        IdeaCategory.KNOWLEDGE_GAP: "Knowledge Gaps",
        IdeaCategory.SKILL_TO_BUILD: "Skills to Build",
    }

    by_category = defaultdict(list)
    for idea in ideas:
        by_category[idea.category].append(idea)

    category_order = [
        IdeaCategory.PATTERN_TO_NAME,
        IdeaCategory.DECISION_TO_REVISIT,
        IdeaCategory.FACT_TO_VERIFY,
        IdeaCategory.KNOWLEDGE_GAP,
        IdeaCategory.CONNECTION_TO_EXPLORE,
        IdeaCategory.SKILL_TO_BUILD,
    ]

    for cat in category_order:
        group = by_category.get(cat, [])
        if not group:
            continue
        label = category_labels.get(cat, cat)
        lines.append(f"### {label} ({len(group)})")
        lines.append("")
        for idea in group:
            lines.append(f"- **[{idea.priority:.0%}]** {idea.title}")
            lines.append(f"  {idea.reasoning}")
            if idea.evidence:
                evidence_str = "; ".join(str(e)[:100] for e in idea.evidence[:2])
                lines.append(f"  Evidence: {evidence_str}")
            lines.append("")

    return "\n".join(lines)


# --- CLI Mode ---
if __name__ == "__main__":
    print("idea_generation Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Idea categories:")
    print("  - pattern_to_name: recurring themes without structured artifacts")
    print("  - decision_to_revisit: stale or unvalidated decisions")
    print("  - fact_to_verify: unverified facts needing evidence")
    print("  - connection_to_explore: disconnected high-activity domains")
    print("  - knowledge_gap: structural imbalances in the artifact space")
    print("  - skill_to_build: automation opportunities")
