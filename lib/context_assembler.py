"""
Context Assembler - Orchestrates the Cartridge Memory System.

Part of the Cartridge Memory System.
Assembles context from: Project Constitution + Skills + Task Pack.

Token budget model:
- Always-on Skills: 20-40K tokens (core procedural knowledge)
- Project Constitution: 1-3K tokens (project-specific laws)
- Task Pack: 2-8K tokens (dynamic, task-specific)
- Deep Archive: On-demand retrieval
"""

import json
import re
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

# Sibling imports
from constitution_loader import load_constitution, render_constitution, list_constitutions

SKILLS_DIR = Path.home() / ".agent" / "skills"
STATS_FILE = SKILLS_DIR / "stats.json"


class RenderMode(Enum):
    MINIMAL = "minimal"
    COMPACT = "compact"
    FULL = "full"


@dataclass
class TokenBudget:
    """Token budget allocation for context assembly."""
    constitution: int = 2000
    skills: int = 30000
    task_pack: int = 5000
    total: int = 40000


@dataclass
class ContextPack:
    """Assembled context ready for injection."""
    constitution: Optional[str]
    skills: List[Dict[str, Any]]
    task_context: Optional[str]
    total_tokens: int
    budget_used: Dict[str, int]


def estimate_tokens(text: str) -> int:
    """Rough token estimation (~1.3 tokens per word)."""
    return int(len(text.split()) * 1.3)


def load_skill_stats() -> Dict[str, Dict[str, Any]]:
    """Load skill statistics from stats.json."""
    if not STATS_FILE.exists():
        return {}

    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("stats", {})


