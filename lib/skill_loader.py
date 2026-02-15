"""
Skill Loader - Load skills with token-aware rendering.

Part of the Cartridge Memory System (Phase 4.1).
Provides skill discovery, loading, and token-aware rendering.

Currently a stub - skill loading logic exists in context_assembler.py.
Phase 4.1 will refactor to consolidate here.
"""

import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


SKILLS_DIR = Path.home() / ".agent" / "skills"
INDEX_FILE = SKILLS_DIR / "index.json"
STATS_FILE = SKILLS_DIR / "stats.json"


class RenderMode(Enum):
    MINIMAL = "minimal"   # ~50 tokens - name + one-liner
    COMPACT = "compact"   # ~200 tokens - + triggers + examples
    FULL = "full"         # ~500 tokens - full documentation


@dataclass
class SkillMetadata:
    """Metadata for a loaded skill."""
    id: str
    name: str
    tier: str
    file_path: str
    token_estimate: int
    keywords: List[str]


def load_skill_index() -> Dict[str, Any]:
    """Load the skills index.json."""
    if not INDEX_FILE.exists():
        return {"skills": []}
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_skill(skill_path: Path) -> Optional[Dict[str, Any]]:
    """Load a skill definition from YAML file."""
    if not skill_path.exists():
        return None
    with open(skill_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_skill_by_id(skill_id: str) -> Optional[Dict[str, Any]]:
    """Load a skill by its ID from the index."""
    index = load_skill_index()
    for skill_meta in index.get("skills", []):
        if skill_meta.get("id") == skill_id:
            skill_path = SKILLS_DIR / skill_meta.get("file", "")
            return load_skill(skill_path)
    return None


def get_skill_rendering(skill: Dict[str, Any], mode: RenderMode) -> str:
    """
    Get precompiled rendering for a skill at specified detail level.

    Precompiled renderings are stored in skill.renderings.{mode}.
    Falls back to generating from description if not precompiled.
    """
    renderings = skill.get("renderings", {})

    # Try precompiled rendering first
    if mode.value in renderings:
        return renderings[mode.value]

    # Fallback: generate from description
    desc = skill.get("description", {})
    name = skill.get("name", "Unknown skill")

    if mode == RenderMode.MINIMAL:
        return f"{name}: {desc.get('short', '')}"
    elif mode == RenderMode.COMPACT:
        lines = [f"## {name}", desc.get("short", "")]
        if triggers := skill.get("triggers", {}):
            lines.append(f"Triggers: {', '.join(triggers.get('keywords', []))}")
        return "\n".join(lines)
    else:  # FULL
        lines = [f"## {name}", "", desc.get("full", desc.get("short", ""))]
        if examples := skill.get("examples", []):
            lines.append("\nExamples:")
            for ex in examples[:3]:
                lines.append(f"- {ex}")
        return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token)."""
    return len(text) // 4


def list_skills(tier_filter: Optional[str] = None) -> List[SkillMetadata]:
    """List all skills with optional tier filter."""
    index = load_skill_index()
    skills = []

    for skill_meta in index.get("skills", []):
        if tier_filter and skill_meta.get("tier") != tier_filter:
            continue

        skills.append(SkillMetadata(
            id=skill_meta.get("id", ""),
            name=skill_meta.get("name", ""),
            tier=skill_meta.get("tier", "unknown"),
            file_path=skill_meta.get("file", ""),
            token_estimate=skill_meta.get("token_estimate", 200),
            keywords=skill_meta.get("keywords", [])
        ))

    return skills


def find_skills_by_keywords(keywords: List[str], limit: int = 10) -> List[SkillMetadata]:
    """Find skills matching given keywords."""
    all_skills = list_skills()
    scored = []

    for skill in all_skills:
        score = 0
        skill_keywords = set(kw.lower() for kw in skill.keywords)
        for keyword in keywords:
            if keyword.lower() in skill_keywords:
                score += 2
            elif any(keyword.lower() in sk for sk in skill_keywords):
                score += 1

        if score > 0:
            scored.append((skill, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in scored[:limit]]


# Phase 4.1 TODO: Refactor context_assembler.py to use this module
