"""
Promotion Compactor - Handles knowledge promotion and compaction.

Part of the Cartridge Memory System.
Manages the flow from ephemeral knowledge to permanent memory:
- Preference -> Law
- Tactic -> Pattern
- Procedural -> Skill
- Output -> Template

Every promoted artifact stores provenance links to source decisions.
"""

import json
import yaml
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Literal
from dataclasses import dataclass, asdict
from enum import Enum

CONSTITUTIONS_DIR = Path.home() / ".agent" / "constitutions"
SKILLS_DIR = Path.home() / ".agent" / "skills"
PENDING_DIR = Path.home() / ".agent" / "pending_promotions"


class PromotionType(Enum):
    PREFERENCE_TO_LAW = "preference_to_law"
    TACTIC_TO_PATTERN = "tactic_to_pattern"
    PROCEDURAL_TO_SKILL = "procedural_to_skill"
    OUTPUT_TO_TEMPLATE = "output_to_template"


@dataclass
class PromotionCandidate:
    """A piece of knowledge being considered for promotion."""
    id: str
    type: PromotionType
    content: Dict[str, Any]
    source_decisions: List[str]  # Decision IDs that support this
    occurrences: int  # Times this pattern was observed
    user_endorsed: bool  # User explicitly approved
    prevented_failure: bool  # Helped avoid a mistake
    contradicted_later: bool  # Was later reversed
    created_at: str
    last_seen: str


@dataclass
class PromotionScore:
    """Scoring for promotion decision."""
    base_score: float
    repeated_bonus: float  # +3 if >= 3 occurrences
    endorsement_bonus: float  # +2 if user endorsed
    failure_prevention_bonus: float  # +2 if prevented failure
    contradiction_penalty: float  # -4 if contradicted
    total: float
    threshold: float = 5.0
    should_promote: bool = False


def generate_id() -> str:
    """Generate a unique ID for tracking."""
    return f"promo_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def score_candidate(candidate: PromotionCandidate) -> PromotionScore:
    """
    Score a candidate for promotion.

    Scoring system:
    - +3: repeated >= 3 times
    - +2: user endorsed
    - +2: prevented failure
    - -4: contradicted later

    Threshold: >= 5 to promote
    """
    base = 0.0
    repeated = 3.0 if candidate.occurrences >= 3 else candidate.occurrences * 0.5
    endorsed = 2.0 if candidate.user_endorsed else 0.0
    prevented = 2.0 if candidate.prevented_failure else 0.0
    contradicted = -4.0 if candidate.contradicted_later else 0.0

    total = base + repeated + endorsed + prevented + contradicted

    return PromotionScore(
        base_score=base,
        repeated_bonus=repeated,
        endorsement_bonus=endorsed,
        failure_prevention_bonus=prevented,
        contradiction_penalty=contradicted,
        total=total,
        threshold=5.0,
        should_promote=total >= 5.0
    )


def create_candidate(
    content: Dict[str, Any],
    promotion_type: PromotionType,
    source_decisions: List[str],
    user_endorsed: bool = False,
    prevented_failure: bool = False
) -> PromotionCandidate:
    """Create a new promotion candidate."""
    now = datetime.utcnow().isoformat() + "Z"

    return PromotionCandidate(
        id=generate_id(),
        type=promotion_type,
        content=content,
        source_decisions=source_decisions,
        occurrences=1,
        user_endorsed=user_endorsed,
        prevented_failure=prevented_failure,
        contradicted_later=False,
        created_at=now,
        last_seen=now
    )


def save_pending(candidate: PromotionCandidate) -> Path:
    """Save a candidate to pending promotions."""
    PENDING_DIR.mkdir(parents=True, exist_ok=True)

    # Convert to dict with enum values serialized
    data = asdict(candidate)
    data['type'] = candidate.type.value  # Convert enum to string value

    filepath = PENDING_DIR / f"{candidate.id}.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    return filepath


