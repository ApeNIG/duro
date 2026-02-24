"""
Skill: ghost
Description: Answer questions the way the user would, based on their documented history
Version: 1.0.0
Tier: tested

Synthesizes the user's background knowledge, decisions, and biases to generate
responses that sound authentically like them.

Inspired by: Podcast discussion of /ghost command for Obsidian + Claude

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


# Skill metadata
SKILL_META = {
    "name": "ghost",
    "description": "Answer questions the way the user would, based on their documented history",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Podcast - Obsidian + Claude Code integration",
    "validated": "2026-02-24",
    "triggers": ["ghost", "answer as me", "how would I answer", "in my voice"],
    "keywords": [
        "ghost", "persona", "voice", "style", "answer", "synthesize",
        "authentic", "me", "user", "perspective", "opinion"
    ],
    "phase": "4.0",
}

# Required capabilities
REQUIRES = ["query_memory", "semantic_search"]

# Default configuration
DEFAULT_CONFIG = {
    "max_decisions": 20,
    "max_facts": 30,
    "max_logs": 10,
}


def extract_user_voice(artifacts: List[Dict]) -> Dict[str, Any]:
    """Extract user's voice characteristics from artifacts."""

    voice_profile = {
        "values": [],           # Core values from decisions
        "biases": [],           # Recurring preferences
        "expertise": [],        # Domains of knowledge
        "style_markers": [],    # Writing style indicators
        "strong_opinions": [],  # High-confidence stances
    }

    # Analyze decisions for values and preferences
    for art in artifacts:
        art_type = art.get("type") or art.get("artifact_type", "")
        data = art.get("data", art)

        if art_type == "decision":
            rationale = data.get("rationale", "")
            decision = data.get("decision", "")

            # Extract value indicators from rationale
            value_keywords = ["important", "priority", "prefer", "value", "believe", "always", "never"]
            for keyword in value_keywords:
                if keyword in rationale.lower():
                    # Capture the context around the value statement
                    voice_profile["values"].append(f"{decision[:50]}... ({keyword} in rationale)")
                    break

            # Track alternatives rejected (shows preferences)
            alternatives = data.get("alternatives", [])
            if alternatives:
                voice_profile["biases"].append(f"Chose '{decision[:30]}' over {alternatives}")

        elif art_type == "fact":
            confidence = data.get("confidence", 0.5)
            claim = data.get("claim", "")
            tags = art.get("tags", [])

            # High-confidence facts show strong opinions (lowered to 0.7)
            if confidence >= 0.7 and claim:
                voice_profile["strong_opinions"].append(claim)

            # Tags reveal expertise areas
            voice_profile["expertise"].extend(tags)

    # Deduplicate expertise
    voice_profile["expertise"] = list(set(voice_profile["expertise"]))[:10]

    return voice_profile


def build_ghost_response(
    question: str,
    voice_profile: Dict[str, Any],
    relevant_artifacts: List[Dict]
) -> str:
    """Build a response in the user's voice."""

    response_parts = []

    # Opening - acknowledge the question
    response_parts.append(f"**Question**: {question}\n")
    response_parts.append("**How I would answer** (based on my documented history):\n")

    # Find directly relevant evidence
    relevant_claims = []
    for art in relevant_artifacts:
        data = art.get("data", {})
        # Extract text from nested data structure or top-level
        claim = (
            data.get("decision") or
            data.get("claim") or
            data.get("rationale") or
            art.get("title") or
            art.get("decision") or
            art.get("claim") or
            ""
        )
        if claim:
            relevant_claims.append(claim[:100])

    if relevant_claims:
        response_parts.append("\n*Evidence from my history:*")
        for claim in relevant_claims[:5]:
            response_parts.append(f"- {claim}")

    # Add voice characteristics
    if voice_profile["strong_opinions"]:
        response_parts.append("\n*My documented strong positions:*")
        for opinion in voice_profile["strong_opinions"][:3]:
            response_parts.append(f"- {opinion[:80]}...")

    if voice_profile["expertise"]:
        response_parts.append(f"\n*My areas of expertise:* {', '.join(voice_profile['expertise'][:5])}")

    # Synthesis note
    response_parts.append("\n---")
    response_parts.append("*This is a synthesis of documented decisions, facts, and patterns.*")
    response_parts.append("*Use this as a starting point for your actual response.*")

    return "\n".join(response_parts)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            question: str - The question to answer as the user
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
            response: str,
            voice_profile: dict,
            evidence_count: int,
        }
    """
    question = args.get("question", "")
    domain = args.get("domain")

    if not question:
        return {"success": False, "error": "Question is required"}

    query_memory = tools.get("query_memory")
    semantic_search = tools.get("semantic_search")

    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    # Gather artifacts for voice profile
    all_artifacts = []

    # Get decisions (show values and preferences)
    try:
        decisions = query_memory(artifact_type="decision", limit=DEFAULT_CONFIG["max_decisions"])
        if isinstance(decisions, list):
            for d in decisions:
                d["artifact_type"] = "decision"
            all_artifacts.extend(decisions)
    except Exception:
        pass

    # Get high-confidence facts (show strong opinions)
    try:
        facts = query_memory(artifact_type="fact", limit=DEFAULT_CONFIG["max_facts"])
        if isinstance(facts, list):
            for f in facts:
                f["artifact_type"] = "fact"
            all_artifacts.extend(facts)
    except Exception:
        pass

    # Build voice profile
    voice_profile = extract_user_voice(all_artifacts)

    # Find relevant artifacts for this specific question
    relevant_artifacts = []
    if semantic_search:
        try:
            search_query = question
            if domain:
                search_query = f"{domain}: {question}"

            results = semantic_search(query=search_query, limit=10)
            if isinstance(results, dict):
                relevant_artifacts = results.get("results", [])
            elif isinstance(results, list):
                relevant_artifacts = results
        except Exception:
            pass

    # Build ghost response
    response = build_ghost_response(question, voice_profile, relevant_artifacts)

    return {
        "success": True,
        "response": response,
        "voice_profile": {
            "values_found": len(voice_profile["values"]),
            "expertise_areas": voice_profile["expertise"],
            "strong_opinions_count": len(voice_profile["strong_opinions"]),
        },
        "evidence_count": len(relevant_artifacts),
        "total_artifacts_analyzed": len(all_artifacts),
    }


# CLI mode
if __name__ == "__main__":
    print("ghost Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Purpose: Answer questions the way YOU would, based on")
    print("your documented decisions, facts, and patterns.")
    print()
    print("Usage:")
    print("  Run via MCP: duro_run_skill('ghost', {question: '...'})")
    print()
    print("Example questions:")
    print("  - Should I use TypeScript or JavaScript?")
    print("  - What's my stance on microservices?")
    print("  - How do I typically handle error handling?")
