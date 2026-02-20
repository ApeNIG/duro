"""Skill library endpoints."""

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

SKILLS_PATH = Path.home() / ".agent" / "skills"
SKILL_STATS_PATH = Path.home() / ".agent" / "memory" / "skill_stats"


def load_json_file(path: Path) -> dict[str, Any] | None:
    """Load a JSON file safely."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def get_skill_stats(skill_id: str) -> dict[str, Any] | None:
    """Load stats for a specific skill."""
    stats_file = SKILL_STATS_PATH / f"ss_{skill_id}.json"
    return load_json_file(stats_file)


@router.get("/skills")
async def list_skills(
    category: Optional[str] = Query(None, description="Filter by category"),
    tested: Optional[bool] = Query(None, description="Filter by tested status"),
) -> dict[str, Any]:
    """List all skills with their stats."""
    try:
        if not SKILLS_PATH.exists():
            return {"skills": [], "total": 0}

        skills = []

        # Load skills from index if it exists
        index_path = SKILLS_PATH / "index.json"
        if index_path.exists():
            index = load_json_file(index_path)
            if index and "skills" in index:
                for skill_entry in index["skills"]:
                    skill_id = skill_entry.get("id") or skill_entry.get("name")
                    if not skill_id:
                        continue

                    skill = {
                        "id": skill_id,
                        "name": skill_entry.get("name", skill_id),
                        "description": skill_entry.get("description", ""),
                        "category": skill_entry.get("category", "general"),
                        "is_core": skill_entry.get("is_core", False),
                        "tested": skill_entry.get("tested", False),
                        "tags": skill_entry.get("tags", []),
                    }

                    # Load stats if available
                    stats = get_skill_stats(skill_id)
                    if stats:
                        skill["stats"] = {
                            "total_uses": stats.get("total_uses", 0),
                            "successes": stats.get("successes", 0),
                            "failures": stats.get("failures", 0),
                            "success_rate": stats.get("success_rate", 0),
                            "last_used": stats.get("last_used"),
                            "avg_duration_ms": stats.get("avg_duration_ms"),
                        }

                    # Apply filters
                    if category and skill["category"] != category:
                        continue
                    if tested is not None and skill["tested"] != tested:
                        continue

                    skills.append(skill)
        else:
            # Fallback: scan skill files directly
            for skill_file in SKILLS_PATH.glob("*.py"):
                if skill_file.name.startswith("_"):
                    continue

                skill_id = skill_file.stem
                skill = {
                    "id": skill_id,
                    "name": skill_id.replace("_", " ").title(),
                    "description": "",
                    "category": "general",
                    "is_core": False,
                    "tested": False,
                    "file_path": str(skill_file),
                }

                # Try to read docstring
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if line.strip().startswith('"""') or line.strip().startswith("'''"):
                            # Found docstring start
                            quote = line.strip()[:3]
                            if line.strip().endswith(quote) and len(line.strip()) > 6:
                                skill["description"] = line.strip()[3:-3]
                            else:
                                # Multi-line docstring
                                doc_lines = []
                                for j in range(i, min(i + 5, len(lines))):
                                    doc_lines.append(lines[j].strip().strip('"\''))
                                skill["description"] = " ".join(doc_lines)[:200]
                            break
                except Exception:
                    pass

                # Load stats
                stats = get_skill_stats(skill_id)
                if stats:
                    skill["stats"] = {
                        "total_uses": stats.get("total_uses", 0),
                        "successes": stats.get("successes", 0),
                        "failures": stats.get("failures", 0),
                        "success_rate": stats.get("success_rate", 0),
                        "last_used": stats.get("last_used"),
                    }

                skills.append(skill)

        # Sort by usage (most used first)
        skills.sort(
            key=lambda s: s.get("stats", {}).get("total_uses", 0),
            reverse=True
        )

        return {
            "skills": skills,
            "total": len(skills),
            "categories": list(set(s["category"] for s in skills)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str) -> dict[str, Any]:
    """Get a single skill with full details and code."""
    try:
        skill_file = SKILLS_PATH / f"{skill_id}.py"

        if not skill_file.exists():
            raise HTTPException(status_code=404, detail="Skill not found")

        # Load code
        code = skill_file.read_text(encoding="utf-8")

        # Load stats
        stats = get_skill_stats(skill_id)

        # Check index for metadata
        index_path = SKILLS_PATH / "index.json"
        metadata = {}
        if index_path.exists():
            index = load_json_file(index_path)
            if index and "skills" in index:
                for skill_entry in index["skills"]:
                    if skill_entry.get("id") == skill_id or skill_entry.get("name") == skill_id:
                        metadata = skill_entry
                        break

        return {
            "id": skill_id,
            "name": metadata.get("name", skill_id),
            "description": metadata.get("description", ""),
            "category": metadata.get("category", "general"),
            "is_core": metadata.get("is_core", False),
            "tested": metadata.get("tested", False),
            "tags": metadata.get("tags", []),
            "code": code,
            "stats": stats,
            "file_path": str(skill_file),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/stats/summary")
async def get_skills_stats_summary() -> dict[str, Any]:
    """Get summary statistics for all skills."""
    try:
        if not SKILL_STATS_PATH.exists():
            return {
                "total_skills": 0,
                "total_uses": 0,
                "overall_success_rate": 0,
                "most_used": [],
                "least_successful": [],
            }

        all_stats = []
        total_uses = 0
        total_successes = 0

        for stats_file in SKILL_STATS_PATH.glob("ss_*.json"):
            stats = load_json_file(stats_file)
            if stats:
                skill_id = stats_file.stem[3:]  # Remove 'ss_' prefix
                stats["skill_id"] = skill_id
                all_stats.append(stats)
                total_uses += stats.get("total_uses", 0)
                total_successes += stats.get("successes", 0)

        # Sort by total uses for most used
        most_used = sorted(
            all_stats,
            key=lambda s: s.get("total_uses", 0),
            reverse=True
        )[:5]

        # Sort by success rate for least successful (with min 3 uses)
        with_enough_uses = [s for s in all_stats if s.get("total_uses", 0) >= 3]
        least_successful = sorted(
            with_enough_uses,
            key=lambda s: s.get("success_rate", 0)
        )[:5]

        return {
            "total_skills": len(all_stats),
            "total_uses": total_uses,
            "overall_success_rate": round(total_successes / total_uses * 100, 1) if total_uses > 0 else 0,
            "most_used": [
                {"skill_id": s["skill_id"], "uses": s.get("total_uses", 0)}
                for s in most_used
            ],
            "least_successful": [
                {"skill_id": s["skill_id"], "success_rate": s.get("success_rate", 0)}
                for s in least_successful
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