def load_skill(skill_path: Path) -> Optional[Dict[str, Any]]:
    """Load a skill definition from YAML file."""
    if not skill_path.exists():
        return None

    with open(skill_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_skill_rendering(skill: Dict[str, Any], mode: RenderMode) -> str:
    """Get precompiled rendering for a skill at specified detail level."""
    renderings = skill.get("renderings", {})

    # Try requested mode, fall back to next available
    for try_mode in [mode.value, "compact", "minimal"]:
        if try_mode in renderings:
            return renderings[try_mode].get("content", "")

    # Ultimate fallback: use description
    desc = skill.get("description", {})
    return desc.get("short", skill.get("name", "Unknown skill"))


def score_skill_for_task(skill: Dict[str, Any], task_description: str, stats: Dict[str, Any]) -> float:
    """
    Score how relevant a skill is for a given task.

    Scoring factors:
    - Hard trigger match (intent): +10
    - Keyword overlap: +2 per match
    - Success rate: +0-5 based on historical performance
    - Confidence from stats: +0-3
    """
    score = 0.0
    task_lower = task_description.lower()

    # Check hard triggers (intents)
    triggers = skill.get("triggers", {})
    hard_triggers = triggers.get("hard", {})

    for intent in hard_triggers.get("intents", []):
        if intent.lower() in task_lower:
            score += 10.0
            break

    # Check soft triggers (keywords)
    soft_triggers = triggers.get("soft", {})
    for keyword in soft_triggers.get("keywords", []):
        if keyword.lower() in task_lower:
            score += 2.0

    # Also check old-style keywords field
    for keyword in skill.get("keywords", []):
        if keyword.lower() in task_lower:
            score += 1.5

    # Add stats-based scoring
    skill_id = skill.get("id", "")
    if skill_id in stats:
        s = stats[skill_id]
        # Success rate contribution (0-5)
        score += s.get("success_rate", 0.5) * 5
        # Confidence contribution (0-3)
        score += s.get("confidence", 0.5) * 3

    return score


def select_skills_for_task(
    task_description: str,
    budget_tokens: int = 30000,
    mode: RenderMode = RenderMode.COMPACT
) -> List[Tuple[Dict[str, Any], str, float]]:
    """
    Select and rank skills for a task within token budget.

    Returns: List of (skill, rendered_content, score) tuples.
    """
    skills = []
    stats = load_skill_stats()

    # Load all YAML skills from skills/core and other directories
    for skill_file in SKILLS_DIR.rglob("*.yaml"):
        skill = load_skill(skill_file)
        if skill and "id" in skill:
            score = score_skill_for_task(skill, task_description, stats)
            if score > 0:
                skills.append((skill, score))

    # Sort by score descending
    skills.sort(key=lambda x: x[1], reverse=True)

    # Select within budget
    selected = []
    tokens_used = 0

    for skill, score in skills:
        rendered = get_skill_rendering(skill, mode)
        tokens = estimate_tokens(rendered)

        if tokens_used + tokens <= budget_tokens:
            selected.append((skill, rendered, score))
            tokens_used += tokens
        else:
            # Try with minimal rendering
            if mode != RenderMode.MINIMAL:
                rendered = get_skill_rendering(skill, RenderMode.MINIMAL)
                tokens = estimate_tokens(rendered)
                if tokens_used + tokens <= budget_tokens:
                    selected.append((skill, rendered, score))
                    tokens_used += tokens

    return selected


def detect_project_from_path(path: Path) -> Optional[str]:
    """
    Detect project ID from current working directory.

    Looks for:
    1. .project_id file
    2. constitution_id in package.json
    3. Project directory name matching known constitutions
    """
    # Check for .project_id file
    project_id_file = path / ".project_id"
    if project_id_file.exists():
        return project_id_file.read_text().strip()

    # Check package.json
    package_json = path / "package.json"
    if package_json.exists():
        try:
            with open(package_json, 'r', encoding='utf-8') as f:
                pkg = json.load(f)
                if "constitution_id" in pkg:
                    return pkg["constitution_id"]
        except (json.JSONDecodeError, KeyError):
            pass

    # Check if directory name matches a constitution
    available = list_constitutions()
    dir_name = path.name.lower().replace("-", "").replace("_", "")

    for const_id in available:
        if const_id.replace("-", "") == dir_name:
            return const_id

    # Check parent directories
    for parent in path.parents:
        parent_name = parent.name.lower().replace("-", "").replace("_", "")
        for const_id in available:
            if const_id.replace("-", "") == parent_name:
                return const_id

    return None


def assemble_context(
    task_description: str,
    working_dir: Optional[Path] = None,
    budget: Optional[TokenBudget] = None,
    constitution_mode: RenderMode = RenderMode.COMPACT,
    skill_mode: RenderMode = RenderMode.COMPACT
) -> ContextPack:
    """
    Assemble full context for a task.

    This is the main entry point for the Cartridge Memory System.

    Args:
        task_description: What the user wants to do
        working_dir: Current working directory (for project detection)
        budget: Token budget allocation
        constitution_mode: Detail level for constitution
        skill_mode: Detail level for skills

    Returns:
        ContextPack with assembled context ready for injection
    """
    if budget is None:
        budget = TokenBudget()

    if working_dir is None:
        working_dir = Path.cwd()

    budget_used = {
        "constitution": 0,
        "skills": 0,
        "task_pack": 0
    }

    # 1. Load Project Constitution
    constitution_text = None
    project_id = detect_project_from_path(working_dir)

    if project_id:
        const = load_constitution(project_id)
        if const:
            constitution_text = render_constitution(const, constitution_mode.value)
            budget_used["constitution"] = estimate_tokens(constitution_text)

    # 2. Select Skills
    # Adjust skill budget based on constitution usage
    available_skill_budget = budget.skills
    if budget_used["constitution"] > budget.constitution:
        # Constitution went over, reduce skill budget
        overflow = budget_used["constitution"] - budget.constitution
        available_skill_budget = max(10000, budget.skills - overflow)

    selected_skills = select_skills_for_task(
        task_description,
        budget_tokens=available_skill_budget,
        mode=skill_mode
    )

    skills_data = []
    for skill, rendered, score in selected_skills:
        skills_data.append({
            "id": skill.get("id"),
            "name": skill.get("name"),
            "rendered": rendered,
            "score": score
        })
        budget_used["skills"] += estimate_tokens(rendered)

    # 3. Task Pack (placeholder - would be filled by semantic search)
    task_context = None
    # In full implementation, this would search deep archive for relevant context

    total_tokens = sum(budget_used.values())

    return ContextPack(
        constitution=constitution_text,
        skills=skills_data,
        task_context=task_context,
        total_tokens=total_tokens,
        budget_used=budget_used
    )


def format_context_for_injection(pack: ContextPack) -> str:
    """
    Format assembled context for direct injection into prompt.

    Returns a single string ready for context injection.
    """
    sections = []

    # Constitution section
    if pack.constitution:
        sections.append("# Project Constitution\n")
        sections.append(pack.constitution)
        sections.append("\n")

    # Skills section
    if pack.skills:
        sections.append("# Relevant Skills\n")
        for skill in pack.skills:
            sections.append(f"## {skill['name']}\n")
            sections.append(skill['rendered'])
            sections.append("\n")

    # Task context section
    if pack.task_context:
        sections.append("# Task Context\n")
        sections.append(pack.task_context)
        sections.append("\n")

    # Budget info (minimal)
    sections.append(f"\n<!-- Context: {pack.total_tokens} tokens -->")

    return "\n".join(sections)


# CLI interface for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python context_assembler.py <task_description>")
        print("\nExample:")
        print('  python context_assembler.py "commit my changes"')
        sys.exit(1)

    task = " ".join(sys.argv[1:])

    print(f"Assembling context for: {task}\n")

    pack = assemble_context(task)

    print("=" * 60)
    print(f"Total tokens: {pack.total_tokens}")
    print(f"Budget used: {pack.budget_used}")
    print("=" * 60)

    if pack.constitution:
        print("\n--- CONSTITUTION ---")
        print(pack.constitution[:500] + "..." if len(pack.constitution) > 500 else pack.constitution)

    if pack.skills:
        print("\n--- SKILLS ---")
        for skill in pack.skills:
            print(f"\n[{skill['name']}] (score: {skill['score']:.1f})")
            print(skill['rendered'][:300] + "..." if len(skill['rendered']) > 300 else skill['rendered'])
