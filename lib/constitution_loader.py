"""
Constitution Loader - Load and validate project constitutions.

Part of the Cartridge Memory System.
Constitutions are the "laws of this project" - tiny (1-3K tokens),
enforceable, versioned, and traceable to decisions.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

CONSTITUTIONS_DIR = Path.home() / ".agent" / "constitutions"

# Cache: project_id -> (mtime, constitution)
_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}


def sanitize_project_id(project_id: str) -> str:
    """Prevent path traversal attacks."""
    if not re.match(r'^[a-z0-9-]+$', project_id.lower()):
        raise ValueError(f"Invalid project_id: {project_id}. Use lowercase alphanumeric and hyphens only.")
    return project_id.lower()


def load_constitution(project_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a project constitution with caching.

    Args:
        project_id: Project identifier (e.g., 'msj', 'cinematch')

    Returns:
        Constitution dict or None if not found
    """
    project_id = sanitize_project_id(project_id)
    filepath = CONSTITUTIONS_DIR / f"{project_id}.yaml"

    if not filepath.exists():
        return None

    mtime = filepath.stat().st_mtime

    # Check cache - hot reload if file changed
    if project_id in _cache:
        cached_mtime, cached_const = _cache[project_id]
        if cached_mtime == mtime:
            return cached_const

    # Load and validate
    with open(filepath, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    errors = validate_constitution(data)
    if errors:
        raise ValueError(f"Invalid constitution '{project_id}': {'; '.join(errors)}")

    _cache[project_id] = (mtime, data)
    return data


def validate_constitution(data: Dict[str, Any]) -> List[str]:
    """
    Validate constitution structure.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Required top-level fields
    required = ['project_id', 'name', 'version', 'north_star', 'laws', 'constraints']
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return errors  # Can't validate further without required fields

    # Validate north_star
    ns = data.get('north_star', {})
    if 'statement' not in ns:
        errors.append("north_star.statement is required")
    if 'primary_user_job' not in ns:
        errors.append("north_star.primary_user_job is required")

    # Validate laws
    for i, law in enumerate(data.get('laws', [])):
        prefix = f"laws[{i}]"
        if 'id' not in law:
            errors.append(f"{prefix}: missing 'id'")
        if 'rule' not in law:
            errors.append(f"{prefix}: missing 'rule'")
        if 'strength' not in law:
            errors.append(f"{prefix}: missing 'strength'")
        elif law['strength'] not in ('hard', 'soft'):
            errors.append(f"{prefix}: strength must be 'hard' or 'soft'")

    # Validate constraints
    constraints = data.get('constraints', {})
    if 'do_not' not in constraints:
        errors.append("constraints.do_not is required")

    # Validate conflict_policy if present
    if 'conflict_policy' in data:
        cp = data['conflict_policy']
        if 'order' not in cp:
            errors.append("conflict_policy.order is required")
        if 'tie_break' not in cp:
            errors.append("conflict_policy.tie_break is required")
        elif cp.get('tie_break') not in ('newer_version_wins', 'stricter_wins', 'ask_user'):
            errors.append("conflict_policy.tie_break must be one of: newer_version_wins, stricter_wins, ask_user")

    return errors


def render_constitution(const: Dict[str, Any], mode: str = 'full') -> str:
    """
    Render constitution for context injection.

    Args:
        const: Constitution dict
        mode: 'minimal' (~200 tokens), 'compact' (~800), 'full' (~2000)

    Returns:
        Rendered string ready for context injection
    """
    if mode == 'minimal':
        return _render_minimal(const)
    elif mode == 'compact':
        return _render_compact(const)
    else:
        return _render_full(const)


def _render_minimal(const: Dict[str, Any]) -> str:
    """~200 tokens: Just north star and hard laws."""
    lines = [
        f"# {const['name']}",
        f"{const['north_star']['statement']}",
        "",
        "**Hard Laws:**"
    ]
    for law in const.get('laws', []):
        if law['strength'] == 'hard':
            lines.append(f"- {law['rule']}")

    lines.append("")
    lines.append("**Do Not:**")
    for item in const.get('constraints', {}).get('do_not', [])[:3]:  # Top 3 only
        lines.append(f"- {item}")

    return "\n".join(lines)


def _render_compact(const: Dict[str, Any]) -> str:
    """~800 tokens: Laws + constraints + deciding axes."""
    lines = [
        f"# {const['name']} Constitution",
        f"**Vision:** {const['north_star']['statement']}",
        f"**User Job:** {const['north_star']['primary_user_job']}",
        "",
        "## Laws"
    ]

    # Group by strength
    hard_laws = [l for l in const.get('laws', []) if l['strength'] == 'hard']
    soft_laws = [l for l in const.get('laws', []) if l['strength'] == 'soft']

    if hard_laws:
        lines.append("### Hard (Must Follow)")
        for law in hard_laws:
            lines.append(f"- {law['rule']}")

    if soft_laws:
        lines.append("\n### Soft (Prefer)")
        for law in soft_laws:
            lines.append(f"- {law['rule']}")

    lines.append("\n## Do Not")
    for item in const.get('constraints', {}).get('do_not', []):
        lines.append(f"- {item}")

    if const.get('deciding_axes'):
        lines.append("\n## Deciding Axes")
        for axis in const['deciding_axes']:
            lines.append(f"- {axis}")

    return "\n".join(lines)


def _render_full(const: Dict[str, Any]) -> str:
    """~2000 tokens: Everything including patterns."""
    lines = [
        f"# {const['name']} Constitution v{const['version']}",
        "",
        "## North Star",
        f"**Vision:** {const['north_star']['statement']}",
        f"**User Job:** {const['north_star']['primary_user_job']}",
    ]
    if 'tone' in const['north_star']:
        lines.append(f"**Tone:** {const['north_star']['tone']}")

    # Laws grouped by strength
    lines.append("\n## Laws")

    hard_laws = [l for l in const.get('laws', []) if l['strength'] == 'hard']
    soft_laws = [l for l in const.get('laws', []) if l['strength'] == 'soft']

    if hard_laws:
        lines.append("\n### Hard Laws (Must Follow)")
        for law in hard_laws:
            lines.append(f"\n**{law['id']}**")
            lines.append(f"{law['rule']}")
            if 'rationale' in law:
                lines.append(f"*Rationale: {law['rationale']}*")

    if soft_laws:
        lines.append("\n### Soft Laws (Prefer)")
        for law in soft_laws:
            lines.append(f"\n**{law['id']}**")
            lines.append(f"{law['rule']}")
            if 'rationale' in law:
                lines.append(f"*Rationale: {law['rationale']}*")

    # Constraints
    lines.append("\n## Constraints")
    lines.append("\n### Do Not")
    for item in const.get('constraints', {}).get('do_not', []):
        lines.append(f"- {item}")

    if 'accessibility' in const.get('constraints', {}):
        lines.append("\n### Accessibility")
        acc = const['constraints']['accessibility']
        if 'min_contrast' in acc:
            lines.append(f"- Contrast: {acc['min_contrast']}")
        if 'touch_target_min_px' in acc:
            lines.append(f"- Touch targets: {acc['touch_target_min_px']}px minimum")

    if 'performance' in const.get('constraints', {}):
        lines.append("\n### Performance")
        perf = const['constraints']['performance']
        if 'max_bundle_kb' in perf:
            lines.append(f"- Bundle size: <{perf['max_bundle_kb']}KB")

    # Patterns
    if const.get('patterns_top'):
        lines.append("\n## Top Patterns")
        for p in const['patterns_top']:
            lines.append(f"\n### {p['id']}")
            lines.append(f"**When:** {p['when']}")
            lines.append(f"**Pattern:** {p['pattern']}")
            lines.append(f"**Value:** {p['value']}")

    # Deciding axes
    if const.get('deciding_axes'):
        lines.append("\n## Deciding Axes")
        for axis in const['deciding_axes']:
            lines.append(f"- {axis}")

    # Conflict policy
    if const.get('conflict_policy'):
        lines.append("\n## Conflict Resolution")
        cp = const['conflict_policy']
        lines.append(f"**Priority:** {' > '.join(cp.get('order', []))}")
        lines.append(f"**Tie-break:** {cp.get('tie_break', 'newer_version_wins')}")

    return "\n".join(lines)


def count_tokens(text: str) -> int:
    """
    Rough token count estimation.

    Uses word count * 1.3 as approximation for GPT-style tokenizers.
    """
    return int(len(text.split()) * 1.3)


def list_constitutions() -> List[str]:
    """List all available project IDs with constitutions."""
    if not CONSTITUTIONS_DIR.exists():
        return []

    return [
        f.stem for f in CONSTITUTIONS_DIR.glob("*.yaml")
        if f.stem != "schema"  # Exclude schema file
    ]


def get_constitution_info(project_id: str) -> Optional[Dict[str, Any]]:
    """Get constitution metadata without full load."""
    const = load_constitution(project_id)
    if not const:
        return None

    return {
        "project_id": const['project_id'],
        "name": const['name'],
        "version": const['version'],
        "updated_at": const.get('updated_at'),
        "law_count": len(const.get('laws', [])),
        "hard_law_count": len([l for l in const.get('laws', []) if l['strength'] == 'hard']),
        "pattern_count": len(const.get('patterns_top', [])),
        "token_estimate": {
            "minimal": count_tokens(_render_minimal(const)),
            "compact": count_tokens(_render_compact(const)),
            "full": count_tokens(_render_full(const)),
        }
    }