def load_pending() -> List[PromotionCandidate]:
    """Load all pending promotion candidates."""
    if not PENDING_DIR.exists():
        return []

    candidates = []
    for filepath in PENDING_DIR.glob("*.json"):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            data['type'] = PromotionType(data['type'])
            candidates.append(PromotionCandidate(**data))

    return candidates


def find_similar_candidate(
    content: Dict[str, Any],
    promotion_type: PromotionType,
    candidates: List[PromotionCandidate]
) -> Optional[PromotionCandidate]:
    """Find an existing candidate that matches this content."""
    # Simple matching based on key fields
    content_str = json.dumps(content, sort_keys=True)

    for candidate in candidates:
        if candidate.type == promotion_type:
            existing_str = json.dumps(candidate.content, sort_keys=True)
            # Very simple similarity - could be made smarter
            if content_str == existing_str:
                return candidate

    return None


def record_observation(
    content: Dict[str, Any],
    promotion_type: PromotionType,
    source_decisions: List[str],
    user_endorsed: bool = False,
    prevented_failure: bool = False
) -> PromotionCandidate:
    """
    Record an observation of a pattern/preference/tactic.

    If similar candidate exists, increment its occurrence count.
    Otherwise, create a new candidate.
    """
    candidates = load_pending()
    existing = find_similar_candidate(content, promotion_type, candidates)

    if existing:
        # Update existing candidate
        existing.occurrences += 1
        existing.last_seen = datetime.utcnow().isoformat() + "Z"
        existing.source_decisions = list(set(existing.source_decisions + source_decisions))
        if user_endorsed:
            existing.user_endorsed = True
        if prevented_failure:
            existing.prevented_failure = True

        save_pending(existing)
        return existing
    else:
        # Create new candidate
        candidate = create_candidate(
            content=content,
            promotion_type=promotion_type,
            source_decisions=source_decisions,
            user_endorsed=user_endorsed,
            prevented_failure=prevented_failure
        )
        save_pending(candidate)
        return candidate


def mark_contradicted(candidate_id: str) -> bool:
    """Mark a candidate as contradicted (user reversed the pattern)."""
    filepath = PENDING_DIR / f"{candidate_id}.json"
    if not filepath.exists():
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data['contradicted_later'] = True
    data['last_seen'] = datetime.utcnow().isoformat() + "Z"

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    return True


def promote_to_law(
    candidate: PromotionCandidate,
    project_id: str,
    law_id: str,
    strength: Literal["hard", "soft"] = "soft"
) -> Dict[str, Any]:
    """
    Promote a preference to a project law.

    Adds the law to the project's constitution with provenance.
    """
    const_path = CONSTITUTIONS_DIR / f"{project_id}.yaml"
    if not const_path.exists():
        raise ValueError(f"Constitution not found: {project_id}")

    with open(const_path, 'r', encoding='utf-8') as f:
        const = yaml.safe_load(f)

    # Create the new law
    new_law = {
        "id": law_id,
        "rule": candidate.content.get("rule", str(candidate.content)),
        "strength": strength,
        "applies_to": candidate.content.get("applies_to", ["general"]),
        "rationale": candidate.content.get("rationale", "Promoted from repeated preference"),
        "provenance": candidate.source_decisions,
        "last_verified": datetime.utcnow().strftime("%Y-%m-%d")
    }

    # Add to constitution
    if "laws" not in const:
        const["laws"] = []
    const["laws"].append(new_law)

    # Update version
    version_parts = const.get("version", "0.1.0").split(".")
    version_parts[-1] = str(int(version_parts[-1]) + 1)
    const["version"] = ".".join(version_parts)
    const["updated_at"] = datetime.utcnow().isoformat() + "Z"

    # Save constitution
    with open(const_path, 'w', encoding='utf-8') as f:
        yaml.dump(const, f, default_flow_style=False, sort_keys=False)

    # Remove from pending
    pending_path = PENDING_DIR / f"{candidate.id}.json"
    if pending_path.exists():
        pending_path.unlink()

    return new_law


