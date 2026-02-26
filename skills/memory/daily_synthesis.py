"""
Skill: daily_synthesis
Description: Compound skill that chains reflection skills together for deeper insights
Version: 1.0.0
Tier: tested

This is a COMPOUND SKILL - it runs multiple skills in sequence and passes
outputs between them. The result is insights that no single skill could produce.

Flow:
1. graduate_logs → Promote today's learnings to permanent facts
2. emerge → Find patterns across all artifacts (including new facts)
3. idea_generation → Create actionable ideas from patterns
4. connect_domains → Explore suggested domain connections
5. Unified report → Everything in one place with clear actions

Why compound?
- Single skills see one slice of knowledge
- Compound skills see how slices connect
- The output of step 1 makes step 2 smarter
- The output of step 2 makes step 3 smarter
- etc.

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import time
from typing import Dict, List, Any, Optional
from datetime import datetime


# Skill metadata
SKILL_META = {
    "name": "daily_synthesis",
    "description": "Compound skill that chains reflection skills for deeper insights",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Built to close the skill compounding gap - skills should build on each other",
    "validated": "2026-02-26",
    "triggers": [
        "daily synthesis", "compound reflect", "deep reflection",
        "chain skills", "full analysis", "synthesize"
    ],
    "keywords": [
        "compound", "synthesis", "chain", "reflect", "emerge",
        "graduate", "ideas", "connect", "daily", "session-end"
    ],
    "phase": "4.0",
    "compound": True,  # Marks this as a compound skill
    "chains": ["graduate_logs", "emerge", "idea_generation", "connect_domains"],
}

# Default configuration
DEFAULT_CONFIG = {
    "days_back": 1,           # How far back to look
    "auto_promote": True,     # Actually promote learnings (not just preview)
    "max_patterns": 5,        # Patterns to surface from emerge
    "max_ideas": 5,           # Ideas to generate
    "max_connections": 2,     # Domain connections to explore
    "dry_run": False,         # If True, don't make changes
}

# Required capabilities
REQUIRES = ["run_skill", "query_memory"]

# Default timeout (longer because we run multiple skills)
DEFAULT_TIMEOUT = 180


def run_child_skill(
    skill_name: str,
    args: Dict,
    tools: Dict,
    timeout_remaining: float
) -> Dict[str, Any]:
    """
    Run a child skill and return its results.
    """
    run_skill = tools.get("run_skill")
    if not run_skill:
        return {"success": False, "error": "run_skill tool not available"}

    try:
        result = run_skill(skill_name=skill_name, args=args)
        return {
            "success": True,
            "skill": skill_name,
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "skill": skill_name,
            "error": str(e)
        }


def extract_domain_suggestions(idea_result: Dict) -> List[tuple]:
    """
    Extract domain connection suggestions from idea_generation output.
    Returns list of (domain_a, domain_b) tuples.
    """
    connections = []

    # Parse the result to find connection suggestions
    if isinstance(idea_result, dict):
        report = idea_result.get("report", "")
        # Look for "Explore connection: X ↔ Y" patterns
        import re
        matches = re.findall(r'"([^"]+)"\s*[↔←→]\s*"([^"]+)"', report)
        connections.extend(matches)

        # Also check ideas list
        ideas = idea_result.get("ideas", [])
        for idea in ideas:
            if isinstance(idea, dict) and "connection" in idea.get("type", "").lower():
                domain_a = idea.get("domain_a", "")
                domain_b = idea.get("domain_b", "")
                if domain_a and domain_b:
                    connections.append((domain_a, domain_b))

    return connections[:3]  # Limit to 3


def format_compound_report(
    graduate_result: Dict,
    emerge_result: Dict,
    idea_result: Dict,
    connection_results: List[Dict],
    elapsed: float
) -> str:
    """
    Create a unified report from all skill outputs.
    """
    lines = []
    lines.append("# Daily Synthesis Report")
    lines.append(f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC*")
    lines.append("")

    # Section 1: Graduated Learnings
    lines.append("## 1. Learnings Promoted")
    if graduate_result.get("success"):
        result = graduate_result.get("result", {})
        promoted = result.get("promoted_count", 0)
        if isinstance(result, str):
            # Parse from report string
            if "Created:" in result:
                lines.append(result.split("### ")[0])  # Just the summary
            else:
                lines.append(f"Skill completed. Check output for details.")
        else:
            lines.append(f"**{promoted}** learnings promoted to permanent facts")
    else:
        lines.append(f"⚠️ Could not run: {graduate_result.get('error', 'unknown error')}")
    lines.append("")

    # Section 2: Patterns Found
    lines.append("## 2. Patterns Discovered")
    if emerge_result.get("success"):
        result = emerge_result.get("result", {})
        if isinstance(result, str):
            # Extract pattern names from report
            pattern_lines = [l for l in result.split("\n") if l.startswith("### ")]
            if pattern_lines:
                for p in pattern_lines[:5]:
                    name = p.replace("### ", "").split("**")[0].strip()
                    lines.append(f"- {name}")
            else:
                lines.append("Patterns found - see full emerge report")
        elif isinstance(result, dict):
            patterns = result.get("patterns", [])
            if patterns:
                for p in patterns[:5]:
                    name = p.get("name", "unnamed")
                    score = p.get("score", 0)
                    lines.append(f"- **{name}** ({score:.0%} signal)")
            else:
                lines.append("No strong patterns detected")
    else:
        lines.append(f"⚠️ Could not run: {emerge_result.get('error', 'unknown error')}")
    lines.append("")

    # Section 3: Actionable Ideas
    lines.append("## 3. Ideas to Act On")
    if idea_result.get("success"):
        result = idea_result.get("result", {})
        if isinstance(result, str):
            # Extract key ideas from report
            if "###" in result:
                sections = result.split("###")
                for s in sections[1:4]:  # First 3 sections
                    title = s.split("\n")[0].strip()
                    if title:
                        lines.append(f"- {title}")
            else:
                lines.append("Ideas generated - see full report")
        elif isinstance(result, dict):
            ideas = result.get("ideas", [])
            for idea in ideas[:5]:
                if isinstance(idea, dict):
                    title = idea.get("title", idea.get("description", ""))[:80]
                    lines.append(f"- {title}")
    else:
        lines.append(f"⚠️ Could not run: {idea_result.get('error', 'unknown error')}")
    lines.append("")

    # Section 4: Domain Connections
    lines.append("## 4. Connections Explored")
    if connection_results:
        for conn in connection_results:
            if conn.get("success"):
                result = conn.get("result", {})
                domains = conn.get("domains", ("?", "?"))
                lines.append(f"**{domains[0]} ↔ {domains[1]}**")
                if isinstance(result, str) and "Direct Connections" in result:
                    # Count connections
                    direct = result.count("**[")
                    lines.append(f"  Found {direct} connections")
                elif isinstance(result, dict):
                    direct = len(result.get("direct_connections", []))
                    bridges = len(result.get("bridges", []))
                    lines.append(f"  {direct} direct, {bridges} bridges")
            else:
                lines.append(f"⚠️ Connection failed: {conn.get('error', '')}")
        lines.append("")
    else:
        lines.append("No domain connections to explore (none suggested)")
        lines.append("")

    # Section 5: Quick Actions
    lines.append("## Next Actions")
    lines.append("Based on this synthesis:")

    actions = []

    # Action from patterns
    if emerge_result.get("success"):
        result = emerge_result.get("result", {})
        if isinstance(result, dict):
            patterns = result.get("patterns", [])
            high_unart = [p for p in patterns if p.get("unarticulated_ratio", 0) > 0.7]
            if high_unart:
                actions.append(f"📝 Name the '{high_unart[0].get('name', 'top')}' pattern as a formal concept")

    # Action from ideas
    if idea_result.get("success"):
        result = idea_result.get("result", {})
        if isinstance(result, dict) and result.get("ideas"):
            actions.append("💡 Review generated ideas and pick one to implement")

    # Default actions
    if not actions:
        actions.append("✅ Knowledge base is healthy - no urgent actions")

    for action in actions[:3]:
        lines.append(f"- {action}")

    lines.append("")
    lines.append(f"---")
    lines.append(f"*Compound synthesis completed in {elapsed:.1f}s*")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main compound skill execution.

    Runs 4 skills in sequence, passing insights between them:
    1. graduate_logs - Promote learnings
    2. emerge - Find patterns
    3. idea_generation - Create ideas
    4. connect_domains - Explore connections

    Args:
        args: {
            days_back: int (default 1)
            auto_promote: bool (default True)
            max_patterns: int (default 5)
            max_ideas: int (default 5)
            max_connections: int (default 2)
            dry_run: bool (default False)
            skip_graduate: bool (default False) - Skip if already graduated
            skip_connections: bool (default False) - Skip domain exploration
        }
        tools: {
            run_skill: callable - Run child skills
            query_memory: callable - For context
        }
        context: {run_id, timeout}

    Returns:
        {
            success: bool,
            report: str - Unified report
            steps_completed: int
            skills_run: List[str]
            insights_chained: int - Ideas that built on previous steps
            elapsed_seconds: float
        }
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    # Parse args
    days_back = args.get("days_back", DEFAULT_CONFIG["days_back"])
    auto_promote = args.get("auto_promote", DEFAULT_CONFIG["auto_promote"])
    max_patterns = args.get("max_patterns", DEFAULT_CONFIG["max_patterns"])
    max_ideas = args.get("max_ideas", DEFAULT_CONFIG["max_ideas"])
    max_connections = args.get("max_connections", DEFAULT_CONFIG["max_connections"])
    dry_run = args.get("dry_run", DEFAULT_CONFIG["dry_run"])
    skip_graduate = args.get("skip_graduate", False)
    skip_connections = args.get("skip_connections", False)

    run_skill = tools.get("run_skill")
    if not run_skill:
        return {"success": False, "error": "run_skill capability required for compound skills"}

    skills_run = []
    steps_completed = 0

    # ================================================
    # Step 1: Graduate Logs → Promote learnings to facts
    # ================================================
    graduate_result = {"success": False, "error": "skipped"}

    if not skip_graduate:
        remaining = timeout - (time.time() - start_time)
        if remaining > 30:
            graduate_result = run_child_skill(
                "graduate_logs",
                {
                    "days_back": days_back,
                    "auto_promote": auto_promote and not dry_run,
                    "dry_run": dry_run,
                },
                tools,
                remaining
            )
            skills_run.append("graduate_logs")
            if graduate_result.get("success"):
                steps_completed += 1

    # ================================================
    # Step 2: Emerge → Find patterns (now including new facts)
    # ================================================
    emerge_result = {"success": False, "error": "timeout"}

    remaining = timeout - (time.time() - start_time)
    if remaining > 30:
        emerge_result = run_child_skill(
            "emerge",
            {
                "days_back": days_back * 7,  # Look wider for patterns
                "max_patterns": max_patterns,
            },
            tools,
            remaining
        )
        skills_run.append("emerge")
        if emerge_result.get("success"):
            steps_completed += 1

    # ================================================
    # Step 3: Idea Generation → Create ideas from patterns
    # ================================================
    idea_result = {"success": False, "error": "timeout"}

    remaining = timeout - (time.time() - start_time)
    if remaining > 30:
        idea_result = run_child_skill(
            "idea_generation",
            {
                "max_ideas": max_ideas,
            },
            tools,
            remaining
        )
        skills_run.append("idea_generation")
        if idea_result.get("success"):
            steps_completed += 1

    # ================================================
    # Step 4: Connect Domains → Explore suggested connections
    # ================================================
    connection_results = []

    if not skip_connections:
        # Extract domain suggestions from idea_generation
        domain_pairs = extract_domain_suggestions(idea_result.get("result", {}))

        # Also add connections from emerge patterns
        emerge_patterns = emerge_result.get("result", {})
        if isinstance(emerge_patterns, dict):
            for pattern in emerge_patterns.get("patterns", [])[:2]:
                tags = pattern.get("tags", [])
                if len(tags) >= 2:
                    domain_pairs.append((tags[0], tags[1]))

        # Run connect_domains for top pairs
        for domain_a, domain_b in domain_pairs[:max_connections]:
            remaining = timeout - (time.time() - start_time)
            if remaining < 15:
                break

            conn_result = run_child_skill(
                "connect_domains",
                {
                    "concept_a": domain_a,
                    "concept_b": domain_b,
                },
                tools,
                remaining
            )
            conn_result["domains"] = (domain_a, domain_b)
            connection_results.append(conn_result)
            skills_run.append(f"connect_domains({domain_a}↔{domain_b})")
            if conn_result.get("success"):
                steps_completed += 1

    # ================================================
    # Generate unified report
    # ================================================
    elapsed = time.time() - start_time

    report = format_compound_report(
        graduate_result,
        emerge_result,
        idea_result,
        connection_results,
        elapsed
    )

    return {
        "success": steps_completed >= 2,  # At least 2 steps must succeed
        "report": report,
        "steps_completed": steps_completed,
        "skills_run": skills_run,
        "elapsed_seconds": round(elapsed, 2),
        "child_results": {
            "graduate_logs": graduate_result,
            "emerge": emerge_result,
            "idea_generation": idea_result,
            "connect_domains": connection_results,
        }
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("daily_synthesis - Compound Reflection Skill")
    print("=" * 50)
    print()
    print("This skill CHAINS multiple skills together:")
    print()
    print("  1. graduate_logs")
    print("     └─ Promotes learnings to permanent facts")
    print("         │")
    print("         ▼")
    print("  2. emerge")
    print("     └─ Finds patterns (now sees new facts)")
    print("         │")
    print("         ▼")
    print("  3. idea_generation")
    print("     └─ Creates ideas from patterns")
    print("         │")
    print("         ▼")
    print("  4. connect_domains")
    print("     └─ Explores suggested connections")
    print("         │")
    print("         ▼")
    print("  [Unified Report]")
    print()
    print("Each step builds on the previous.")
    print("This is compound intelligence.")
