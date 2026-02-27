"""
Rules Guard - Layer 7: Rule-based enforcement
==============================================

Checks tool calls against active rules from the rules index.
For "hard" rules with enforcement="PreToolUse", provides warnings or blocks.
For "soft" rules, provides guidance only.

Integrates with:
- rules.py: Rule loading and matching
- policy_gate.py: As Layer 7 check
- enforcement_patterns.json: Pattern-based enforcement

Design:
- Rules are matched by trigger_keywords against tool name + args
- Hard rules with PreToolUse enforcement can block execution
- All rule checks are logged for audit trail
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RuleCheckResult:
    """Result of checking rules against a tool call."""
    allowed: bool
    matched_rules: List[Dict]
    hard_violations: List[Dict]  # Hard rules that should block
    soft_warnings: List[Dict]    # Soft rules that provide guidance
    message: str

    @property
    def has_violations(self) -> bool:
        return len(self.hard_violations) > 0


# Paths
def get_agent_home() -> str:
    return os.environ.get("DURO_AGENT_HOME", os.path.expanduser("~/.agent"))


def get_rules_dir() -> str:
    return os.path.join(get_agent_home(), "rules")


def get_index_path() -> str:
    return os.path.join(get_rules_dir(), "index.json")


def get_enforcement_patterns_path() -> str:
    return os.path.join(get_rules_dir(), "enforcement_patterns.json")


# Cache
_rules_cache = None
_rules_cache_time = None
CACHE_TTL_SECONDS = 60


def load_rules_index(force_reload: bool = False) -> Dict:
    """Load the rules index with caching."""
    global _rules_cache, _rules_cache_time

    now = datetime.now()
    if not force_reload and _rules_cache is not None:
        if _rules_cache_time and (now - _rules_cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return _rules_cache

    index_path = get_index_path()
    if not os.path.exists(index_path):
        return {"active_rules": [], "soft_rules": []}

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            _rules_cache = json.load(f)
            _rules_cache_time = now
            return _rules_cache
    except Exception:
        return {"active_rules": [], "soft_rules": []}


def load_rule_content(rule: Dict) -> Optional[Dict]:
    """Load full rule content from file."""
    rules_dir = get_rules_dir()
    rule_file = rule.get("file", "")
    if not rule_file:
        return None

    filepath = os.path.join(rules_dir, rule_file)
    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def increment_rule_validation(rule: Dict) -> bool:
    """
    Increment the validation count for a matched rule.
    This proves the rule is catching real cases.

    Returns True if successfully incremented, False otherwise.
    """
    rules_dir = get_rules_dir()
    rule_file = rule.get("file", "")
    if not rule_file:
        return False

    filepath = os.path.join(rules_dir, rule_file)
    if not os.path.exists(filepath):
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = json.load(f)

        # Increment validations
        current = content.get("validations", 0)
        content["validations"] = current + 1
        content["last_validated"] = datetime.now().strftime("%Y-%m-%d")

        # Write back
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)

        return True
    except Exception:
        return False


def extract_context_from_tool_call(tool_name: str, arguments: Dict) -> str:
    """
    Extract searchable context from a tool call.
    This is what we match against trigger_keywords.
    """
    parts = [tool_name.lower()]

    # Add argument values that might be relevant
    for key, value in arguments.items():
        if isinstance(value, str):
            # Add the value (lowercased)
            parts.append(value.lower())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item.lower())

    return " ".join(parts)


def check_rules_for_tool(
    tool_name: str,
    arguments: Dict,
    enforce_hard: bool = True
) -> RuleCheckResult:
    """
    Check if any rules apply to this tool call.

    Args:
        tool_name: Name of the tool being called
        arguments: Tool arguments
        enforce_hard: If True, hard rules with PreToolUse enforcement will block

    Returns:
        RuleCheckResult with matched rules and whether to allow/block
    """
    index = load_rules_index()

    # Get all rules (active + soft)
    all_rules = index.get("active_rules", []) + index.get("soft_rules", [])

    # Extract context for matching
    context = extract_context_from_tool_call(tool_name, arguments)

    matched_rules = []
    hard_violations = []
    soft_warnings = []

    for rule in all_rules:
        keywords = rule.get("trigger_keywords", [])
        rule_type = rule.get("type", "soft")
        enforcement = rule.get("enforcement", "none")

        # Check if any keyword matches
        matched_keyword = None
        for kw in keywords:
            if kw.lower() in context:
                matched_keyword = kw
                break

        if matched_keyword:
            # Load full content for matched rule
            content = load_rule_content(rule)

            # Auto-increment validation count (proves rule catches real cases)
            increment_rule_validation(rule)

            match_info = {
                "rule": rule,
                "content": content,
                "matched_keyword": matched_keyword,
            }
            matched_rules.append(match_info)

            # Categorize by type and enforcement
            if rule_type == "hard" and enforcement == "PreToolUse":
                hard_violations.append(match_info)
            elif rule_type == "soft":
                soft_warnings.append(match_info)

    # Determine if we should block
    allowed = True
    message = ""

    if hard_violations and enforce_hard:
        allowed = False
        violation_names = [v["rule"]["name"] for v in hard_violations]
        message = f"Blocked by rule(s): {', '.join(violation_names)}"
    elif soft_warnings:
        warning_names = [w["rule"]["name"] for w in soft_warnings]
        message = f"Guidance: {', '.join(warning_names)}"
    else:
        message = "No applicable rules"

    return RuleCheckResult(
        allowed=allowed,
        matched_rules=matched_rules,
        hard_violations=hard_violations,
        soft_warnings=soft_warnings,
        message=message,
    )


def format_rule_guidance(result: RuleCheckResult) -> str:
    """Format rule check result as human-readable guidance."""
    if not result.matched_rules:
        return ""

    lines = []

    if result.hard_violations:
        lines.append("## Rule Violations (BLOCKED)")
        for v in result.hard_violations:
            rule = v["rule"]
            content = v.get("content", {})
            lines.append(f"- **{rule['name']}** (triggered by: {v['matched_keyword']})")
            if content:
                prevention = content.get("prevention", {})
                if isinstance(prevention, dict):
                    before = prevention.get("before_action", "")
                    if before:
                        lines.append(f"  → {before}")
        lines.append("")

    if result.soft_warnings:
        lines.append("## Rule Guidance")
        for w in result.soft_warnings:
            rule = w["rule"]
            lines.append(f"- **{rule['name']}** (triggered by: {w['matched_keyword']})")
        lines.append("")

    return "\n".join(lines)


def check_enforcement_patterns(
    tool_name: str,
    arguments: Dict
) -> Tuple[bool, str, Optional[str]]:
    """
    Check enforcement_patterns.json for regex-based blocks.
    This is separate from rules and handles low-level pattern matching.

    Returns:
        (allowed, reason, matched_pattern_id)
    """
    patterns_path = get_enforcement_patterns_path()
    if not os.path.exists(patterns_path):
        return True, "No enforcement patterns", None

    try:
        with open(patterns_path, "r", encoding="utf-8") as f:
            patterns_data = json.load(f)
    except Exception:
        return True, "Could not load patterns", None

    enforcement_rules = patterns_data.get("enforcement_rules", [])

    # Only check patterns for the matching tool
    for er in enforcement_rules:
        if er.get("tool") != tool_name:
            continue

        action = er.get("action", "warn")
        patterns = er.get("patterns", [])

        # Build the text to check (usually command for Bash)
        text_to_check = ""
        if tool_name == "Bash":
            text_to_check = arguments.get("command", "")
        elif tool_name == "Edit":
            text_to_check = f"{arguments.get('old_string', '')} {arguments.get('new_string', '')}"
        elif tool_name == "Write":
            text_to_check = arguments.get("content", "")
        else:
            # Generic: join all string arguments
            text_to_check = " ".join(
                str(v) for v in arguments.values() if isinstance(v, str)
            )

        # Check each pattern
        for p in patterns:
            regex = p.get("regex", "")
            flags = p.get("flags", "")

            try:
                re_flags = 0
                if "i" in flags:
                    re_flags |= re.IGNORECASE

                if re.search(regex, text_to_check, re_flags):
                    if action == "block":
                        return False, f"Pattern blocked: {p.get('description', regex)}", er.get("id")
                    # else warn - still allow but note it
            except re.error:
                continue

    return True, "No pattern violations", None


# Main entry point for policy gate integration
def check_rules_layer(
    tool_name: str,
    arguments: Dict,
    enforce: bool = True
) -> Tuple[bool, str, List[Dict]]:
    """
    Main entry point for Layer 7 (Rules Guard) check.

    Called by policy_gate.py after other layers.

    Args:
        tool_name: Name of the tool being called
        arguments: Tool arguments
        enforce: If True, hard rules can block execution

    Returns:
        (allowed, message, matched_rules)
    """
    # Check rules index
    result = check_rules_for_tool(tool_name, arguments, enforce_hard=enforce)

    # Also check enforcement patterns (for regex-based blocks)
    pattern_allowed, pattern_reason, pattern_id = check_enforcement_patterns(tool_name, arguments)

    # Combine results
    if not pattern_allowed:
        return False, pattern_reason, result.matched_rules

    if not result.allowed:
        return False, result.message, result.matched_rules

    return True, result.message, result.matched_rules


# CLI test
if __name__ == "__main__":
    print("Rules Guard - Layer 7")
    print("=" * 50)

    # Test with a sample tool call
    test_tool = "Bash"
    test_args = {"command": "git commit -m 'test'"}

    print(f"\nTesting: {test_tool} with args: {test_args}")

    allowed, message, rules = check_rules_layer(test_tool, test_args)

    print(f"Allowed: {allowed}")
    print(f"Message: {message}")
    print(f"Matched rules: {len(rules)}")

    for r in rules:
        print(f"  - {r['rule']['name']} (keyword: {r['matched_keyword']})")
