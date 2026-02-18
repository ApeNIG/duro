"""
Skill: code_quality_verifier
Description: Check code against quality rules with high accuracy
Version: 1.0.0
Tier: core

12 high-accuracy rules across 3 categories:
- TypeScript (4 rules): any, unsafe assertions, as unknown as, explicit any
- React (4 rules): conditional hooks, missing effect deps, inline components, key prop
- Security (4 rules): dangerouslySetInnerHTML, eval, secrets, innerHTML

Design principles:
- Rules are data-only (RuleSpec), not executable code
- Each rule has scope, timeout, confidence
- Supports .duroignore and inline // duro-ignore: rule_id
- Outputs devkit-compatible JSON

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# Import from skill_runner
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))
try:
    from skill_runner import (
        SkillRunner, SkillResult, Finding, CheckResult,
        RuleSpec, RuleEngine, Severity, generate_run_id, get_timestamp
    )
except ImportError:
    # Fallback for standalone use
    from enum import Enum

    class Severity(Enum):
        INFO = "info"
        WARN = "warn"
        ERROR = "error"


# Skill metadata
SKILL_META = {
    "name": "code_quality_verifier",
    "description": "Check code against quality rules with high accuracy",
    "tier": "tested",
    "version": "1.0.1",
    "author": "duro",
    "triggers": ["check quality", "lint code", "code review", "quality check"],
    "validated": "2026-02-18",
}

# Required capabilities
REQUIRES = ["read_file", "glob_files"]


# === RULE DEFINITIONS ===

# TypeScript Rules (4)
TS_RULES = [
    {
        "id": "ts_no_any",
        "name": "No any type",
        "pattern": r":\s*any\b",
        "message": "Avoid using 'any' type - it disables type checking",
        "severity": Severity.WARN,
        "confidence": 0.95,
        "scope": ["**/*.ts", "**/*.tsx"],
        "suggested_fix": "Use a specific type or 'unknown' if type is truly unknown",
    },
    {
        "id": "ts_no_as_any",
        "name": "No as any assertion",
        "pattern": r"\bas\s+any\b",
        "message": "Avoid 'as any' assertions - they bypass type safety",
        "severity": Severity.ERROR,
        "confidence": 0.98,
        "scope": ["**/*.ts", "**/*.tsx"],
        "suggested_fix": "Use proper type narrowing or fix the underlying type issue",
    },
    {
        "id": "ts_no_as_unknown_as",
        "name": "No double assertion via unknown",
        "pattern": r"\bas\s+unknown\s+as\b",
        "message": "Double assertion 'as unknown as X' bypasses type safety",
        "severity": Severity.ERROR,
        "confidence": 0.99,
        "scope": ["**/*.ts", "**/*.tsx"],
        "suggested_fix": "Fix the type mismatch instead of forcing with double assertion",
    },
    {
        "id": "ts_no_non_null_assertion",
        "name": "Avoid non-null assertion",
        "pattern": r"\w+!\.",
        "message": "Non-null assertion (!) can cause runtime errors",
        "severity": Severity.INFO,
        "confidence": 0.7,  # Lower confidence - sometimes legitimate
        "scope": ["**/*.ts", "**/*.tsx"],
        "suggested_fix": "Use optional chaining (?.) or proper null checks",
    },
]

# React Rules (4)
REACT_RULES = [
    {
        "id": "react_no_conditional_hooks",
        "name": "No conditional hooks",
        "pattern": r"if\s*\([^)]*\)\s*\{[^}]*\buse[A-Z]\w+\s*\(",
        "message": "Hooks must not be called conditionally",
        "severity": Severity.ERROR,
        "confidence": 0.85,
        "scope": ["**/*.tsx", "**/*.jsx"],
        "suggested_fix": "Move hook call outside the conditional or use conditional logic inside the hook",
    },
    {
        "id": "react_effect_missing_deps_heuristic",
        "name": "Effect may have missing deps",
        "pattern": r"useEffect\s*\(\s*\(\)\s*=>\s*\{[^}]*\b(props|state)\.\w+[^}]*\}\s*,\s*\[\s*\]\s*\)",
        "message": "useEffect with empty deps array references props/state - may be stale",
        "severity": Severity.WARN,
        "confidence": 0.6,  # Heuristic - may have false positives
        "scope": ["**/*.tsx", "**/*.jsx"],
        "suggested_fix": "Add referenced variables to dependency array or verify intent",
    },
    {
        "id": "react_no_inline_component",
        "name": "No inline component definition",
        "pattern": r"return\s*\([^)]*<[A-Z]\w+[^>]*>\s*\{[^}]*=>\s*<",
        "message": "Inline component in render causes remount on every render",
        "severity": Severity.WARN,
        "confidence": 0.7,
        "scope": ["**/*.tsx", "**/*.jsx"],
        "suggested_fix": "Extract the component outside the render function",
    },
    {
        "id": "react_map_missing_key",
        "name": "Map may be missing key prop",
        "pattern": r"\.map\s*\([^)]*=>\s*<[A-Z]\w+(?![^>]*\bkey\s*=)[^>]*>",
        "message": "Component in .map() should have a key prop",
        "severity": Severity.WARN,
        "confidence": 0.75,
        "scope": ["**/*.tsx", "**/*.jsx"],
        "suggested_fix": "Add key={uniqueId} prop to the mapped component",
    },
]

# Security Rules (4)
SECURITY_RULES = [
    {
        "id": "sec_no_dangerous_html",
        "name": "No dangerouslySetInnerHTML",
        "pattern": r"dangerouslySetInnerHTML",
        "message": "dangerouslySetInnerHTML can lead to XSS vulnerabilities",
        "severity": Severity.ERROR,
        "confidence": 0.99,
        "scope": ["**/*.tsx", "**/*.jsx", "**/*.ts", "**/*.js"],
        "suggested_fix": "Use a sanitizer library or avoid raw HTML injection",
    },
    {
        "id": "sec_no_eval",
        "name": "No eval()",
        "pattern": r"\beval\s*\(",
        "message": "eval() can execute arbitrary code - major security risk",
        "severity": Severity.ERROR,
        "confidence": 0.99,
        "scope": ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"],
        "suggested_fix": "Use JSON.parse() for JSON, or safer alternatives",
    },
    {
        "id": "sec_no_inner_html",
        "name": "No innerHTML assignment",
        "pattern": r"\.innerHTML\s*=",
        "message": "Direct innerHTML assignment can lead to XSS",
        "severity": Severity.ERROR,
        "confidence": 0.95,
        "scope": ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"],
        "suggested_fix": "Use textContent or sanitize HTML before assignment",
    },
    {
        "id": "sec_no_hardcoded_secrets",
        "name": "No hardcoded secrets",
        "pattern": r"(password|secret|api_key|apikey|api-key|token|auth)\s*[=:]\s*['\"][^'\"]{8,}['\"]",
        "message": "Possible hardcoded secret detected",
        "severity": Severity.ERROR,
        "confidence": 0.8,
        "scope": ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.env*"],
        "suggested_fix": "Move secrets to environment variables",
    },
]

# All rules combined
ALL_RULES = TS_RULES + REACT_RULES + SECURITY_RULES


@dataclass
class QualityResult:
    """Result of quality verification."""
    success: bool
    files_checked: int
    findings: List[Dict[str, Any]] = field(default_factory=list)
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_rule: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


def check_file(
    content: str,
    file_path: str,
    rules: List[Dict],
    suppressed_rules: set = None
) -> List[Dict[str, Any]]:
    """
    Check a single file against all applicable rules.

    Returns list of findings.
    """
    findings = []
    suppressed_rules = suppressed_rules or set()
    lines = content.splitlines()

    for rule in rules:
        rule_id = rule["id"]

        # Check if rule applies to this file type
        file_ext = os.path.splitext(file_path)[1]
        scope = rule.get("scope", ["**/*"])
        applies = any(
            file_path.endswith(s.replace("**/*", "").replace("*", ""))
            for s in scope
        )
        if not applies:
            continue

        pattern = re.compile(rule["pattern"], re.IGNORECASE if rule.get("case_insensitive") else 0)

        for line_num, line in enumerate(lines, 1):
            # Check inline suppression
            if f"duro-ignore: {rule_id}" in line or f"duro-ignore:{rule_id}" in line:
                continue

            # Check global suppression
            if rule_id in suppressed_rules:
                continue

            if pattern.search(line):
                findings.append({
                    "id": f"{rule_id}_{line_num}",
                    "rule_id": rule_id,
                    "type": "quality_violation",
                    "severity": rule["severity"].value if hasattr(rule["severity"], "value") else rule["severity"],
                    "confidence": rule["confidence"],
                    "file": file_path,
                    "line": line_num,
                    "snippet": line.strip()[:100],
                    "message": rule["message"],
                    "suggested_fix": rule.get("suggested_fix"),
                })

    return findings


def load_duroignore(code_dir: str) -> set:
    """Load suppressed rules from .duroignore file."""
    suppressed = set()
    ignore_file = os.path.join(code_dir, ".duroignore")

    if os.path.exists(ignore_file):
        with open(ignore_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Format: rule_id or rule_id:path_pattern
                    if ":" not in line:
                        suppressed.add(line)

    return suppressed


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            code_dir: str - path to code directory
            rules: list (optional) - rule IDs to run (default: all)
            exclude_rules: list (optional) - rule IDs to exclude
            file_pattern: str (optional) - glob pattern for files
        }
        tools: {
            read_file: callable - read code files
            glob_files: callable - find files by pattern
        }
        context: {run_id, constraints}

    Returns:
        {success, findings, by_severity, by_rule, files_checked, errors}
    """
    code_dir = args.get("code_dir", "")
    rule_ids = args.get("rules", None)  # None = all rules
    exclude_rules = set(args.get("exclude_rules", []))
    file_pattern = args.get("file_pattern", "**/*.{ts,tsx,js,jsx}")
    output_format = args.get("output_format", "standard")
    run_id = context.get("run_id", generate_run_id() if 'generate_run_id' in dir() else "run_unknown")

    if not code_dir:
        return {"success": False, "error": "code_dir is required"}

    result = QualityResult(success=True, files_checked=0)

    # Select rules
    rules = ALL_RULES
    if rule_ids:
        rules = [r for r in ALL_RULES if r["id"] in rule_ids]
    rules = [r for r in rules if r["id"] not in exclude_rules]

    if not rules:
        return {"success": True, "findings": [], "message": "No rules selected"}

    # Load suppressions
    suppressed_rules = load_duroignore(code_dir)

    # Find files
    try:
        # Try multiple patterns
        all_files = []
        for pattern in ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"]:
            files = tools["glob_files"](pattern=pattern, path=code_dir)
            if files:
                all_files.extend(files if isinstance(files, list) else files.get("files", []))

        if not all_files:
            return {"success": True, "findings": [], "message": "No files found to check"}

        result.files_checked = len(all_files)

    except Exception as e:
        result.errors.append(f"Failed to find files: {str(e)}")
        result.success = False
        return _format_result(result)

    # Check each file
    for file_path in all_files:
        try:
            content = tools["read_file"](file_path)
            if content:
                findings = check_file(content, file_path, rules, suppressed_rules)
                result.findings.extend(findings)
        except Exception as e:
            result.errors.append(f"Failed to read {file_path}: {str(e)}")

    # Aggregate by severity and rule
    for finding in result.findings:
        severity = finding["severity"]
        rule_id = finding["rule_id"]
        result.by_severity[severity] = result.by_severity.get(severity, 0) + 1
        result.by_rule[rule_id] = result.by_rule.get(rule_id, 0) + 1

    # Determine success (no errors = success)
    error_count = result.by_severity.get("error", 0)
    result.success = error_count == 0

    if output_format == "devkit":
        return _format_devkit_result(result, run_id, code_dir)
    return _format_result(result)


