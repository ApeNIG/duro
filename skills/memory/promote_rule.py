"""
Skill: promote_rule
Description: Promote a candidate rule to active status - closes the candidate→active loop
Version: 1.1.0
Tier: tested

Phase 4 automation: validated candidates become active laws.

Algorithm:
1. Find candidate rule by ID in candidates/*/
2. Check validations >= threshold (default 3, or force=True to bypass)
3. Move file from candidates/{category}/ to {category}/
4. Update rule status from "candidate" to "active"
5. Add entry to index.json active_rules
6. Update statistics

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import os
import json
import shutil
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


# Skill metadata
SKILL_META = {
    "name": "promote_rule",
    "description": "Promote a candidate rule to active status - closes the candidate→active loop",
    "tier": "tested",
    "version": "1.1.0",
    "author": "duro",
    "origin": "Phase 4 evolution - validated candidates become permanent laws",
    "validated": "2026-02-27",
    "triggers": [
        "promote rule", "activate rule", "candidate to active",
        "make rule active", "enable rule"
    ],
    "keywords": [
        "promote", "rule", "candidate", "active", "law",
        "validation", "enforcement", "phase4"
    ],
    "phase": "4.0",
}

# Default configuration
DEFAULT_CONFIG = {
    "min_validations": 3,     # Validations needed before promotion
    "min_age_hours": 24,      # Candidate must exist for this long (prevents instant law)
    "min_severity": "medium", # Minimum severity to auto-promote
    "force": False,           # Bypass all safety checks
    "dry_run": False,         # If True, don't make changes
}

# Severity ranking for safety latch
SEVERITY_RANK = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

# Required capabilities
REQUIRES = []

# Default timeout
DEFAULT_TIMEOUT = 30

# Category to directory mapping
CATEGORY_DIRS = {
    "failures": "failures",
    "quality": "quality",
    "safety": "safety",
    "tools": "tools",
    "workflows": "workflows",
}


def get_agent_home() -> str:
    """Get the agent home directory."""
    return os.environ.get("DURO_AGENT_HOME", os.path.expanduser("~/.agent"))


def get_rules_dir() -> str:
    return os.path.join(get_agent_home(), "rules")


def find_candidate_rule(rule_id: str) -> Optional[Tuple[str, Dict]]:
    """
    Find a candidate rule by ID.
    Returns (filepath, rule_data) or None if not found.
    """
    rules_dir = get_rules_dir()
    candidates_dir = os.path.join(rules_dir, "candidates")

    if not os.path.exists(candidates_dir):
        return None

    # Search in all candidate subdirectories
    for category in os.listdir(candidates_dir):
        category_path = os.path.join(candidates_dir, category)
        if not os.path.isdir(category_path):
            continue

        for filename in os.listdir(category_path):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(category_path, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    rule = json.load(f)
                    if rule.get("id") == rule_id:
                        return filepath, rule
            except Exception:
                continue

    return None


def get_next_rule_id(category: str, rules_dir: str) -> str:
    """Generate the next rule ID for a category."""
    index_path = os.path.join(rules_dir, "index.json")

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)

        # Find highest ID number for this category
        prefix = f"rule_{category[:4]}_"
        existing_ids = []

        for rule in index.get("active_rules", []):
            rule_id = rule.get("id", "")
            if rule_id.startswith(prefix):
                try:
                    num = int(rule_id.split("_")[-1])
                    existing_ids.append(num)
                except ValueError:
                    continue

        next_num = max(existing_ids, default=0) + 1
        return f"{prefix}{next_num:03d}"
    except Exception:
        # Fallback
        timestamp = datetime.now().strftime("%Y%m%d")
        return f"rule_{category[:4]}_{timestamp}"


def promote_candidate(
    filepath: str,
    rule: Dict,
    rules_dir: str,
    dry_run: bool = False
) -> Tuple[bool, str, str]:
    """
    Promote a candidate rule to active.
    Returns (success, new_filepath, message).
    """
    category = rule.get("category", "failures")
    category_dir = CATEGORY_DIRS.get(category, category)

    # Target directory
    target_dir = os.path.join(rules_dir, category_dir)

    if dry_run:
        return True, "", f"[DRY RUN] Would move to {target_dir}/"

    # Ensure target directory exists
    os.makedirs(target_dir, exist_ok=True)

    # Update rule status
    rule["status"] = "active"
    rule["promoted_at"] = datetime.utcnow().strftime("%Y-%m-%d")
    rule["last_validated"] = datetime.utcnow().strftime("%Y-%m-%d")

    # Generate filename
    filename = os.path.basename(filepath)
    target_path = os.path.join(target_dir, filename)

    try:
        # Write updated rule to new location
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(rule, f, indent=2)

        # Remove from candidates
        os.remove(filepath)

        return True, target_path, f"Promoted to {target_path}"
    except Exception as e:
        return False, "", str(e)


def update_index(
    rule: Dict,
    new_filepath: str,
    rules_dir: str,
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Add promoted rule to index.json.
    Returns (success, message).
    """
    index_path = os.path.join(rules_dir, "index.json")

    if dry_run:
        return True, "[DRY RUN] Would update index.json"

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)

        # Get relative path for file reference
        rel_path = os.path.relpath(new_filepath, rules_dir)

        # Create index entry
        entry = {
            "id": rule["id"],
            "name": rule.get("name", "Unnamed Rule"),
            "file": rel_path.replace("\\", "/"),
            "type": rule.get("type", "hard"),
            "priority": rule.get("priority", 1),
            "enforcement": "PreToolUse",  # Hard rules block at policy gate Layer 7
            "measurable": True,
            "trigger_keywords": rule.get("trigger_keywords", []),
        }

        # Add to active_rules
        index["active_rules"].append(entry)

        # Update statistics
        stats = index.get("statistics", {})
        stats["total_active"] = len(index["active_rules"])
        candidates_count = stats.get("candidates", 44)
        stats["candidates"] = max(0, candidates_count - 1)
        index["statistics"] = stats

        # Update last_updated
        index["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")

        # Write back
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)

        return True, "Index updated"
    except Exception as e:
        return False, str(e)


