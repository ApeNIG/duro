"""
Rule Extractor - Extract rules from episodes, failures, and successes.

This meta-skill analyzes episodes and generates candidate rules
that can be promoted to the active ruleset after validation.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


RULES_DIR = Path(__file__).parent.parent.parent / "rules"
CANDIDATES_DIR = RULES_DIR / "candidates"
TEMPLATES_DIR = RULES_DIR / "templates"
INDEX_FILE = RULES_DIR / "index.json"


def load_template(template_type: str) -> Optional[dict]:
    """Load a rule template by type."""
    template_file = TEMPLATES_DIR / f"{template_type}_rule.json"
    if not template_file.exists():
        return None
    with open(template_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_rule_id(category: str) -> str:
    """Generate a unique rule ID."""
    # Load existing rules to find next ID
    if INDEX_FILE.exists():
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            index = json.load(f)
        existing_ids = [r.get("id", "") for r in index.get("rules", [])]
    else:
        existing_ids = []

    # Also check candidates
    if CANDIDATES_DIR.exists():
        for f in CANDIDATES_DIR.glob("*.json"):
            existing_ids.append(f.stem)

    # Find next number for this category
    prefix = f"rule_{category}_"
    max_num = 0
    for rid in existing_ids:
        if rid.startswith(prefix):
            try:
                num = int(rid.replace(prefix, ""))
                max_num = max(max_num, num)
            except ValueError:
                pass

    return f"{prefix}{max_num + 1:03d}"


def extract_keywords(text: str) -> List[str]:
    """Extract potential trigger keywords from text."""
    # Common stop words to filter
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'to', 'of', 'in',
        'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
        'during', 'before', 'after', 'above', 'below', 'between', 'under',
        'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
        'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some',
        'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
        'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because', 'until',
        'while', 'this', 'that', 'these', 'those', 'it', 'its'
    }

    # Extract words
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())

    # Filter and count
    word_counts = {}
    for word in words:
        if word not in stop_words:
            word_counts[word] = word_counts.get(word, 0) + 1

    # Return top keywords by frequency
    sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
    return [w[0] for w in sorted_words[:10]]


def extract_from_failure(
    failure_description: str,
    lesson_learned: str,
    context: Optional[str] = None,
    source_episode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract a failure rule from a failure incident.

    Args:
        failure_description: What went wrong
        lesson_learned: What to do differently
        context: Additional context
        source_episode: Episode ID if from an episode

    Returns:
        Candidate rule dict
    """
    template = load_template("failure")
    if not template:
        template = {"fields": {}}

    fields = template.get("fields", {})

    # Generate rule
    rule_id = generate_rule_id("failure")
    keywords = extract_keywords(f"{failure_description} {lesson_learned}")

    rule = {
        "id": rule_id,
        "name": lesson_learned[:50] if len(lesson_learned) > 50 else lesson_learned,
        "category": "failures",
        "type": "hard",
        "priority": 1,
        "trigger_keywords": keywords,
        "failure_pattern": {
            "symptom": failure_description,
            "root_cause": "Extracted from failure",
            "detection": "Match trigger keywords"
        },
        "prevention": {
            "before_action": lesson_learned,
            "avoid": failure_description,
            "alternative": lesson_learned
        },
        "recovery": {
            "if_detected": "Stop and apply lesson",
            "cleanup": "Review and retry"
        },
        "source_episode": source_episode,
        "confidence": 0.5,  # Start at 0.5, needs validation
        "validations": 1,   # First validation from extraction
        "created": datetime.now().strftime("%Y-%m-%d"),
        "last_validated": datetime.now().strftime("%Y-%m-%d"),
        "context": context
    }

    return rule