def promote_to_pattern(
    candidate: PromotionCandidate,
    project_id: str,
    pattern_id: str
) -> Dict[str, Any]:
    """
    Promote a tactic to a project pattern.

    Adds the pattern to the project's constitution with provenance.
    """
    const_path = CONSTITUTIONS_DIR / f"{project_id}.yaml"
    if not const_path.exists():
        raise ValueError(f"Constitution not found: {project_id}")

    with open(const_path, 'r', encoding='utf-8') as f:
        const = yaml.safe_load(f)

    # Create the new pattern
    new_pattern = {
        "id": pattern_id,
        "pattern": candidate.content.get("pattern", str(candidate.content)),
        "when": candidate.content.get("when", "General usage"),
        "value": candidate.content.get("value", "Proven effective through repeated use"),
        "provenance": candidate.source_decisions
    }

    # Add to constitution
    if "patterns_top" not in const:
        const["patterns_top"] = []
    const["patterns_top"].append(new_pattern)

    # Update version
    version_parts = const.get("version", "0.1.0").split(".")
    version_parts[-1] = str(int(version_parts[-1]) + 1)
    const["version"] = ".".join(version_parts)
    const["updated_at"] = datetime.utcnow().isoformat() + "Z"

    # Save constitution
    with open(const_path, 'w', encoding='utf-8') as f:
        yaml.dump(const, f, default_flow_style=False, sort_keys=False)

    # Remove from pending
    pending_path = PENDING_DIR / f"{candidate.id}.json"
    if pending_path.exists():
        pending_path.unlink()

    return new_pattern


def get_ready_for_promotion() -> List[tuple[PromotionCandidate, PromotionScore]]:
    """Get all candidates that meet the promotion threshold."""
    candidates = load_pending()
    ready = []

    for candidate in candidates:
        score = score_candidate(candidate)
        if score.should_promote:
            ready.append((candidate, score))

    # Sort by score descending
    ready.sort(key=lambda x: x[1].total, reverse=True)

    return ready


def get_promotion_report() -> Dict[str, Any]:
    """Generate a report of pending and ready-to-promote candidates."""
    candidates = load_pending()

    ready = []
    pending = []
    contradicted = []

    for candidate in candidates:
        score = score_candidate(candidate)
        entry = {
            "id": candidate.id,
            "type": candidate.type.value,
            "occurrences": candidate.occurrences,
            "score": score.total,
            "content_preview": str(candidate.content)[:100]
        }

        if candidate.contradicted_later:
            contradicted.append(entry)
        elif score.should_promote:
            ready.append(entry)
        else:
            pending.append(entry)

    return {
        "ready_for_promotion": len(ready),
        "pending": len(pending),
        "contradicted": len(contradicted),
        "ready": ready,
        "waiting": pending,
        "rejected": contradicted
    }


# CLI interface for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python promotion_compactor.py report")
        print("  python promotion_compactor.py ready")
        print("  python promotion_compactor.py record <type> <content_json>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "report":
        report = get_promotion_report()
        print(json.dumps(report, indent=2))

    elif cmd == "ready":
        ready = get_ready_for_promotion()
        if not ready:
            print("No candidates ready for promotion.")
        else:
            for candidate, score in ready:
                print(f"\n{candidate.id} ({candidate.type.value})")
                print(f"  Score: {score.total:.1f} / {score.threshold}")
                print(f"  Occurrences: {candidate.occurrences}")
                print(f"  Sources: {candidate.source_decisions}")

    elif cmd == "record" and len(sys.argv) >= 4:
        promo_type = PromotionType(sys.argv[2])
        content = json.loads(sys.argv[3])
        candidate = record_observation(
            content=content,
            promotion_type=promo_type,
            source_decisions=["manual_test"]
        )
        print(f"Recorded: {candidate.id}")
        print(f"Occurrences: {candidate.occurrences}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
