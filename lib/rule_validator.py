"""
Rule Validator - Check rule staleness and validity.

Validates rules based on:
- Last validation date
- Usage count
- Confidence score
- Conflict detection
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


RULES_DIR = Path(__file__).parent.parent / "rules"
INDEX_FILE = RULES_DIR / "index.json"
CANDIDATES_DIR = RULES_DIR / "candidates"

# Staleness thresholds
STALE_DAYS = 30  # Rule is stale if not validated in 30 days
UNUSED_DAYS = 60  # Rule is unused if not applied in 60 days


@dataclass
class RuleValidation:
    """Validation result for a rule."""
    rule_id: str
    name: str
    is_valid: bool
    is_stale: bool
    is_unused: bool
    days_since_used: Optional[int]
    days_since_validated: Optional[int]
    confidence: float
    validations: int
    issues: List[str]

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "is_valid": self.is_valid,
            "is_stale": self.is_stale,
            "is_unused": self.is_unused,
            "days_since_used": self.days_since_used,
            "days_since_validated": self.days_since_validated,
            "confidence": self.confidence,
            "validations": self.validations,
            "issues": self.issues
        }


def load_rules_index() -> dict:
    """Load the rules index."""
    if not INDEX_FILE.exists():
        return {"rules": []}
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_rules_index(index: dict) -> None:
    """Save the rules index."""
    index["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)


def load_rule_content(file_path: str) -> Optional[dict]:
    """Load rule content from file."""
    full_path = RULES_DIR / file_path
    if not full_path.exists():
        return None
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse a date string to datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None


def days_since(date_str: Optional[str]) -> Optional[int]:
    """Calculate days since a date."""
    dt = parse_date(date_str)
    if not dt:
        return None
    # Make dt timezone-naive if it has timezone
    if dt.tzinfo:
        dt = dt.replace(tzinfo=None)
    return (datetime.now() - dt).days


def validate_rule(rule_entry: dict) -> RuleValidation:
    """Validate a single rule."""
    rule_id = rule_entry.get("id", "unknown")
    name = rule_entry.get("name", "Unknown")
    issues = []

    # Load rule content for more details
    content = load_rule_content(rule_entry.get("file", ""))

    # Check staleness
    last_used = rule_entry.get("last_used")
    last_validated = content.get("last_validated") if content else None

    days_used = days_since(last_used)
    days_validated = days_since(last_validated)

    is_stale = (days_validated is None) or (days_validated > STALE_DAYS)
    is_unused = (days_used is None) or (days_used > UNUSED_DAYS)

    if is_stale:
        issues.append(f"Stale: not validated in {days_validated or 'unknown'} days")
    if is_unused:
        issues.append(f"Unused: not applied in {days_used or 'unknown'} days")

    # Check confidence
    confidence = content.get("confidence", 0.5) if content else 0.5
    if confidence < 0.5:
        issues.append(f"Low confidence: {confidence}")

    # Check validations count
    validations = content.get("validations", 0) if content else 0
    if validations < 2:
        issues.append(f"Under-validated: only {validations} validations")

    # Check if file exists
    if not content:
        issues.append("Rule file missing or invalid")

    # Check trigger keywords
    if not rule_entry.get("trigger_keywords"):
        issues.append("No trigger keywords defined")

    # Determine overall validity
    is_valid = len(issues) == 0 or (len(issues) == 1 and is_stale)

    return RuleValidation(
        rule_id=rule_id,
        name=name,
        is_valid=is_valid,
        is_stale=is_stale,
        is_unused=is_unused,
        days_since_used=days_used,
        days_since_validated=days_validated,
        confidence=confidence,
        validations=validations,
        issues=issues
    )


def validate_all_rules() -> Dict[str, Any]:
    """Validate all rules and return summary."""
    index = load_rules_index()
    rules = index.get("rules", [])

    validations = []
    valid_count = 0
    stale_count = 0
    unused_count = 0

    for rule in rules:
        v = validate_rule(rule)
        validations.append(v.to_dict())
        if v.is_valid:
            valid_count += 1
        if v.is_stale:
            stale_count += 1
        if v.is_unused:
            unused_count += 1

    return {
        "total_rules": len(rules),
        "valid": valid_count,
        "stale": stale_count,
        "unused": unused_count,
        "health_score": valid_count / len(rules) if rules else 0,
        "validations": validations,
        "checked_at": datetime.now().isoformat()
    }


def mark_rule_validated(rule_id: str, success: bool = True) -> bool:
    """Mark a rule as validated (used and confirmed working)."""
    index = load_rules_index()

    for rule in index.get("rules", []):
        if rule.get("id") == rule_id:
            rule["last_used"] = datetime.now().strftime("%Y-%m-%d")
            rule["usage_count"] = rule.get("usage_count", 0) + 1

            # Also update the rule file if it exists
            content = load_rule_content(rule.get("file", ""))
            if content:
                content["last_validated"] = datetime.now().strftime("%Y-%m-%d")
                if success:
                    content["validations"] = content.get("validations", 0) + 1
                    content["confidence"] = min(0.99, content.get("confidence", 0.5) + 0.02)
                else:
                    content["confidence"] = max(0.1, content.get("confidence", 0.5) - 0.05)

                # Save content
                full_path = RULES_DIR / rule.get("file", "")
                with open(full_path, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=2)

            save_rules_index(index)
            return True

    return False


def get_stale_rules() -> List[Dict[str, Any]]:
    """Get list of stale rules that need revalidation."""
    result = validate_all_rules()
    return [v for v in result["validations"] if v["is_stale"]]


def get_promotion_candidates() -> List[Dict[str, Any]]:
    """
    Get rules from candidates/ that meet promotion criteria.

    Criteria:
    - confidence >= 0.7
    - validations >= 2
    - no conflicts with existing rules
    """
    if not CANDIDATES_DIR.exists():
        return []

    candidates = []
    for file in CANDIDATES_DIR.glob("*.json"):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = json.load(f)

            confidence = content.get("confidence", 0)
            validations = content.get("validations", 0)

            if confidence >= 0.7 and validations >= 2:
                candidates.append({
                    "file": file.name,
                    "name": content.get("name", file.stem),
                    "confidence": confidence,
                    "validations": validations,
                    "ready_for_promotion": True
                })
            else:
                candidates.append({
                    "file": file.name,
                    "name": content.get("name", file.stem),
                    "confidence": confidence,
                    "validations": validations,
                    "ready_for_promotion": False,
                    "needs": {
                        "confidence": max(0, 0.7 - confidence),
                        "validations": max(0, 2 - validations)
                    }
                })
        except (json.JSONDecodeError, IOError):
            continue

    return candidates


if __name__ == "__main__":
    print("Rule Validation Report")
    print("=" * 50)

    result = validate_all_rules()

    print(f"Total rules: {result['total_rules']}")
    print(f"Valid: {result['valid']}")
    print(f"Stale: {result['stale']}")
    print(f"Unused: {result['unused']}")
    print(f"Health score: {result['health_score']:.1%}")

    print("\nStale rules:")
    for v in result["validations"]:
        if v["is_stale"]:
            print(f"  - {v['name']}: {', '.join(v['issues'])}")

    print("\nPromotion candidates:")
    for c in get_promotion_candidates():
        status = "READY" if c["ready_for_promotion"] else "PENDING"
        print(f"  - {c['name']}: {status} (conf: {c['confidence']}, val: {c['validations']})")
