"""
Skill: plan_deepen
Description: Research-driven plan enhancement with parallel sub-agents
Version: 1.0.0
Tier: tested

Inspired by compound-engineering plugin's /deepen-plan command.
Spawns 4 parallel research sub-agents to gather context before complex tasks:

1. framework_docs_researcher - Fetch current framework documentation (uses Context7)
2. learnings_researcher - Search past learnings, decisions, incidents
3. best_practices_researcher - Gather external best practices
4. codebase_analyzer - Analyze relevant code patterns and history

This front-loads research to make execution more accurate.

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass


# Skill metadata
SKILL_META = {
    "name": "plan_deepen",
    "description": "Research-driven plan enhancement with 4 parallel research sub-agents",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Inspired by compound-engineering /deepen-plan command",
    "validated": "2026-03-05",
    "triggers": [
        "deepen plan", "research before", "gather context",
        "pre-task research", "enhance plan"
    ],
    "keywords": [
        "plan", "deepen", "research", "context", "parallel",
        "framework", "learnings", "best practices", "codebase"
    ],
    "phase": "4.0",
    "compound": True,
    "parallel": True,
    "model_tier": "advanced",  # Planning needs complex reasoning
    "researchers": [
        "framework_docs_researcher",
        "learnings_researcher",
        "best_practices_researcher",
        "codebase_analyzer"
    ],
}

# Required capabilities
REQUIRES = ["query_memory", "semantic_search", "web_search", "read_file"]

# Default timeout
DEFAULT_TIMEOUT = 180


@dataclass
class ResearchFinding:
    """A single research finding"""
    researcher: str
    category: str  # "framework", "learning", "best_practice", "codebase"
    title: str
    content: str
    source: str
    relevance: float  # 0-1
    actionable: bool


@dataclass
class ResearcherResult:
    """Result from a single researcher"""
    researcher: str
    findings: List[ResearchFinding]
    summary: str
    elapsed_ms: int
    success: bool
    error: Optional[str] = None


# ============================================================
# RESEARCHER FUNCTIONS - Each gathers different context
# ============================================================

def research_framework_docs(
    task_context: Dict,
    tools: Dict
) -> ResearcherResult:
    """
    Framework Docs Researcher - Fetch current framework documentation

    Uses Context7 MCP if available, falls back to web search.
    Focuses on frameworks mentioned in the task or detected in codebase.
    """
    start = time.time()
    findings = []

    task = task_context.get("task", "")
    frameworks = task_context.get("frameworks", [])
    tech_stack = task_context.get("tech_stack", [])

    # Combine detected frameworks
    all_frameworks = set(frameworks + tech_stack)

    # Common framework keywords to detect
    framework_keywords = {
        "react": "React",
        "next": "Next.js",
        "vue": "Vue.js",
        "express": "Express.js",
        "django": "Django",
        "fastapi": "FastAPI",
        "rails": "Ruby on Rails",
        "tailwind": "Tailwind CSS",
        "postgres": "PostgreSQL",
        "supabase": "Supabase",
    }

    # Detect frameworks from task description
    task_lower = task.lower()
    for keyword, framework in framework_keywords.items():
        if keyword in task_lower:
            all_frameworks.add(framework)

    # Try to use Context7 MCP if available
    context7_fetch = tools.get("context7_get_docs")
    web_search = tools.get("web_search")

    for framework in list(all_frameworks)[:3]:  # Limit to top 3
        try:
            if context7_fetch:
                # Use Context7 for real-time docs
                docs = context7_fetch(framework)
                if docs:
                    findings.append(ResearchFinding(
                        researcher="framework_docs_researcher",
                        category="framework",
                        title=f"{framework} Documentation",
                        content=docs[:500] + "..." if len(docs) > 500 else docs,
                        source="Context7 MCP",
                        relevance=0.9,
                        actionable=True
                    ))
            elif web_search:
                # Fallback to web search
                results = web_search(f"{framework} documentation best practices 2026")
                if results:
                    findings.append(ResearchFinding(
                        researcher="framework_docs_researcher",
                        category="framework",
                        title=f"{framework} Best Practices",
                        content=str(results)[:500],
                        source="Web Search",
                        relevance=0.7,
                        actionable=True
                    ))
        except Exception as e:
            pass  # Skip failed lookups

    # If no frameworks detected, note it
    if not findings:
        findings.append(ResearchFinding(
            researcher="framework_docs_researcher",
            category="framework",
            title="No specific frameworks detected",
            content="Task doesn't mention specific frameworks. Consider specifying tech stack.",
            source="Analysis",
            relevance=0.3,
            actionable=False
        ))

    elapsed = int((time.time() - start) * 1000)

    summary = f"Found documentation for {len(all_frameworks)} frameworks"
    if findings:
        summary += f": {', '.join(all_frameworks)}"

    return ResearcherResult(
        researcher="framework_docs_researcher",
        findings=findings,
        summary=summary,
        elapsed_ms=elapsed,
        success=True
    )


def research_learnings(
    task_context: Dict,
    tools: Dict
) -> ResearcherResult:
    """
    Learnings Researcher - Search past learnings, decisions, and incidents

    Queries Duro's memory for:
    - Related facts
    - Past decisions on similar tasks
    - Relevant incidents/RCAs
    """
    start = time.time()
    findings = []

    task = task_context.get("task", "")
    keywords = task_context.get("keywords", [])

    # Use semantic search if available
    semantic_search = tools.get("semantic_search")
    query_memory = tools.get("query_memory")

    # Search for related facts
    if semantic_search:
        try:
            results = semantic_search(query=task, artifact_type="fact", limit=5)
            if results:
                for r in results.get("results", [])[:3]:
                    findings.append(ResearchFinding(
                        researcher="learnings_researcher",
                        category="learning",
                        title="Related Fact",
                        content=r.get("claim", r.get("content", "")),
                        source=f"fact:{r.get('id', 'unknown')}",
                        relevance=r.get("score", 0.5),
                        actionable=True
                    ))
        except Exception:
            pass

    # Search for related decisions
    if semantic_search:
        try:
            results = semantic_search(query=task, artifact_type="decision", limit=5)
            if results:
                for r in results.get("results", [])[:3]:
                    findings.append(ResearchFinding(
                        researcher="learnings_researcher",
                        category="learning",
                        title="Related Decision",
                        content=r.get("decision", r.get("content", "")),
                        source=f"decision:{r.get('id', 'unknown')}",
                        relevance=r.get("score", 0.5),
                        actionable=True
                    ))
        except Exception:
            pass

    # Search for related incidents
    if query_memory:
        try:
            results = query_memory(artifact_type="incident_rca", limit=3)
            if results:
                for r in results[:2]:
                    if any(kw.lower() in str(r).lower() for kw in keywords):
                        findings.append(ResearchFinding(
                            researcher="learnings_researcher",
                            category="learning",
                            title="Related Incident",
                            content=r.get("symptom", "") + " → " + r.get("fix", ""),
                            source=f"incident:{r.get('id', 'unknown')}",
                            relevance=0.8,
                            actionable=True
                        ))
        except Exception:
            pass

    elapsed = int((time.time() - start) * 1000)

    return ResearcherResult(
        researcher="learnings_researcher",
        findings=findings,
        summary=f"Found {len(findings)} related learnings from memory",
        elapsed_ms=elapsed,
        success=True
    )


def research_best_practices(
    task_context: Dict,
    tools: Dict
) -> ResearcherResult:
    """
    Best Practices Researcher - Gather external best practices

    Searches for:
    - Industry best practices
    - Common patterns for the task type
    - Anti-patterns to avoid
    """
    start = time.time()
    findings = []

    task = task_context.get("task", "")
    task_type = task_context.get("task_type", "implementation")

    # Map task types to best practice queries
    practice_queries = {
        "design": "UI UX design best practices accessibility",
        "api": "REST API design best practices error handling",
        "database": "database schema design best practices normalization",
        "authentication": "authentication security best practices OWASP",
        "testing": "software testing best practices coverage strategies",
        "refactoring": "code refactoring best practices patterns",
        "performance": "web performance optimization best practices",
        "implementation": "software engineering best practices clean code",
    }

    query = practice_queries.get(task_type, practice_queries["implementation"])

    web_search = tools.get("web_search")

    if web_search:
        try:
            results = web_search(query)
            if results:
                # Parse results
                if isinstance(results, list):
                    for r in results[:3]:
                        findings.append(ResearchFinding(
                            researcher="best_practices_researcher",
                            category="best_practice",
                            title=r.get("title", "Best Practice"),
                            content=r.get("snippet", str(r))[:300],
                            source=r.get("url", "Web"),
                            relevance=0.7,
                            actionable=True
                        ))
                elif isinstance(results, str):
                    findings.append(ResearchFinding(
                        researcher="best_practices_researcher",
                        category="best_practice",
                        title=f"Best Practices for {task_type}",
                        content=results[:500],
                        source="Web Search",
                        relevance=0.7,
                        actionable=True
                    ))
        except Exception:
            pass

    # Add common best practices based on task type
    common_practices = {
        "design": [
            "Use consistent spacing (8px grid)",
            "Ensure WCAG AA contrast ratios",
            "Mobile-first responsive design",
        ],
        "api": [
            "Use proper HTTP status codes",
            "Implement rate limiting",
            "Version your API endpoints",
        ],
        "authentication": [
            "Never store passwords in plain text",
            "Use secure session management",
            "Implement MFA where possible",
        ],
    }

    if task_type in common_practices:
        for practice in common_practices[task_type]:
            findings.append(ResearchFinding(
                researcher="best_practices_researcher",
                category="best_practice",
                title="Common Best Practice",
                content=practice,
                source="Industry Standard",
                relevance=0.8,
                actionable=True
            ))

    elapsed = int((time.time() - start) * 1000)

    return ResearcherResult(
        researcher="best_practices_researcher",
        findings=findings,
        summary=f"Found {len(findings)} best practices for {task_type}",
        elapsed_ms=elapsed,
        success=True
    )


def analyze_codebase(
    task_context: Dict,
    tools: Dict
) -> ResearcherResult:
    """
    Codebase Analyzer - Analyze relevant code patterns and history

    Looks at:
    - Existing patterns in the codebase
    - Recent changes to related files
    - Code conventions being used
    """
    start = time.time()
    findings = []

    task = task_context.get("task", "")
    files = task_context.get("related_files", [])
    project_path = task_context.get("project_path", "")

    read_file = tools.get("read_file")
    query_changes = tools.get("query_recent_changes")

    # Analyze related files for patterns
    if read_file and files:
        for file_path in files[:3]:
            try:
                content = read_file(file_path)
                if content:
                    # Extract patterns (simplified)
                    patterns = []
                    if "useState" in content:
                        patterns.append("React hooks pattern")
                    if "async/await" in content:
                        patterns.append("Async/await pattern")
                    if "try {" in content or "try:" in content:
                        patterns.append("Error handling with try/catch")
                    if "@dataclass" in content:
                        patterns.append("Python dataclasses")

                    if patterns:
                        findings.append(ResearchFinding(
                            researcher="codebase_analyzer",
                            category="codebase",
                            title=f"Patterns in {file_path.split('/')[-1]}",
                            content=", ".join(patterns),
                            source=file_path,
                            relevance=0.85,
                            actionable=True
                        ))
            except Exception:
                pass

    # Check recent changes for context
    if query_changes:
        try:
            changes = query_changes(hours=48, limit=10)
            if changes:
                relevant_changes = [
                    c for c in changes
                    if any(kw in str(c).lower() for kw in task.lower().split()[:3])
                ]
                if relevant_changes:
                    findings.append(ResearchFinding(
                        researcher="codebase_analyzer",
                        category="codebase",
                        title="Recent Related Changes (48h)",
                        content=str(relevant_changes[:3]),
                        source="Change Ledger",
                        relevance=0.9,
                        actionable=True
                    ))
        except Exception:
            pass

    elapsed = int((time.time() - start) * 1000)

    return ResearcherResult(
        researcher="codebase_analyzer",
        findings=findings,
        summary=f"Analyzed {len(files)} files, found {len(findings)} patterns",
        elapsed_ms=elapsed,
        success=True
    )


# ============================================================
# MAIN EXECUTION - Runs all researchers in parallel
# ============================================================

RESEARCHERS = {
    "framework_docs_researcher": research_framework_docs,
    "learnings_researcher": research_learnings,
    "best_practices_researcher": research_best_practices,
    "codebase_analyzer": analyze_codebase,
}


def format_research_report(
    results: List[ResearcherResult],
    task: str,
    elapsed: float
) -> str:
    """Create a consolidated research report."""
    lines = []
    lines.append("# Plan Deepening Research Report")
    lines.append(f"*{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC | {elapsed:.1f}s total*")
    lines.append("")
    lines.append(f"**Task:** {task[:100]}{'...' if len(task) > 100 else ''}")
    lines.append("")

    # Summary table
    lines.append("## Research Summary")
    lines.append("| Researcher | Findings | Time |")
    lines.append("|------------|----------|------|")
    for r in results:
        status = f"{len(r.findings)} findings" if r.success else "ERROR"
        lines.append(f"| {r.researcher} | {status} | {r.elapsed_ms}ms |")
    lines.append("")

    # Group findings by category
    all_findings: Dict[str, List[ResearchFinding]] = {
        "framework": [],
        "learning": [],
        "best_practice": [],
        "codebase": [],
    }

    for r in results:
        for f in r.findings:
            if f.category in all_findings:
                all_findings[f.category].append(f)

    # Framework Documentation
    if all_findings["framework"]:
        lines.append("## Framework Context")
        for f in all_findings["framework"]:
            lines.append(f"### {f.title}")
            lines.append(f"{f.content}")
            lines.append(f"*Source: {f.source}*")
            lines.append("")

    # Past Learnings
    if all_findings["learning"]:
        lines.append("## Relevant Learnings from Memory")
        for f in all_findings["learning"]:
            lines.append(f"- **{f.title}**: {f.content}")
            lines.append(f"  _{f.source}_")
        lines.append("")

    # Best Practices
    if all_findings["best_practice"]:
        lines.append("## Best Practices to Follow")
        for f in all_findings["best_practice"]:
            if f.actionable:
                lines.append(f"- {f.content}")
        lines.append("")

    # Codebase Patterns
    if all_findings["codebase"]:
        lines.append("## Codebase Patterns")
        for f in all_findings["codebase"]:
            lines.append(f"- **{f.title}**: {f.content}")
        lines.append("")

    # Actionable recommendations
    lines.append("## Recommendations")
    actionable = [f for cat in all_findings.values() for f in cat if f.actionable]
    if actionable:
        lines.append("Based on research, consider:")
        for i, f in enumerate(actionable[:5], 1):
            lines.append(f"{i}. {f.content[:100]}")
    else:
        lines.append("- No specific recommendations from research")

    lines.append("")
    lines.append("---")
    total_findings = sum(len(r.findings) for r in results)
    lines.append(f"*{total_findings} total findings from {len(results)} researchers*")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main plan deepening execution.

    Runs 4 research sub-agents in parallel to gather context before complex tasks.

    Args:
        args: {
            task: str - The task to research
            task_type: str - Type of task (design, api, auth, etc.)
            frameworks: List[str] - Known frameworks in use
            tech_stack: List[str] - Known tech stack
            related_files: List[str] - Files related to the task
            project_path: str - Path to the project
            keywords: List[str] - Additional keywords for search
            skip_researchers: List[str] - Researchers to skip
            max_workers: int - Parallel threads (default 4)
        }
        tools: {
            semantic_search: callable - Duro semantic search
            query_memory: callable - Duro memory query
            web_search: callable - Web search
            read_file: callable - File reader
            query_recent_changes: callable - Change ledger query
            context7_get_docs: callable - Context7 MCP (optional)
        }
        context: {run_id, timeout}

    Returns:
        {
            success: bool,
            report: str - Consolidated research report
            findings_count: int
            framework_findings: int
            learning_findings: int
            best_practice_findings: int
            codebase_findings: int
            researcher_results: List[dict]
            elapsed_seconds: float
        }
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    # Parse args
    task = args.get("task", "")
    if not task:
        return {"success": False, "error": "Task description required"}

    task_context = {
        "task": task,
        "task_type": args.get("task_type", "implementation"),
        "frameworks": args.get("frameworks", []),
        "tech_stack": args.get("tech_stack", []),
        "related_files": args.get("related_files", []),
        "project_path": args.get("project_path", ""),
        "keywords": args.get("keywords", task.split()[:5]),
    }

    skip_researchers = args.get("skip_researchers", [])
    max_workers = args.get("max_workers", 4)

    # Determine which researchers to run
    researchers_to_run = {
        name: func for name, func in RESEARCHERS.items()
        if name not in skip_researchers
    }

    if not researchers_to_run:
        return {"success": False, "error": "No researchers to run (all skipped)"}

    # Run researchers in parallel
    results: List[ResearcherResult] = []

    with ThreadPoolExecutor(max_workers=min(max_workers, len(researchers_to_run))) as executor:
        futures = {
            executor.submit(func, task_context, tools): name
            for name, func in researchers_to_run.items()
        }

        for future in as_completed(futures, timeout=timeout):
            researcher_name = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append(ResearcherResult(
                    researcher=researcher_name,
                    findings=[],
                    summary=f"Error: {str(e)}",
                    elapsed_ms=0,
                    success=False,
                    error=str(e)
                ))

    # Calculate metrics
    elapsed = time.time() - start_time

    all_findings = []
    for r in results:
        all_findings.extend(r.findings)

    framework_count = len([f for f in all_findings if f.category == "framework"])
    learning_count = len([f for f in all_findings if f.category == "learning"])
    best_practice_count = len([f for f in all_findings if f.category == "best_practice"])
    codebase_count = len([f for f in all_findings if f.category == "codebase"])

    # Generate report
    report = format_research_report(results, task, elapsed)

    return {
        "success": len([r for r in results if r.success]) >= 2,
        "report": report,
        "findings_count": len(all_findings),
        "framework_findings": framework_count,
        "learning_findings": learning_count,
        "best_practice_findings": best_practice_count,
        "codebase_findings": codebase_count,
        "researcher_results": [
            {
                "researcher": r.researcher,
                "findings": len(r.findings),
                "summary": r.summary,
                "elapsed_ms": r.elapsed_ms,
                "success": r.success,
                "error": r.error,
            }
            for r in results
        ],
        "elapsed_seconds": round(elapsed, 2),
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("plan_deepen - Research-Driven Plan Enhancement v1.0.0")
    print("=" * 60)
    print()
    print("This skill runs 4 research sub-agents IN PARALLEL:")
    print()
    print("  ┌─────────────────────────────────────────────────┐")
    print("  │               plan_deepen                        │")
    print("  ├─────────────────────────────────────────────────┤")
    print("  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │")
    print("  │  │Framework │  │Learnings │  │ Best     │       │")
    print("  │  │  Docs    │  │Researcher│  │Practices │       │")
    print("  │  └────┬─────┘  └────┬─────┘  └────┬─────┘       │")
    print("  │       │              │              │            │")
    print("  │       │         ┌────┴─────┐       │            │")
    print("  │       │         │ Codebase │       │            │")
    print("  │       │         │ Analyzer │       │            │")
    print("  │       │         └────┬─────┘       │            │")
    print("  │       └──────────┬───┴─────────────┘            │")
    print("  │          Consolidated Research Report            │")
    print("  └─────────────────────────────────────────────────┘")
    print()
    print("Front-loads research to make execution more accurate.")
    print("Uses Context7 MCP for framework docs when available.")
