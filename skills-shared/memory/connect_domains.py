"""
Skill: connect_domains
Description: Find unexpected bridges between two concepts/tags across the artifact space
Version: 1.0.0
Tier: tested

The creative tool. Given two concepts (tags, keywords, or phrases), finds
artifacts that bridge both domains — the unexpected connections.

Algorithm:
1. Search each domain independently (tag query + semantic search)
2. Find intersection artifacts (appear in both result sets)
3. Find bridge artifacts (semantically close to both but not tagged in either)
4. Score bridges by: relevance to both domains, rarity, artifact type diversity
5. Report connections with evidence and suggested implications

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import re
import time
from collections import defaultdict
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field


SKILL_META = {
    "name": "connect_domains",
    "description": "Find unexpected bridges between two concepts/tags across the artifact space",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Reflective layer roadmap (Greg Eisenberg x Internet Vin podcast)",
    "validated": "2026-02-24",
    "triggers": ["connect", "bridge", "between", "link domains", "cross-pollinate"],
    "keywords": [
        "connect", "domains", "bridge", "cross-cutting", "intersection",
        "unexpected", "link", "creative", "cross-pollinate", "combine"
    ],
    "phase": "4.0",
}

DEFAULT_CONFIG = {
    "search_limit": 30,         # Per-domain semantic search limit
    "tag_limit": 30,            # Per-domain tag query limit
    "max_bridges": 10,          # Max bridge artifacts to return
    "min_relevance": 0.15,      # Min relevance to a domain to count
}

REQUIRES = ["query_memory", "semantic_search"]

DEFAULT_TIMEOUT = 60


@dataclass
class DomainResult:
    """Artifacts found for one domain."""
    concept: str
    artifact_ids: Set[str] = field(default_factory=set)
    artifacts: Dict[str, Dict] = field(default_factory=dict)  # id -> artifact


@dataclass
class Bridge:
    """An artifact that connects two domains."""
    artifact_id: str
    artifact_type: str
    text: str
    timestamp: str
    tags: List[str]
    relevance_a: float          # Relevance to domain A
    relevance_b: float          # Relevance to domain B
    bridge_type: str            # "intersection", "semantic_bridge", "tag_bridge"
    score: float = 0.0

    @property
    def combined_relevance(self) -> float:
        return self.relevance_a + self.relevance_b

    @property
    def balance(self) -> float:
        """How evenly balanced between domains (1.0 = perfect balance)."""
        if self.combined_relevance == 0:
            return 0
        return 1.0 - abs(self.relevance_a - self.relevance_b) / self.combined_relevance


def extract_text(artifact: Dict) -> str:
    title = artifact.get("title", "")
    if title:
        return str(title)
    if "data" in artifact:
        data = artifact["data"]
        parts = []
        for key in ("message", "claim", "decision", "rationale", "title"):
            val = data.get(key, "")
            if val:
                parts.append(str(val))
        return " ".join(parts) if parts else ""
    for key in ("message", "claim", "decision"):
        val = artifact.get(key, "")
        if val:
            return str(val)
    return ""


def extract_tags(artifact: Dict) -> List[str]:
    return artifact.get("tags", []) or []


def extract_type(artifact: Dict) -> str:
    return artifact.get("artifact_type", artifact.get("type", "unknown"))


def extract_timestamp(artifact: Dict) -> str:
    return (
        artifact.get("created_at", "") or
        artifact.get("timestamp", "") or
        ""
    )


def concept_relevance(text: str, concept: str) -> float:
    """Score how relevant text is to a concept (0-1)."""
    text_lower = text.lower()
    concept_lower = concept.lower()
    concept_words = concept_lower.split()

    score = 0.0

    if concept_lower in text_lower:
        score += 0.5

    word_hits = sum(1 for w in concept_words if w in text_lower)
    if concept_words:
        score += 0.3 * (word_hits / len(concept_words))

    first_100 = text_lower[:100]
    if concept_lower in first_100:
        score += 0.2

    return min(1.0, score)


def search_domain(
    concept: str,
    tools: Dict[str, Any],
    search_limit: int,
    tag_limit: int,
    timeout_at: float,
) -> DomainResult:
    """Search for all artifacts related to a concept."""
    domain = DomainResult(concept=concept)
    query_memory = tools.get("query_memory")
    semantic_search = tools.get("semantic_search")

    # Tag-based search across artifact types
    if query_memory:
        scan_types = ["fact", "decision", "log", "episode", "evaluation",
                       "incident_rca", "design_reference"]
        for art_type in scan_types:
            if time.time() >= timeout_at:
                break
            try:
                result = query_memory(artifact_type=art_type, tags=[concept], limit=tag_limit)
                items = result if isinstance(result, list) else (
                    result.get("results", result.get("artifacts", []))
                    if isinstance(result, dict) else []
                )
                for item in items:
                    art_id = item.get("id", "")
                    if art_id:
                        if "artifact_type" not in item:
                            item["artifact_type"] = art_type
                        domain.artifact_ids.add(art_id)
                        domain.artifacts[art_id] = item
            except Exception:
                continue

    # Semantic search
    if semantic_search and time.time() < timeout_at:
        try:
            result = semantic_search(query=concept, limit=search_limit)
            items = []
            if isinstance(result, dict):
                items = result.get("results", [])
            elif isinstance(result, list):
                items = result
            for item in items:
                art_id = item.get("id", "")
                if art_id:
                    domain.artifact_ids.add(art_id)
                    if art_id not in domain.artifacts:
                        domain.artifacts[art_id] = item
        except Exception:
            pass

    return domain


def find_bridges(
    domain_a: DomainResult,
    domain_b: DomainResult,
    min_relevance: float,
    max_bridges: int,
) -> List[Bridge]:
    """Find artifacts that bridge two domains."""
    bridges = []
    seen_ids = set()

    # 1. Direct intersection — artifacts in both result sets
    intersection_ids = domain_a.artifact_ids & domain_b.artifact_ids
    for art_id in intersection_ids:
        artifact = domain_a.artifacts.get(art_id) or domain_b.artifacts.get(art_id)
        if not artifact:
            continue
        text = extract_text(artifact)
        if not text or len(text) < 20:
            continue

        rel_a = concept_relevance(text, domain_a.concept)
        rel_b = concept_relevance(text, domain_b.concept)

        bridges.append(Bridge(
            artifact_id=art_id,
            artifact_type=extract_type(artifact),
            text=text,
            timestamp=extract_timestamp(artifact),
            tags=extract_tags(artifact),
            relevance_a=rel_a,
            relevance_b=rel_b,
            bridge_type="intersection",
        ))
        seen_ids.add(art_id)

    # 2. Semantic bridges — in domain A's results but relevant to B (and vice versa)
    for art_id, artifact in domain_a.artifacts.items():
        if art_id in seen_ids:
            continue
        text = extract_text(artifact)
        if not text or len(text) < 20:
            continue

        rel_b = concept_relevance(text, domain_b.concept)
        if rel_b >= min_relevance:
            rel_a = concept_relevance(text, domain_a.concept)
            bridges.append(Bridge(
                artifact_id=art_id,
                artifact_type=extract_type(artifact),
                text=text,
                timestamp=extract_timestamp(artifact),
                tags=extract_tags(artifact),
                relevance_a=rel_a,
                relevance_b=rel_b,
                bridge_type="semantic_bridge",
            ))
            seen_ids.add(art_id)

    for art_id, artifact in domain_b.artifacts.items():
        if art_id in seen_ids:
            continue
        text = extract_text(artifact)
        if not text or len(text) < 20:
            continue

        rel_a = concept_relevance(text, domain_a.concept)
        if rel_a >= min_relevance:
            rel_b = concept_relevance(text, domain_b.concept)
            bridges.append(Bridge(
                artifact_id=art_id,
                artifact_type=extract_type(artifact),
                text=text,
                timestamp=extract_timestamp(artifact),
                tags=extract_tags(artifact),
                relevance_a=rel_a,
                relevance_b=rel_b,
                bridge_type="semantic_bridge",
            ))
            seen_ids.add(art_id)

    # 3. Tag bridges — artifacts whose tags span both domains
    all_artifacts = {**domain_a.artifacts, **domain_b.artifacts}
    concept_a_lower = domain_a.concept.lower()
    concept_b_lower = domain_b.concept.lower()
    for art_id, artifact in all_artifacts.items():
        if art_id in seen_ids:
            continue
        tags_lower = [t.lower() for t in extract_tags(artifact)]
        has_a = any(concept_a_lower in t or t in concept_a_lower for t in tags_lower)
        has_b = any(concept_b_lower in t or t in concept_b_lower for t in tags_lower)
        if has_a and has_b:
            text = extract_text(artifact)
            if not text or len(text) < 20:
                continue
            bridges.append(Bridge(
                artifact_id=art_id,
                artifact_type=extract_type(artifact),
                text=text,
                timestamp=extract_timestamp(artifact),
                tags=extract_tags(artifact),
                relevance_a=concept_relevance(text, domain_a.concept),
                relevance_b=concept_relevance(text, domain_b.concept),
                bridge_type="tag_bridge",
            ))
            seen_ids.add(art_id)

    # Score and sort
    for bridge in bridges:
        bridge.score = score_bridge(bridge)

    bridges.sort(key=lambda b: -b.score)
    return bridges[:max_bridges]


def score_bridge(bridge: Bridge) -> float:
    """Score a bridge artifact. Higher = more interesting connection.

    Factors:
    - Combined relevance (0-0.35): relevant to both domains
    - Balance (0-0.30): evenly relevant to both (not lopsided)
    - Bridge type (0-0.20): intersection > tag_bridge > semantic_bridge
    - Text substance (0-0.15): longer text = more substance
    """
    score = 0.0

    # Combined relevance (0-0.35)
    score += min(0.35, bridge.combined_relevance * 0.175)

    # Balance (0-0.30) — penalize lopsided bridges
    score += bridge.balance * 0.30

    # Bridge type bonus (0-0.20)
    type_scores = {
        "intersection": 0.20,
        "tag_bridge": 0.15,
        "semantic_bridge": 0.10,
    }
    score += type_scores.get(bridge.bridge_type, 0.05)

    # Text substance (0-0.15)
    word_count = len(bridge.text.split())
    if word_count >= 30:
        score += 0.15
    elif word_count >= 15:
        score += 0.10
    elif word_count >= 8:
        score += 0.05

    return round(score, 3)


def format_report(
    concept_a: str,
    concept_b: str,
    domain_a: DomainResult,
    domain_b: DomainResult,
    bridges: List[Bridge],
) -> str:
    lines = []
    lines.append(f"## Connect Domains: \"{concept_a}\" ↔ \"{concept_b}\"")
    lines.append("")

    lines.append(f"**Domain A** (\"{concept_a}\"): {len(domain_a.artifact_ids)} artifacts")
    lines.append(f"**Domain B** (\"{concept_b}\"): {len(domain_b.artifact_ids)} artifacts")
    overlap = len(domain_a.artifact_ids & domain_b.artifact_ids)
    lines.append(f"**Direct overlap:** {overlap} artifacts")
    lines.append(f"**Bridges found:** {len(bridges)}")
    lines.append("")

    if not bridges:
        lines.append(f"No bridges found between \"{concept_a}\" and \"{concept_b}\". These domains appear isolated from each other.")
        return "\n".join(lines)

    # Group by bridge type
    intersections = [b for b in bridges if b.bridge_type == "intersection"]
    semantic = [b for b in bridges if b.bridge_type == "semantic_bridge"]
    tag_bridges = [b for b in bridges if b.bridge_type == "tag_bridge"]

    if intersections:
        lines.append(f"### Direct Connections ({len(intersections)})")
        lines.append("*Artifacts that live in both domains:*")
        lines.append("")
        for b in intersections:
            truncated = b.text[:180] + "..." if len(b.text) > 180 else b.text
            lines.append(f"- **[{b.artifact_type}]** (score: {b.score:.0%}) {truncated}")
            if b.tags:
                lines.append(f"  Tags: {', '.join(b.tags[:6])}")
        lines.append("")

    if semantic:
        lines.append(f"### Semantic Bridges ({len(semantic)})")
        lines.append("*Artifacts from one domain that are relevant to the other:*")
        lines.append("")
        for b in semantic:
            truncated = b.text[:180] + "..." if len(b.text) > 180 else b.text
            # Show which direction the bridge goes
            if b.relevance_a > b.relevance_b:
                direction = f"\"{concept_a}\" → \"{concept_b}\""
            else:
                direction = f"\"{concept_b}\" → \"{concept_a}\""
            lines.append(f"- **[{b.artifact_type}]** (score: {b.score:.0%}, {direction}) {truncated}")
        lines.append("")

    if tag_bridges:
        lines.append(f"### Tag Bridges ({len(tag_bridges)})")
        lines.append("*Artifacts tagged in both domains:*")
        lines.append("")
        for b in tag_bridges:
            truncated = b.text[:180] + "..." if len(b.text) > 180 else b.text
            lines.append(f"- **[{b.artifact_type}]** (score: {b.score:.0%}) {truncated}")
            lines.append(f"  Tags: {', '.join(b.tags[:6])}")
        lines.append("")

    # Synthesis
    lines.append("### Synthesis")
    if overlap > 3:
        lines.append(f"These domains are **well-connected** ({overlap} shared artifacts). The bridge artifacts suggest a natural relationship.")
    elif overlap > 0:
        lines.append(f"These domains have **some connection** ({overlap} shared artifacts). The bridges point to specific linking themes.")
    else:
        lines.append(f"These domains are **mostly isolated**. The {len(bridges)} bridges found represent potentially novel connections worth exploring.")
    lines.append("")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            concept_a: str (required) - First domain/concept
            concept_b: str (required) - Second domain/concept
            max_bridges: int (default 10) - Max bridge artifacts to return
            search_limit: int (default 30) - Per-domain semantic search limit
        }
        tools: {
            query_memory: callable
            semantic_search: callable
        }
        context: {run_id, timeout}
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    concept_a = args.get("concept_a", "").strip()
    concept_b = args.get("concept_b", "").strip()
    if not concept_a or not concept_b:
        return {"success": False, "error": "Both concept_a and concept_b are required"}

    max_bridges = args.get("max_bridges", DEFAULT_CONFIG["max_bridges"])
    search_limit = args.get("search_limit", DEFAULT_CONFIG["search_limit"])
    tag_limit = args.get("tag_limit", DEFAULT_CONFIG["tag_limit"])
    min_relevance = args.get("min_relevance", DEFAULT_CONFIG["min_relevance"])

    # ==============================
    # Step 1: Search both domains
    # ==============================
    half_timeout = start_time + (timeout * 0.4)

    domain_a = search_domain(concept_a, tools, search_limit, tag_limit, half_timeout)
    domain_b = search_domain(concept_b, tools, search_limit, tag_limit, start_time + (timeout * 0.7))

    if not domain_a.artifact_ids and not domain_b.artifact_ids:
        return {
            "success": True,
            "report": f"No artifacts found for either \"{concept_a}\" or \"{concept_b}\".",
            "bridges": [],
            "domain_a_size": 0,
            "domain_b_size": 0,
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    # ==============================
    # Step 1b: Combined semantic probe (finds embeddings near BOTH concepts)
    # ==============================
    semantic_search = tools.get("semantic_search")
    if semantic_search and time.time() - start_time < timeout * 0.8:
        try:
            combined_query = f"{concept_a} {concept_b}"
            result = semantic_search(query=combined_query, limit=search_limit)
            items = []
            if isinstance(result, dict):
                items = result.get("results", [])
            elif isinstance(result, list):
                items = result
            for item in items:
                art_id = item.get("id", "")
                if not art_id:
                    continue
                # Add to whichever domain doesn't have it (or both)
                if art_id not in domain_a.artifacts:
                    domain_a.artifact_ids.add(art_id)
                    domain_a.artifacts[art_id] = item
                if art_id not in domain_b.artifacts:
                    domain_b.artifact_ids.add(art_id)
                    domain_b.artifacts[art_id] = item
        except Exception:
            pass

    # ==============================
    # Step 2: Find bridges
    # ==============================
    bridges = find_bridges(domain_a, domain_b, min_relevance, max_bridges)

    # ==============================
    # Step 3: Report
    # ==============================
    report = format_report(concept_a, concept_b, domain_a, domain_b, bridges)

    bridges_output = [
        {
            "artifact_id": b.artifact_id,
            "artifact_type": b.artifact_type,
            "text": b.text[:300],
            "bridge_type": b.bridge_type,
            "relevance_a": b.relevance_a,
            "relevance_b": b.relevance_b,
            "balance": round(b.balance, 2),
            "score": b.score,
            "tags": b.tags,
        }
        for b in bridges
    ]

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "report": report,
        "bridges": bridges_output,
        "domain_a_size": len(domain_a.artifact_ids),
        "domain_b_size": len(domain_b.artifact_ids),
        "overlap_count": len(domain_a.artifact_ids & domain_b.artifact_ids),
        "bridges_found": len(bridges),
        "elapsed_seconds": elapsed,
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("connect_domains Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Usage: run({'concept_a': 'design', 'concept_b': 'security'}, tools, ctx)")
    print()
    print("Bridge types:")
    print("  - intersection: artifact appears in both domain searches")
    print("  - semantic_bridge: in one domain, textually relevant to the other")
    print("  - tag_bridge: tags span both domains")
    print()
    print("Scoring:")
    print("  - Combined relevance (0-0.35)")
    print("  - Balance (0-0.30): evenly relevant to both domains")
    print("  - Bridge type (0-0.20): intersection > tag > semantic")
    print("  - Text substance (0-0.15)")