def extract_from_success(
    task_description: str,
    approach_used: str,
    why_it_worked: str,
    category: str = "workflow",
    source_episode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract a rule from a successful approach.

    Args:
        task_description: What task was accomplished
        approach_used: How it was done
        why_it_worked: Why this approach succeeded
        category: Rule category (workflow, tool, quality)
        source_episode: Episode ID if from an episode

    Returns:
        Candidate rule dict
    """
    rule_id = generate_rule_id(category)
    keywords = extract_keywords(f"{task_description} {approach_used}")

    rule = {
        "id": rule_id,
        "name": f"Use {approach_used[:30]}..." if len(approach_used) > 30 else f"Use {approach_used}",
        "category": category,
        "type": "soft",
        "priority": 2,
        "trigger_keywords": keywords,
        "condition": {
            "when": task_description,
            "task_patterns": keywords[:5]
        },
        "action": {
            "approach": approach_used,
            "reason": why_it_worked
        },
        "source_episode": source_episode,
        "confidence": 0.5,
        "validations": 1,
        "created": datetime.now().strftime("%Y-%m-%d"),
        "last_validated": datetime.now().strftime("%Y-%m-%d")
    }

    return rule


def save_candidate(rule: Dict[str, Any]) -> str:
    """Save a rule to candidates directory."""
    CANDIDATES_DIR.mkdir(exist_ok=True)

    rule_id = rule.get("id", "unknown")
    file_path = CANDIDATES_DIR / f"{rule_id}.json"

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(rule, f, indent=2)

    return str(file_path)


def extract_from_episode(episode: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract rules from a completed episode.

    Analyzes the episode result and actions to identify
    potential rules.
    """
    rules = []
    result = episode.get("result", "")
    goal = episode.get("goal", "")
    actions = episode.get("actions", [])

    if result == "failed":
        # Extract failure rule
        result_summary = episode.get("result_summary", "Unknown failure")
        rule = extract_from_failure(
            failure_description=result_summary,
            lesson_learned=f"Avoid: {result_summary}",
            context=goal,
            source_episode=episode.get("id")
        )
        rules.append(rule)

    elif result == "success":
        # Extract success pattern if there's something notable
        if len(actions) >= 3:
            approach = ", ".join([a.get("summary", "")[:30] for a in actions[:3]])
            rule = extract_from_success(
                task_description=goal,
                approach_used=approach,
                why_it_worked="Completed successfully",
                source_episode=episode.get("id")
            )
            rules.append(rule)

    return rules


def run(
    extraction_type: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Main entry point for rule extraction.

    Args:
        extraction_type: 'failure', 'success', or 'episode'
        **kwargs: Arguments for the specific extraction type

    Returns:
        Extraction result with candidate rule(s)
    """
    if extraction_type == "failure":
        rule = extract_from_failure(
            failure_description=kwargs.get("failure_description", ""),
            lesson_learned=kwargs.get("lesson_learned", ""),
            context=kwargs.get("context"),
            source_episode=kwargs.get("source_episode")
        )
        path = save_candidate(rule)
        return {
            "success": True,
            "rule_id": rule["id"],
            "saved_to": path,
            "rule": rule
        }

    elif extraction_type == "success":
        rule = extract_from_success(
            task_description=kwargs.get("task_description", ""),
            approach_used=kwargs.get("approach_used", ""),
            why_it_worked=kwargs.get("why_it_worked", ""),
            category=kwargs.get("category", "workflow"),
            source_episode=kwargs.get("source_episode")
        )
        path = save_candidate(rule)
        return {
            "success": True,
            "rule_id": rule["id"],
            "saved_to": path,
            "rule": rule
        }

    elif extraction_type == "episode":
        episode = kwargs.get("episode", {})
        rules = extract_from_episode(episode)
        results = []
        for rule in rules:
            path = save_candidate(rule)
            results.append({
                "rule_id": rule["id"],
                "saved_to": path
            })
        return {
            "success": True,
            "rules_extracted": len(rules),
            "results": results
        }

    else:
        return {
            "success": False,
            "error": f"Unknown extraction type: {extraction_type}"
        }


if __name__ == "__main__":
    # Test extraction
    result = run(
        extraction_type="failure",
        failure_description="Image generation produced distorted faces",
        lesson_learned="Use web search for face/portrait images instead of AI generation"
    )
    print(json.dumps(result, indent=2))