def format_report(
    rule_id: str,
    rule: Optional[Dict],
    promoted: bool,
    new_path: str,
    index_updated: bool,
    messages: List[str],
    dry_run: bool
) -> str:
    """Format the skill report."""
    lines = []
    lines.append("## Promote Rule Report")
    lines.append("")

    mode = "[DRY RUN] " if dry_run else ""

    if not rule:
        lines.append(f"**{mode}Error:** Rule `{rule_id}` not found in candidates")
        return "\n".join(lines)

    lines.append(f"**Rule:** {rule.get('name', 'Unnamed')}")
    lines.append(f"**ID:** `{rule_id}`")
    lines.append(f"**Category:** {rule.get('category', 'unknown')}")
    lines.append(f"**Validations:** {rule.get('validations', 0)}")
    lines.append(f"**Severity:** {rule.get('severity', 'medium')}")
    lines.append("")

    if promoted:
        lines.append(f"### {mode}Promotion Successful")
        lines.append(f"- Moved to: `{new_path}`")
        lines.append(f"- Status: `active`")
        if index_updated:
            lines.append(f"- Index updated")
    else:
        lines.append(f"### {mode}Promotion Failed")
        for msg in messages:
            lines.append(f"- {msg}")

    lines.append("")
    lines.append("### Prevention (now enforced)")
    lines.append(f"> {rule.get('prevention', {}).get('before_action', 'N/A')}")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            rule_id: str - ID of candidate rule to promote (REQUIRED)
            min_validations: int (default 3) - Minimum validations required
            force: bool (default False) - Bypass validation check
            dry_run: bool (default False) - If True, don't make changes
        }
        tools: {} (no tools required)
        context: {run_id, timeout}

    Returns:
        {
            success: bool,
            report: str,
            promoted: bool,
            rule_id: str,
            new_path: str,
            elapsed_seconds: float,
        }
    """
    start_time = time.time()

    # Parse args
    rule_id = args.get("rule_id")
    if not rule_id:
        return {
            "success": False,
            "error": "rule_id is required",
            "report": "**Error:** rule_id argument is required",
        }

    min_validations = args.get("min_validations", DEFAULT_CONFIG["min_validations"])
    force = args.get("force", DEFAULT_CONFIG["force"])
    dry_run = args.get("dry_run", DEFAULT_CONFIG["dry_run"])

    rules_dir = get_rules_dir()
    messages = []

    # ==============================
    # Phase 1: Find candidate
    # ==============================
    result = find_candidate_rule(rule_id)

    if not result:
        report = format_report(rule_id, None, False, "", False, ["Not found"], dry_run)
        return {
            "success": False,
            "error": f"Candidate rule '{rule_id}' not found",
            "report": report,
            "promoted": False,
            "rule_id": rule_id,
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    filepath, rule = result

    # ==============================
    # Phase 2: Safety latch checks
    # ==============================
    validations = rule.get("validations", 0)
    severity = rule.get("severity", "medium")
    created_date = rule.get("created", "")
    min_age_hours = args.get("min_age_hours", DEFAULT_CONFIG["min_age_hours"])
    min_severity = args.get("min_severity", DEFAULT_CONFIG["min_severity"])

    # Check 2a: Validations threshold
    if validations < min_validations and not force:
        messages.append(f"Insufficient validations: {validations}/{min_validations}")
        messages.append("Use force=True to bypass, or validate the rule more")

        report = format_report(rule_id, rule, False, "", False, messages, dry_run)
        return {
            "success": False,
            "error": f"Rule needs {min_validations - validations} more validations",
            "report": report,
            "promoted": False,
            "rule_id": rule_id,
            "validations": validations,
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    # Check 2b: Severity threshold (prevent low-severity auto-promotion)
    severity_rank = SEVERITY_RANK.get(severity, 1)
    min_severity_rank = SEVERITY_RANK.get(min_severity, 1)

    if severity_rank < min_severity_rank and not force:
        messages.append(f"Severity '{severity}' below threshold '{min_severity}'")
        messages.append("Use force=True to bypass severity check")

        report = format_report(rule_id, rule, False, "", False, messages, dry_run)
        return {
            "success": False,
            "error": f"Severity '{severity}' too low for auto-promotion",
            "report": report,
            "promoted": False,
            "rule_id": rule_id,
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    # Check 2c: Age threshold (prevent instant law from bursty failures)
    if created_date and min_age_hours > 0 and not force:
        try:
            # Try ISO timestamp first, fall back to date-only for backwards compat
            try:
                created_dt = datetime.strptime(created_date, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                created_dt = datetime.strptime(created_date, "%Y-%m-%d")
            age_hours = (datetime.utcnow() - created_dt).total_seconds() / 3600
            if age_hours < min_age_hours:
                messages.append(f"Candidate age {age_hours:.1f}h < {min_age_hours}h minimum")
                messages.append("Wait for candidate to mature, or use force=True")

                report = format_report(rule_id, rule, False, "", False, messages, dry_run)
                return {
                    "success": False,
                    "error": f"Candidate too young ({age_hours:.1f}h < {min_age_hours}h)",
                    "report": report,
                    "promoted": False,
                    "rule_id": rule_id,
                    "elapsed_seconds": round(time.time() - start_time, 2),
                }
        except ValueError:
            pass  # Invalid date format, skip age check

    # ==============================
    # Phase 3: Promote
    # ==============================
    promoted, new_path, msg = promote_candidate(filepath, rule, rules_dir, dry_run)
    messages.append(msg)

    if not promoted:
        report = format_report(rule_id, rule, False, "", False, messages, dry_run)
        return {
            "success": False,
            "error": f"Promotion failed: {msg}",
            "report": report,
            "promoted": False,
            "rule_id": rule_id,
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    # ==============================
    # Phase 4: Update index
    # ==============================
    index_updated, idx_msg = update_index(rule, new_path, rules_dir, dry_run)
    messages.append(idx_msg)

    # ==============================
    # Phase 5: Generate report
    # ==============================
    report = format_report(rule_id, rule, True, new_path, index_updated, messages, dry_run)

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "report": report,
        "promoted": True,
        "rule_id": rule_id,
        "new_path": new_path,
        "index_updated": index_updated,
        "elapsed_seconds": elapsed,
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("promote_rule Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Algorithm:")
    print("  1. Find candidate rule by ID")
    print("  2. Check validations >= threshold (default 3)")
    print("  3. Move from candidates/{category}/ to {category}/")
    print("  4. Update status to 'active'")
    print("  5. Add to index.json active_rules")
    print()
    print("Usage:")
    print("  promote_rule(rule_id='rule_failure_inc_abc123')")
    print("  promote_rule(rule_id='...', force=True)  # bypass validation")
    print()
    print("Default config:")
    for k, v in DEFAULT_CONFIG.items():
        print(f"  {k}: {v}")
