"""
Skill: emerge
Description: Detect latent patterns — things Duro knows that the user hasn't articulated
Version: 1.0.0
Tier: tested

Surfaces recurring themes buried across artifacts that haven't been named as
facts or decisions. The most valuable output is patterns with high signal in
logs but no corresponding structured artifact.

Algorithm:
1. Census — collect all artifacts, build tag frequency map by type
2. Term Extraction — find significant phrases recurring in logs but absent from facts
3. Semantic Probing — use semantic_search to expand seed concepts into clusters
4. Pattern Scoring — rank by cluster size, type diversity, unarticulated ratio
5. Report — present named patterns with evidence and suggested actions

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import re
import time
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field


# Skill metadata
SKILL_META = {
    "name": "emerge",
    "description": "Detect latent patterns — things Duro knows that the user hasn't articulated",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Reflective layer roadmap (Greg Eisenberg x Internet Vin podcast)",
    "validated": "2026-02-24",
    "triggers": ["emerge", "patterns", "latent", "what do I keep thinking about", "themes"],
    "keywords": [
        "emerge", "pattern", "latent", "detect", "cluster", "semantic",
        "theme", "recurring", "unarticulated", "reflection", "insight"
    ],
    "phase": "4.0",
}

# Default configuration
DEFAULT_CONFIG = {
    "max_artifacts": 500,       # Max artifacts to scan per type
    "max_patterns": 10,         # Max patterns to return
    "min_cluster_size": 3,      # Minimum artifacts to form a pattern
    "min_term_frequency": 3,    # Minimum occurrences for a term to be interesting
    "max_semantic_probes": 10,  # Max semantic_search calls (budget)
    "days_back": 30,            # How far back to scan
}

# Required capabilities
REQUIRES = ["query_memory", "semantic_search"]

# Default timeout
DEFAULT_TIMEOUT = 60


@dataclass
class PatternCandidate:
    """A latent pattern detected across artifacts."""
    name: str                       # Short descriptive label
    seed: str                       # The seed that spawned this pattern
    seed_type: str                  # "tag", "term", or "semantic"
    artifact_ids: List[str] = field(default_factory=list)
    artifact_types: Dict[str, int] = field(default_factory=dict)  # type -> count
    sample_messages: List[str] = field(default_factory=list)      # Up to 3 examples
    tags_involved: List[str] = field(default_factory=list)
    score: float = 0.0
    unarticulated_ratio: float = 0.0  # % of evidence in logs vs structured
    recency_score: float = 0.0
    reasoning: str = ""


# --- Stop words for term extraction ---
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "don", "now", "and", "but", "or", "if", "while", "that", "this",
    "these", "those", "it", "its", "i", "my", "we", "our", "you", "your",
    "he", "she", "they", "them", "his", "her", "what", "which", "who",
    "whom", "up", "about", "also", "new", "one", "two", "like", "get",
    "set", "use", "using", "used", "make", "made",
}

# Domain-specific stop words (common in Duro logs but not meaningful as patterns)
DOMAIN_STOP = {
    "duro", "artifact", "skill", "log", "fact", "decision", "memory",
    "session", "task", "completed", "created", "updated", "added",
    "removed", "fixed", "changed", "moved", "note", "status", "success",
    "failed", "error", "run", "running", "test", "testing", "check",
}


def extract_text(artifact: Dict) -> str:
    """Extract the main text content from an artifact."""
    if "data" in artifact:
        data = artifact["data"]
        return (
            data.get("message", "") or
            data.get("claim", "") or
            data.get("title", "") or
            data.get("decision", "") or
            data.get("rationale", "") or
            ""
        )
    return (
        artifact.get("message", "") or
        artifact.get("claim", "") or
        artifact.get("title", "") or
        ""
    )


def extract_tags(artifact: Dict) -> List[str]:
    """Extract tags from an artifact."""
    return artifact.get("tags", []) or []


def extract_type(artifact: Dict) -> str:
    """Extract artifact type."""
    return artifact.get("artifact_type", artifact.get("type", "unknown"))


def tokenize(text: str) -> List[str]:
    """Tokenize text into meaningful words."""
    words = re.findall(r'[a-zA-Z][a-zA-Z\'-]{2,}', text.lower())
    return [w for w in words if w not in STOP_WORDS and w not in DOMAIN_STOP]


def extract_bigrams(tokens: List[str]) -> List[str]:
    """Extract bigrams from token list."""
    return [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]


def build_tag_census(artifacts: List[Dict]) -> Dict[str, Dict[str, int]]:
    """
    Build a census: tag -> {artifact_type: count}.
    Shows which tags appear in which artifact types.
    """
    census = defaultdict(lambda: defaultdict(int))
    for art in artifacts:
        art_type = extract_type(art)
        for tag in extract_tags(art):
            tag_lower = tag.lower().strip()
            if tag_lower and len(tag_lower) > 1:
                census[tag_lower][art_type] += 1
    return dict(census)


def find_unarticulated_tags(
    census: Dict[str, Dict[str, int]],
    min_log_count: int = 3
) -> List[Tuple[str, int, float]]:
    """
    Find tags that appear frequently in logs but rarely/never in facts or decisions.
    Returns (tag, log_count, unarticulated_ratio).
    """
    results = []
    for tag, type_counts in census.items():
        log_count = type_counts.get("log", 0)
        fact_count = type_counts.get("fact", 0)
        decision_count = type_counts.get("decision", 0)
        structured_count = fact_count + decision_count

        if log_count < min_log_count:
            continue

        total = log_count + structured_count
        if total == 0:
            continue

        unarticulated = log_count / total
        # Only interesting if mostly unarticulated (>60% in logs)
        if unarticulated > 0.6:
            results.append((tag, log_count, round(unarticulated, 2)))

    results.sort(key=lambda x: (-x[2], -x[1]))
    return results


def find_recurring_terms(
    logs: List[Dict],
    existing_tags: set,
    min_freq: int = 3,
    max_terms: int = 20
) -> List[Tuple[str, int]]:
    """
    Find significant bigrams recurring across multiple logs
    that aren't already captured as tags.
    """
    bigram_counter = Counter()
    bigram_sources = defaultdict(set)  # bigram -> set of log_ids

    for log_entry in logs:
        text = extract_text(log_entry)
        log_id = log_entry.get("id", "")
        tokens = tokenize(text)
        bigrams = extract_bigrams(tokens)

        for bg in bigrams:
            bigram_counter[bg] += 1
            bigram_sources[bg].add(log_id)

    # Filter: must appear in min_freq distinct logs, not already a tag
    results = []
    for bg, count in bigram_counter.most_common(max_terms * 3):
        source_count = len(bigram_sources[bg])
        if source_count < min_freq:
            continue
        # Skip if it's essentially an existing tag
        if any(bg.replace(" ", "") == t.replace(" ", "").lower() or
               bg.replace(" ", "-") == t.lower() or
               bg == t.lower()
               for t in existing_tags):
            continue
        results.append((bg, source_count))
        if len(results) >= max_terms:
            break

    return results


def probe_semantic_cluster(
    seed_query: str,
    tools: Dict[str, Any],
    limit: int = 20
) -> List[Dict]:
    """
    Use semantic_search to find artifacts related to a seed concept.
    Returns list of matching artifacts.
    """
    semantic_search = tools.get("semantic_search")
    if not semantic_search:
        return []

    try:
        result = semantic_search(query=seed_query, limit=limit)
        if isinstance(result, dict):
            return result.get("results", [])
        elif isinstance(result, list):
            return result
    except Exception:
        return []
    return []


def score_pattern(
    candidate: PatternCandidate,
    total_artifacts: int
) -> float:
    """
    Score a pattern candidate. Higher = more interesting.

    Factors:
    - Cluster size (0-0.25): bigger clusters are more significant
    - Type diversity (0-0.25): spanning multiple artifact types is interesting
    - Unarticulated ratio (0-0.3): mostly-in-logs patterns are the gold
    - Tag diversity (0-0.2): touching multiple domains suggests a cross-cutting concern
    """
    score = 0.0

    # Cluster size (0-0.25)
    cluster_size = sum(candidate.artifact_types.values())
    size_ratio = min(1.0, cluster_size / max(total_artifacts * 0.05, 1))
    score += size_ratio * 0.25

    # Type diversity (0-0.25)
    type_count = len(candidate.artifact_types)
    if type_count >= 4:
        score += 0.25
    elif type_count >= 3:
        score += 0.20
    elif type_count >= 2:
        score += 0.12
    else:
        score += 0.05

    # Unarticulated ratio (0-0.3) — the core metric
    score += candidate.unarticulated_ratio * 0.3

    # Tag diversity (0-0.2)
    unique_tags = len(set(candidate.tags_involved))
    tag_score = min(1.0, unique_tags / 5)
    score += tag_score * 0.2

    return round(score, 3)


def name_pattern(seed: str, sample_messages: List[str]) -> str:
    """Generate a short descriptive name for a pattern from its seed and samples."""
    # Use the seed as the base name, title-cased
    name = seed.strip().title()

    # If it's a bigram, keep it. If single word, try to add context from samples.
    if " " not in name and sample_messages:
        # Find the most common co-occurring word in samples
        co_words = Counter()
        seed_lower = seed.lower()
        for msg in sample_messages[:5]:
            tokens = tokenize(msg)
            for t in tokens:
                if t != seed_lower and len(t) > 3:
                    co_words[t] += 1
        if co_words:
            top_co = co_words.most_common(1)[0][0]
            name = f"{name} + {top_co.title()}"

    return name


def calculate_unarticulated_ratio(type_counts: Dict[str, int]) -> float:
    """Calculate what fraction of evidence is in unstructured artifacts (logs)."""
    log_count = type_counts.get("log", 0)
    structured = sum(
        v for k, v in type_counts.items()
        if k in ("fact", "decision")
    )
    total = log_count + structured
    if total == 0:
        return 0.0
    return round(log_count / total, 2)


def format_report(
    patterns: List[PatternCandidate],
    total_artifacts: int,
    tag_census_size: int,
    term_count: int
) -> str:
    """Format the emerge report for display."""
    lines = []
    lines.append("## Emerge Report — Latent Patterns Detected")
    lines.append("")
    lines.append(f"**Scanned:** {total_artifacts} artifacts across all types")
    lines.append(f"**Tag census:** {tag_census_size} unique tags analyzed")
    lines.append(f"**Recurring terms:** {term_count} significant bigrams found")
    lines.append(f"**Patterns surfaced:** {len(patterns)}")
    lines.append("")

    if not patterns:
        lines.append("No strong latent patterns detected. Your structured memory may be well-aligned with your activity.")
        return "\n".join(lines)

    for i, p in enumerate(patterns, 1):
        cluster_size = sum(p.artifact_types.values())
        type_breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(p.artifact_types.items()))

        lines.append(f"### {i}. {p.name}")
        lines.append(f"**Score:** {p.score:.0%} | **Cluster:** {cluster_size} artifacts | **Unarticulated:** {p.unarticulated_ratio:.0%}")
        lines.append(f"**Types:** {type_breakdown}")
        if p.tags_involved:
            lines.append(f"**Tags:** {', '.join(p.tags_involved[:8])}")
        lines.append(f"**Source:** {p.seed_type} seed — \"{p.seed}\"")
        lines.append("")

        # Sample evidence
        if p.sample_messages:
            lines.append("**Evidence:**")
            for j, msg in enumerate(p.sample_messages[:3], 1):
                truncated = msg[:150] + "..." if len(msg) > 150 else msg
                lines.append(f"  {j}. {truncated}")
            lines.append("")

        if p.reasoning:
            lines.append(f"**Why this matters:** {p.reasoning}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            max_artifacts: int (default 500) - Max artifacts to scan per type
            max_patterns: int (default 10) - Max patterns to return
            min_cluster_size: int (default 3) - Min artifacts per pattern
            days_back: int (default 30) - How far back to scan
            max_probes: int (default 10) - Max semantic search calls
            types: List[str] (optional) - Artifact types to scan
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
            patterns: List[dict],
            total_artifacts: int,
            patterns_found: int,
            elapsed_seconds: float,
        }
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    # Parse args
    max_artifacts = args.get("max_artifacts", DEFAULT_CONFIG["max_artifacts"])
    max_patterns = args.get("max_patterns", DEFAULT_CONFIG["max_patterns"])
    min_cluster = args.get("min_cluster_size", DEFAULT_CONFIG["min_cluster_size"])
    days_back = args.get("days_back", DEFAULT_CONFIG["days_back"])
    max_probes = args.get("max_probes", DEFAULT_CONFIG["max_semantic_probes"])
    min_term_freq = args.get("min_term_frequency", DEFAULT_CONFIG["min_term_frequency"])
    scan_types = args.get("types", ["log", "fact", "decision", "episode", "evaluation"])

    query_memory = tools.get("query_memory")
    semantic_search = tools.get("semantic_search")

    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    # ==============================
    # Phase 1: Collect artifacts
    # ==============================
    from datetime import datetime, timedelta
    since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    all_artifacts = []
    artifacts_by_type = defaultdict(list)

    for art_type in scan_types:
        if time.time() - start_time >= timeout * 0.8:
            break
        try:
            result = query_memory(
                artifact_type=art_type,
                since=since_date,
                limit=max_artifacts
            )
            items = []
            if isinstance(result, list):
                items = result
            elif isinstance(result, dict):
                items = result.get("results", result.get("artifacts", []))

            for item in items:
                # Normalize type
                if "artifact_type" not in item:
                    item["artifact_type"] = art_type
                all_artifacts.append(item)
                artifacts_by_type[art_type].append(item)
        except Exception:
            continue

    if not all_artifacts:
        return {
            "success": True,
            "report": f"No artifacts found in last {days_back} days.",
            "patterns": [],
            "total_artifacts": 0,
            "patterns_found": 0,
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    total_artifacts = len(all_artifacts)
    logs = artifacts_by_type.get("log", [])

    # ==============================
    # Phase 2: Tag Census
    # ==============================
    tag_census = build_tag_census(all_artifacts)
    all_tag_names = set(tag_census.keys())

    # Find tags that are mostly unarticulated (heavy in logs, light in facts)
    unarticulated_tags = find_unarticulated_tags(tag_census, min_log_count=min_cluster)

    # ==============================
    # Phase 3: Recurring Term Extraction
    # ==============================
    recurring_terms = find_recurring_terms(
        logs, all_tag_names, min_freq=min_term_freq, max_terms=20
    )

    # ==============================
    # Phase 4: Build seed list for semantic probing
    # ==============================
    seeds = []

    # Priority 1: Unarticulated tags (most valuable — known tags with hidden depth)
    for tag, count, ratio in unarticulated_tags[:5]:
        seeds.append({
            "query": tag,
            "seed_type": "tag",
            "meta": {"log_count": count, "unarticulated_ratio": ratio}
        })

    # Priority 2: Recurring terms (unnamed patterns)
    for term, count in recurring_terms[:5]:
        seeds.append({
            "query": term,
            "seed_type": "term",
            "meta": {"frequency": count}
        })

    # Cap at max_probes
    seeds = seeds[:max_probes]

    # ==============================
    # Phase 5: Semantic Probing
    # ==============================
    pattern_candidates = []
    seen_artifact_sets = []  # To deduplicate overlapping clusters

    for seed_info in seeds:
        if time.time() - start_time >= timeout * 0.9:
            break

        query = seed_info["query"]
        seed_type = seed_info["seed_type"]

        cluster_results = probe_semantic_cluster(query, tools, limit=20)
        if not cluster_results:
            continue

        # Build cluster stats
        cluster_ids = []
        cluster_type_counts = defaultdict(int)
        cluster_tags = []
        cluster_messages = []

        for result_item in cluster_results:
            art_id = result_item.get("id", "")
            art_type = extract_type(result_item)
            text = extract_text(result_item)
            tags = extract_tags(result_item)

            if art_id:
                cluster_ids.append(art_id)
            cluster_type_counts[art_type] += 1
            cluster_tags.extend(tags)
            if text and len(text) > 30:
                cluster_messages.append(text)

        cluster_size = len(cluster_ids)
        if cluster_size < min_cluster:
            continue

        # Deduplicate: skip if >70% overlap with an existing cluster
        id_set = set(cluster_ids)
        is_duplicate = False
        for existing_set in seen_artifact_sets:
            if not id_set or not existing_set:
                continue
            overlap = len(id_set & existing_set) / min(len(id_set), len(existing_set))
            if overlap > 0.7:
                is_duplicate = True
                break

        if is_duplicate:
            continue

        seen_artifact_sets.append(id_set)

        # Calculate unarticulated ratio
        u_ratio = calculate_unarticulated_ratio(dict(cluster_type_counts))

        # Name the pattern
        pattern_name = name_pattern(query, cluster_messages)

        # Generate reasoning
        reasons = []
        if u_ratio >= 0.7:
            reasons.append(f"{u_ratio:.0%} of evidence is in logs — not yet captured as structured knowledge")
        elif u_ratio >= 0.5:
            reasons.append(f"{u_ratio:.0%} of evidence still in logs")
        if len(cluster_type_counts) >= 3:
            reasons.append(f"spans {len(cluster_type_counts)} artifact types — cross-cutting theme")
        if seed_type == "term":
            reasons.append(f"recurring phrase \"{query}\" appears across {seed_info['meta'].get('frequency', '?')} logs but isn't a named concept")
        if cluster_size >= 10:
            reasons.append(f"large cluster ({cluster_size} artifacts) — significant body of thinking")

        # Unique tags in cluster
        unique_cluster_tags = list(set(
            t.lower() for t in cluster_tags
            if t.lower() not in DOMAIN_STOP and len(t) > 1
        ))

        candidate = PatternCandidate(
            name=pattern_name,
            seed=query,
            seed_type=seed_type,
            artifact_ids=cluster_ids,
            artifact_types=dict(cluster_type_counts),
            sample_messages=cluster_messages[:3],
            tags_involved=unique_cluster_tags[:10],
            unarticulated_ratio=u_ratio,
            reasoning="; ".join(reasons) if reasons else "recurring theme across artifacts",
        )

        candidate.score = score_pattern(candidate, total_artifacts)
        pattern_candidates.append(candidate)

    # ==============================
    # Phase 6: Rank and report
    # ==============================
    pattern_candidates.sort(key=lambda p: -p.score)
    pattern_candidates = pattern_candidates[:max_patterns]

    report = format_report(
        pattern_candidates,
        total_artifacts,
        len(tag_census),
        len(recurring_terms),
    )

    # Serialize patterns for output
    patterns_output = []
    for p in pattern_candidates:
        patterns_output.append({
            "name": p.name,
            "seed": p.seed,
            "seed_type": p.seed_type,
            "score": p.score,
            "cluster_size": sum(p.artifact_types.values()),
            "artifact_types": p.artifact_types,
            "unarticulated_ratio": p.unarticulated_ratio,
            "tags": p.tags_involved,
            "sample_messages": [m[:200] for m in p.sample_messages],
            "reasoning": p.reasoning,
        })

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "report": report,
        "patterns": patterns_output,
        "total_artifacts": total_artifacts,
        "patterns_found": len(patterns_output),
        "unarticulated_tags_found": len(unarticulated_tags),
        "recurring_terms_found": len(recurring_terms),
        "seeds_probed": len(seeds),
        "elapsed_seconds": elapsed,
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("emerge Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Algorithm:")
    print("  1. Tag Census — map tag frequency by artifact type")
    print("  2. Term Extraction — find recurring bigrams in logs")
    print("  3. Semantic Probing — expand seeds into clusters")
    print("  4. Pattern Scoring — rank by size, diversity, unarticulated ratio")
    print("  5. Report — present named patterns with evidence")
    print()
    print("Scoring factors:")
    print("  - Cluster size (0-0.25): bigger = more significant")
    print("  - Type diversity (0-0.25): spanning multiple types")
    print("  - Unarticulated ratio (0-0.3): mostly-in-logs = gold")
    print("  - Tag diversity (0-0.2): cross-cutting themes")
    print()
    print("Default config:")
    for k, v in DEFAULT_CONFIG.items():
        print(f"  {k}: {v}")