def _format_result(result: QualityResult) -> Dict[str, Any]:
    """Format result for return."""
    return {
        "success": result.success,
        "files_checked": result.files_checked,
        "total_findings": len(result.findings),
        "by_severity": result.by_severity,
        "by_rule": result.by_rule,
        "findings": result.findings,
        "errors": result.errors,
    }


def _format_devkit_result(result: QualityResult, run_id: str, code_dir: str) -> Dict[str, Any]:
    """Format result in devkit-compatible JSON format."""
    import json
    from datetime import datetime

    return {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "repo": code_dir,
        "success": result.success,

        "checks": [
            {
                "name": "code_quality_verification",
                "success": result.success,
                "duration_ms": 0,
            }
        ],

        "findings": result.findings,

        "metrics": {
            "files_checked": result.files_checked,
            "total_findings": len(result.findings),
            "by_severity": result.by_severity,
            "by_rule": result.by_rule,
        },

        "errors": result.errors,
    }


def to_devkit_json(result: QualityResult, run_id: str, code_dir: str) -> str:
    """Export result as devkit-compatible JSON string."""
    import json
    return json.dumps(_format_devkit_result(result, run_id, code_dir), indent=2)


# CLI for testing
if __name__ == "__main__":
    print("code_quality_verifier Skill v1.0")
    print("=" * 40)
    print(f"\nRules ({len(ALL_RULES)} total):")
    print("\nTypeScript rules:")
    for r in TS_RULES:
        print(f"  - {r['id']}: {r['name']} [{r['severity'].value}]")
    print("\nReact rules:")
    for r in REACT_RULES:
        print(f"  - {r['id']}: {r['name']} [{r['severity'].value}]")
    print("\nSecurity rules:")
    for r in SECURITY_RULES:
        print(f"  - {r['id']}: {r['name']} [{r['severity'].value}]")
