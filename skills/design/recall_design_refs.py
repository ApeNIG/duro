"""
Skill: recall_design_refs
Description: Query and present relevant design references for current task.
Version: 1.0.0
Tier: tested

Purpose: Surface relevant design references from the taste library to inform current design work.
Returns ranked list with stealable rules formatted as actionable brief.

Process:
1. Accept context (project type, style direction, pattern needed)
2. Query design_reference artifacts with semantic search
3. Return ranked list with stealable rules
4. Format as actionable brief for current design task

Usage:
    duro_run_skill(skill_name="recall_design_refs", args={
        "pattern": "dashboard",
        "style_tags": ["minimal", "dark"],
        "project_type": "saas_dashboard",
        "limit": 5
    })
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass


SKILL_META = {
    "name": "recall_design_refs",
    "description": "Query and present relevant design references for current task",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["get design refs", "show references", "design inspiration", "taste library"],
    "keywords": ["design", "reference", "recall", "taste", "library", "inspiration", "pattern"],
}

REQUIRES = ["duro_query_memory", "duro_semantic_search", "duro_get_artifact"]


# Project type to pattern mapping for relevance scoring
PROJECT_PATTERN_RELEVANCE = {
    "saas_dashboard": ["dashboard", "sidebar", "nav", "table", "card", "settings", "profile"],
    "landing_page": ["hero", "pricing", "nav", "card", "form", "landing"],
    "mobile_app": ["nav", "card", "profile", "feed", "onboarding", "modal", "notification"],
    "ecommerce": ["product", "card", "checkout", "nav", "pricing", "form"],
    "admin_panel": ["dashboard", "table", "sidebar", "form", "settings", "modal"],
}


@dataclass
class RankedReference:
    """A design reference with relevance score."""
    artifact_id: str
    product_name: str
    pattern: str
    url: str
    style_tags: List[str]
    why_it_works: List[str]
    stealable_rules: List[str]
    relevance_score: float
    match_reasons: List[str]


def calculate_relevance(
    ref: Dict,
    target_pattern: Optional[str],
    target_style_tags: Optional[List[str]],
    target_project_type: Optional[str]
) -> tuple:
    """
    Calculate relevance score for a reference.

    Returns: (score: float, reasons: List[str])
    """
    score = 0.0
    reasons = []

    ref_pattern = ref.get("pattern", "").lower()
    ref_style_tags = [t.lower() for t in ref.get("style_tags", [])]

    # Pattern match (high weight)
    if target_pattern:
        if ref_pattern == target_pattern.lower():
            score += 0.4
            reasons.append(f"Exact pattern match: {target_pattern}")
        elif target_pattern.lower() in ref_pattern or ref_pattern in target_pattern.lower():
            score += 0.2
            reasons.append(f"Partial pattern match: {ref_pattern}")

    # Style tag matches
    if target_style_tags:
        target_tags_lower = [t.lower() for t in target_style_tags]
        matching_tags = set(ref_style_tags) & set(target_tags_lower)
        if matching_tags:
            tag_score = len(matching_tags) / max(len(target_tags_lower), 1) * 0.3
            score += tag_score
            reasons.append(f"Style match: {', '.join(matching_tags)}")

    # Project type relevance
    if target_project_type:
        relevant_patterns = PROJECT_PATTERN_RELEVANCE.get(target_project_type.lower(), [])
        if ref_pattern in relevant_patterns:
            score += 0.2
            reasons.append(f"Relevant for {target_project_type}")

    # Bonus for having stealable rules
    if ref.get("stealable_rules") and len(ref["stealable_rules"]) >= 3:
        score += 0.1
        reasons.append("Has actionable rules")

    return min(score, 1.0), reasons


def format_as_brief(references: List[RankedReference], context: str = "") -> str:
    """Format references as an actionable design brief."""
    if not references:
        return "No matching design references found in the taste library."

    lines = [
        "# Design Reference Brief",
        "",
    ]

    if context:
        lines.extend([f"**Context:** {context}", ""])

    lines.extend([
        f"Found **{len(references)}** relevant references.",
        "",
        "---",
        "",
    ])

    for i, ref in enumerate(references, 1):
        lines.append(f"## {i}. {ref.product_name}")
        lines.append(f"**Pattern:** {ref.pattern} | **Score:** {ref.relevance_score:.0%}")

        if ref.url:
            lines.append(f"**URL:** {ref.url}")

        if ref.style_tags:
            lines.append(f"**Style:** {', '.join(ref.style_tags)}")

        if ref.match_reasons:
            lines.append(f"**Why relevant:** {'; '.join(ref.match_reasons)}")

        lines.append("")

        if ref.why_it_works:
            lines.append("**Why it works:**")
            for item in ref.why_it_works[:3]:
                lines.append(f"- {item}")
            lines.append("")

        if ref.stealable_rules:
            lines.append("**Stealable rules:**")
            for rule in ref.stealable_rules[:5]:
                lines.append(f"- {rule}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Summary of all stealable rules
    all_rules = []
    for ref in references[:3]:  # Top 3 only
        all_rules.extend(ref.stealable_rules)

    if all_rules:
        lines.append("## Key Rules to Apply")
        for rule in all_rules[:8]:
            lines.append(f"- {rule}")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query and present relevant design references for current task.

    Args:
        args: {
            pattern: str - Pattern type needed (optional)
            style_tags: List[str] - Style direction (optional)
            project_type: str - saas_dashboard, landing_page, mobile_app, etc. (optional)
            limit: int - Max references to return (default: 5)
            query: str - Natural language query for semantic search (optional)
            include_brief: bool - Generate formatted brief (default: True)
        }
        tools: {duro_query_memory, duro_semantic_search, duro_get_artifact}
        context: execution context

    Returns:
        {success, references, brief, count}
    """
    pattern = args.get("pattern")
    style_tags = args.get("style_tags", [])
    project_type = args.get("project_type")
    limit = args.get("limit", 5)
    query = args.get("query")
    include_brief = args.get("include_brief", True)

    references = []

    # Strategy 1: Use semantic search if query provided
    if query and tools.get("duro_semantic_search"):
        try:
            search_results = tools["duro_semantic_search"](
                query=query,
                artifact_type="design_reference",
                limit=limit * 2  # Get more, we'll re-rank
            )
            if search_results:
                for result in search_results:
                    if isinstance(result, dict):
                        references.append(result)
        except Exception:
            pass  # Fall through to query_memory

    # Strategy 2: Query by tags/pattern
    if not references and tools.get("duro_query_memory"):
        try:
            # Build search tags
            search_tags = []
            if pattern:
                search_tags.append(pattern.lower())
            if style_tags:
                search_tags.extend([t.lower() for t in style_tags[:3]])

            results = tools["duro_query_memory"](
                artifact_type="design_reference",
                tags=search_tags if search_tags else None,
                limit=limit * 3  # Get more for ranking
            )

            if results:
                for result in results:
                    if isinstance(result, dict):
                        references.append(result)

        except Exception as e:
            return {"success": False, "error": f"Failed to query memory: {str(e)}"}

    # Strategy 3: Get all design references if nothing else worked
    if not references and tools.get("duro_query_memory"):
        try:
            results = tools["duro_query_memory"](
                artifact_type="design_reference",
                limit=50  # Get all available
            )
            if results:
                for result in results:
                    if isinstance(result, dict):
                        references.append(result)
        except Exception:
            pass

    if not references:
        return {
            "success": True,
            "references": [],
            "count": 0,
            "brief": "No design references found in the taste library. Use capture_design_ref to add some.",
            "message": "Taste library is empty"
        }

    # Rank references by relevance
    ranked = []
    for ref in references:
        # Extract data from artifact
        data = ref.get("data", ref)
        artifact_id = ref.get("id", ref.get("artifact_id", ""))

        score, reasons = calculate_relevance(data, pattern, style_tags, project_type)

        ranked.append(RankedReference(
            artifact_id=artifact_id,
            product_name=data.get("product_name", "Unknown"),
            pattern=data.get("pattern", "unknown"),
            url=data.get("url", ""),
            style_tags=data.get("style_tags", []),
            why_it_works=data.get("why_it_works", []),
            stealable_rules=data.get("stealable_rules", []),
            relevance_score=score,
            match_reasons=reasons
        ))

    # Sort by relevance
    ranked.sort(key=lambda x: x.relevance_score, reverse=True)

    # Take top N
    top_refs = ranked[:limit]

    # Build context string
    context_parts = []
    if pattern:
        context_parts.append(f"Pattern: {pattern}")
    if style_tags:
        context_parts.append(f"Style: {', '.join(style_tags)}")
    if project_type:
        context_parts.append(f"Project: {project_type}")
    context_str = " | ".join(context_parts) if context_parts else "General search"

    # Generate brief if requested
    brief = format_as_brief(top_refs, context_str) if include_brief else ""

    # Convert to dict for return
    results_data = [
        {
            "artifact_id": r.artifact_id,
            "product_name": r.product_name,
            "pattern": r.pattern,
            "url": r.url,
            "style_tags": r.style_tags,
            "why_it_works": r.why_it_works,
            "stealable_rules": r.stealable_rules,
            "relevance_score": r.relevance_score,
            "match_reasons": r.match_reasons
        }
        for r in top_refs
    ]

    return {
        "success": True,
        "references": results_data,
        "count": len(top_refs),
        "total_available": len(references),
        "brief": brief,
        "search_context": context_str
    }


if __name__ == "__main__":
    print("recall_design_refs v1.0.0")
    print("=" * 50)
    print("Query and present relevant design references for current task")
    print("")
    print("Project types with pattern relevance:")
    for proj_type, patterns in PROJECT_PATTERN_RELEVANCE.items():
        print(f"  {proj_type}: {', '.join(patterns[:4])}...")
