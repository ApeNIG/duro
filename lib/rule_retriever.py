"""
Rule Retriever - Match rules to current task context.

Enhanced keyword matching with scoring and priority handling.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


RULES_DIR = Path(__file__).parent.parent / "rules"
INDEX_FILE = RULES_DIR / "index.json"


@dataclass
class MatchedRule:
    """A rule matched to a task with relevance score."""
    rule_id: str
    name: str
    rule_type: str  # hard or soft
    priority: int
    score: float  # 0.0 to 1.0
    matched_keywords: List[str]
    file_path: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "type": self.rule_type,
            "priority": self.priority,
            "score": self.score,
            "matched_keywords": self.matched_keywords,
            "file_path": self.file_path
        }


def load_rules_index() -> dict:
    """Load the rules index."""
    if not INDEX_FILE.exists():
        return {"rules": []}
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_rule_content(rule_entry: dict) -> Optional[dict]:
    """Load the full rule content from its file."""
    file_path = RULES_DIR / rule_entry.get("file", "")
    if not file_path.exists():
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words."""
    return re.findall(r'\b[a-z]+\b', text.lower())


def calculate_match_score(task_tokens: List[str], rule_keywords: List[str]) -> tuple:
    """
    Calculate match score between task and rule keywords.

    Returns (score, matched_keywords)
    """
    if not rule_keywords:
        return 0.0, []

    task_set = set(task_tokens)
    matched = []

    for keyword in rule_keywords:
        keyword_lower = keyword.lower()
        keyword_tokens = set(tokenize(keyword_lower))

        # Direct match
        if keyword_lower in ' '.join(task_tokens):
            matched.append(keyword)
            continue

        # Token overlap
        if keyword_tokens & task_set:
            matched.append(keyword)

    if not matched:
        return 0.0, []

    # Score based on proportion of keywords matched
    score = len(matched) / len(rule_keywords)

    # Bonus for matching multiple keywords
    if len(matched) >= 3:
        score = min(1.0, score * 1.2)

    return round(score, 3), matched


def retrieve_rules(
    task_description: str,
    min_score: float = 0.1,
    max_results: int = 10,
    rule_type: Optional[str] = None,
    include_content: bool = False
) -> List[Dict[str, Any]]:
    """
    Retrieve rules matching a task description.

    Args:
        task_description: The task to match rules against
        min_score: Minimum match score (0.0-1.0)
        max_results: Maximum number of rules to return
        rule_type: Filter by 'hard' or 'soft'
        include_content: Include full rule content

    Returns:
        List of matched rules, sorted by priority then score
    """
    index = load_rules_index()
    rules = index.get("rules", [])

    task_tokens = tokenize(task_description)
    task_text = task_description.lower()

    matches = []

    for rule in rules:
        # Type filter
        if rule_type and rule.get("type") != rule_type:
            continue

        keywords = rule.get("trigger_keywords", [])
        score, matched_kw = calculate_match_score(task_tokens, keywords)

        # Also check rule name
        name_tokens = tokenize(rule.get("name", ""))
        if any(t in task_tokens for t in name_tokens):
            score = min(1.0, score + 0.2)
            matched_kw.append(f"[name:{rule.get('name')}]")

        if score >= min_score:
            match = MatchedRule(
                rule_id=rule.get("id", "unknown"),
                name=rule.get("name", "Unknown Rule"),
                rule_type=rule.get("type", "soft"),
                priority=rule.get("priority", 5),
                score=score,
                matched_keywords=matched_kw,
                file_path=rule.get("file", "")
            )
            matches.append(match)

    # Sort: priority (lower = higher priority), then score (higher = better)
    matches.sort(key=lambda m: (m.priority, -m.score))

    # Limit results
    matches = matches[:max_results]

    # Convert to dicts and optionally include content
    results = []
    for match in matches:
        result = match.to_dict()
        if include_content:
            content = load_rule_content({"file": match.file_path})
            if content:
                result["content"] = content
        results.append(result)

    return results


def get_hard_rules(task_description: str) -> List[Dict[str, Any]]:
    """Get only hard (mandatory) rules for a task."""
    return retrieve_rules(task_description, rule_type="hard", min_score=0.05)


def get_soft_rules(task_description: str) -> List[Dict[str, Any]]:
    """Get only soft (preference) rules for a task."""
    return retrieve_rules(task_description, rule_type="soft", min_score=0.1)


def check_rules(task_description: str) -> Dict[str, Any]:
    """
    Check all applicable rules for a task.

    Returns structured result with hard and soft rules separated.
    """
    hard = get_hard_rules(task_description)
    soft = get_soft_rules(task_description)

    return {
        "task": task_description,
        "hard_rules": hard,
        "soft_rules": soft,
        "total_matched": len(hard) + len(soft),
        "has_hard_constraints": len(hard) > 0
    }


if __name__ == "__main__":
    # Test the retriever
    import sys

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = "generate character image with face"

    print(f"Task: {task}\n")

    result = check_rules(task)

    print(f"Hard rules ({len(result['hard_rules'])}):")
    for r in result['hard_rules']:
        print(f"  - {r['name']} (score: {r['score']}, matched: {r['matched_keywords']})")

    print(f"\nSoft rules ({len(result['soft_rules'])}):")
    for r in result['soft_rules']:
        print(f"  - {r['name']} (score: {r['score']}, matched: {r['matched_keywords']})")
