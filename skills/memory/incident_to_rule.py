"""
Skill: incident_to_rule
Description: Convert incident RCA prevention into candidate rules - closes the mistake→law loop
Version: 1.2.0
Tier: tested

Phase 4 automation: every mistake becomes a permanent law.

Algorithm:
1. Query incidents with severity >= threshold (default: high)
2. Filter to incidents with actionable prevention fields
3. Check if a rule already exists for this prevention pattern
4. Generate candidate rule JSON from failure_rule template
5. Save to candidates/failures/ directory
6. Track for promotion when validations >= threshold

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import os
import json
import re
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


# Skill metadata
SKILL_META = {
    "name": "incident_to_rule",
    "description": "Convert incident RCA prevention into candidate rules - closes the mistake→law loop",
    "tier": "tested",
    "version": "1.2.0",
    "author": "duro",
    "origin": "Phase 4 evolution - every mistake becomes a permanent law",
    "validated": "2026-02-26",
    "triggers": [
        "incident to rule", "promote incident", "mistake to law",
        "prevention to rule", "incident rule", "rca to rule"
    ],
    "keywords": [
        "incident", "rule", "prevention", "promote", "rca", "law",
        "candidate", "failure", "mistake", "permanent", "phase4"
    ],
    "phase": "4.0",
}

# Default configuration
DEFAULT_CONFIG = {
    "min_severity": "medium",       # Minimum severity to consider (low, medium, high, critical)
    "max_incidents": 50,            # Max incidents to process
    "validations_to_promote": 3,    # Validations needed before active promotion
    "dry_run": False,               # If True, don't create files
}

# Severity ranking
SEVERITY_RANK = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

# Required capabilities (get_artifact is optional, for fetching full incident data)
REQUIRES = ["query_memory"]

# Default timeout
DEFAULT_TIMEOUT = 60

# Paths (will be resolved relative to DURO_AGENT_HOME)
def get_agent_home() -> str:
    """Get the agent home directory."""
    return os.environ.get("DURO_AGENT_HOME", os.path.expanduser("~/.agent"))

def get_rules_dir() -> str:
    return os.path.join(get_agent_home(), "rules")

def get_candidates_dir() -> str:
    return os.path.join(get_rules_dir(), "candidates", "failures")

def get_index_path() -> str:
    return os.path.join(get_rules_dir(), "index.json")


# Banned phrases in prevention (too vague to be actionable)
BANNED_PHRASES = {
    "be careful",
    "remember to",
    "don't forget",
    "be more careful",
    "pay attention",
    "check more carefully",
    "be aware",
    "make sure",
}


def is_actionable_prevention(prevention: str) -> Tuple[bool, str]:
    """
    Check if a prevention is actionable (has a verb + artifact).
    Returns (is_actionable, reason).
    """
    if not prevention or len(prevention) < 10:
        return False, "Prevention too short"

    prevention_lower = prevention.lower()

    # Check for banned phrases
    for phrase in BANNED_PHRASES:
        if phrase in prevention_lower:
            return False, f"Contains vague phrase: '{phrase}'"

    # Check for action verbs (should have at least one)
    action_verbs = [
        "add", "create", "implement", "use", "always", "never", "ensure",
        "validate", "check", "verify", "test", "assert", "log", "cache",
        "convert", "wrap", "guard", "sanitize", "escape", "encode",
        "freeze", "immutable", "lock", "scope", "isolate", "sandbox"
    ]

    has_verb = any(verb in prevention_lower for verb in action_verbs)
    if not has_verb:
        return False, "No actionable verb found"

    return True, "Actionable"


def extract_keywords(text: str) -> List[str]:
    """Extract potential trigger keywords from prevention text."""
    # Common technical terms that could be triggers
    keywords = []

    text_lower = text.lower()

    # Extract nouns and technical terms
    patterns = [
        r'\b(config|configuration)\b',
        r'\b(security|secure)\b',
        r'\b(immutable|mutable)\b',
        r'\b(cache|caching)\b',
        r'\b(env|environment)\b',
        r'\b(path|paths)\b',
        r'\b(sync|synchron)\b',
        r'\b(database|db)\b',
        r'\b(api|endpoint)\b',
        r'\b(auth|authentication|authorization)\b',
        r'\b(inject|injection)\b',
        r'\b(validate|validation)\b',
        r'\b(sanitize|sanitization)\b',
        r'\b(timeout|retry)\b',
        r'\b(error|exception)\b',
        r'\b(deploy|deployment)\b',
        r'\b(test|testing)\b',
        r'\b(log|logging)\b',
        r'\b(permission|permissions)\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            keywords.append(match.group(1))

    # Extract quoted terms
    quoted = re.findall(r'"([^"]+)"', text)
    keywords.extend([q.lower() for q in quoted if len(q) < 30])

    # Extract backtick terms (code references)
    backtick = re.findall(r'`([^`]+)`', text)
    keywords.extend([b.lower() for b in backtick if len(b) < 30])

    return list(set(keywords))[:10]


def generate_rule_id(incident_id: str) -> str:
    """Generate a unique rule ID from incident ID."""
    # Create a short hash from incident ID
    hash_suffix = hashlib.md5(incident_id.encode()).hexdigest()[:6]
    return f"rule_failure_inc_{hash_suffix}"


def incident_to_candidate_rule(incident: Dict) -> Dict:
    """
    Convert an incident RCA to a candidate rule.
    """
    data = incident.get("data", incident)
    incident_id = incident.get("id", "unknown")

    symptom = data.get("symptom", "Unknown failure")
    actual_cause = data.get("actual_cause", "Unknown cause")
    prevention = data.get("prevention", "")
    fix = data.get("fix", "")
    severity = data.get("severity", "medium")
    tags = incident.get("tags", [])
    repro_steps = data.get("repro_steps", [])
    first_bad_boundary = data.get("first_bad_boundary", "")

    # Extract keywords for triggers
    trigger_keywords = extract_keywords(prevention + " " + symptom)
    if not trigger_keywords:
        trigger_keywords = [t.lower() for t in tags[:5]]

    # Build rule name from symptom
    rule_name = symptom[:60].strip()
    if len(symptom) > 60:
        rule_name = rule_name.rsplit(" ", 1)[0] + "..."

    rule_id = generate_rule_id(incident_id)

    # Build the candidate rule
    candidate = {
        "id": rule_id,
        "name": rule_name,
        "category": "failures",
        "type": "hard",
        "priority": 1 if severity in ("critical", "high") else 2,
        "trigger_keywords": trigger_keywords,
        "failure_pattern": {
            "symptom": symptom,
            "root_cause": actual_cause,
            "detection": first_bad_boundary or "Manual detection",
        },
        "prevention": {
            "before_action": prevention,
            "avoid": actual_cause,
            "alternative": fix,
        },
        "recovery": {
            "if_detected": fix,
            "cleanup": "Verify fix resolves the issue",
        },
        "examples": [
            {
                "scenario": symptom,
                "outcome": actual_cause,
                "lesson": prevention,
            }
        ],
        "repro_steps": repro_steps,
        "source_incident": incident_id,
        "source_tags": tags,
        "confidence": 0.7 if severity in ("critical", "high") else 0.5,
        "validations": 0,
        "severity": severity,
        "created": datetime.utcnow().strftime("%Y-%m-%d"),
        "last_validated": None,
        "status": "candidate",
    }

    return candidate


def increment_candidate_validation(
    filepath: str,
    incident_id: str,
    dry_run: bool = False
) -> Tuple[bool, int, str]:
    """
    Increment validation count on an existing candidate rule.
    Called when a new incident matches an existing candidate (recurrence = validation).

    IMPORTANT: Only increments if incident_id is NEW evidence (not already seen).
    dry_run=True returns what would happen without writing.

    Args:
        filepath: Path to the candidate rule JSON file
        incident_id: ID of the incident that validates this candidate
        dry_run: If True, don't actually write (purely observational)

    Returns:
        (did_increment, validation_count, message)
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            candidate = json.load(f)

        current = candidate.get("validations", 0)
        seen_incidents = candidate.get("seen_incidents", [])

        # Check if this incident is NEW evidence
        if incident_id in seen_incidents:
            return False, current, "already seen (no increment)"

        # New evidence - would increment
        new_count = current + 1

        if dry_run:
            return False, new_count, f"[DRY RUN] would increment to {new_count}"

        # Actually increment
        candidate["validations"] = new_count
        candidate["last_validated"] = datetime.utcnow().strftime("%Y-%m-%d")
        seen_incidents.append(incident_id)
        candidate["seen_incidents"] = seen_incidents[-10:]  # Keep last 10

        # Atomic write
        tmp_path = filepath + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(candidate, f, indent=2)
        os.replace(tmp_path, filepath)

        return True, new_count, f"incremented to {new_count}"
    except Exception as e:
        return False, 0, str(e)


def check_existing_rules(
    prevention: str,
    rules_index: Dict,
    incident_id: str = None,
    dry_run: bool = False
) -> Tuple[Optional[str], bool, str]:
    """
    Check if a similar rule already exists.
    If a matching candidate is found and incident_id is provided, increments its validations.

    Args:
        prevention: The prevention text to check
        rules_index: The loaded rules index
        incident_id: ID of the incident (for validation tracking)
        dry_run: If True, don't actually increment (purely observational)

    Returns:
        (rule_id or None, was_candidate_validated, validation_message)
    """
    prevention_lower = prevention.lower()

    # Check active rules first
    for rule in rules_index.get("active_rules", []):
        rule_name = rule.get("name", "").lower()
        triggers = rule.get("trigger_keywords", [])

        # Check if any trigger keyword appears in prevention
        for trigger in triggers:
            if trigger.lower() in prevention_lower:
                return rule.get("id"), False, "active rule"  # Active rule exists

    # Check candidates - and increment validation if match found
    candidates_dir = get_candidates_dir()
    if os.path.exists(candidates_dir):
        for filename in os.listdir(candidates_dir):
            if not filename.endswith(".json"):
                continue
            try:
                filepath = os.path.join(candidates_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    candidate = json.load(f)
                    if candidate.get("prevention", {}).get("before_action", "").lower() == prevention_lower:
                        candidate_id = candidate.get("id")
                        # Increment validation on recurrence (if new evidence)
                        if incident_id:
                            did_increment, new_count, msg = increment_candidate_validation(
                                filepath, incident_id, dry_run=dry_run
                            )
                            return candidate_id, did_increment, msg
                        return candidate_id, False, "no incident_id"
            except Exception:
                continue

    return None, False, ""


def save_candidate_rule(rule: Dict, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Save candidate rule to candidates/failures/ directory.
    Returns (success, filepath_or_error).
    """
    candidates_dir = get_candidates_dir()

    if dry_run:
        return True, f"[DRY RUN] Would save to {candidates_dir}/{rule['id']}.json"

    try:
        # Ensure directory exists
        os.makedirs(candidates_dir, exist_ok=True)

        filepath = os.path.join(candidates_dir, f"{rule['id']}.json")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(rule, f, indent=2)

        return True, filepath
    except Exception as e:
        return False, str(e)


def format_report(
    processed: List[Dict],
    created: List[Dict],
    skipped: List[Dict],
    validated: List[Dict],
    errors: List[Dict],
    dry_run: bool
) -> str:
    """Format the skill report."""
    lines = []
    lines.append("## Incident → Rule Report")
    lines.append("")

    mode = "[DRY RUN] " if dry_run else ""
    lines.append(f"**{mode}Processed:** {len(processed)} incidents")
    lines.append(f"**Created:** {len(created)} candidate rules")
    lines.append(f"**Validated:** {len(validated)} existing candidates")
    lines.append(f"**Skipped:** {len(skipped)} (already have rules or not actionable)")
    if errors:
        lines.append(f"**Errors:** {len(errors)}")
    lines.append("")

    # Show validated candidates first (evidence of recurrence)
    if validated:
        lines.append("### Validated Candidates (recurrence detected)")
        lines.append("")
        for item in validated[:5]:  # Top 5
            lines.append(f"- **{item['candidate_id']}**: {item['message']}")
            lines.append(f"  - Evidence: `{item['incident_id']}`")
        if len(validated) > 5:
            lines.append(f"- ... and {len(validated) - 5} more")
        lines.append("")

    if created:
        lines.append("### Created Candidate Rules")
        lines.append("")
        for item in created:
            rule = item["rule"]
            incident_id = item["incident_id"]
            lines.append(f"- **{rule['id']}**: {rule['name']}")
            lines.append(f"  - Source: `{incident_id}`")
            lines.append(f"  - Severity: {rule['severity']}")
            lines.append(f"  - Prevention: {rule['prevention']['before_action'][:100]}...")
            lines.append(f"  - Triggers: {', '.join(rule['trigger_keywords'][:5])}")
            lines.append("")

    if skipped:
        lines.append("### Skipped")
        lines.append("")
        for item in skipped:
            lines.append(f"- `{item['incident_id']}`: {item['reason']}")
        lines.append("")

    if errors:
        lines.append("### Errors")
        lines.append("")
        for item in errors:
            lines.append(f"- `{item['incident_id']}`: {item['error']}")
        lines.append("")

    # Next steps
    lines.append("### Next Steps")
    lines.append("")
    if created:
        lines.append(f"1. Review candidate rules in `candidates/failures/`")
        lines.append(f"2. Rules auto-promote to active after {DEFAULT_CONFIG['validations_to_promote']} validations")
        lines.append(f"3. Run `check_rules` when working to validate rules apply correctly")
    else:
        lines.append("No new candidate rules created. All incidents either:")
        lines.append("- Already have corresponding rules")
        lines.append("- Have non-actionable prevention (too vague)")

    return "\n".join(lines)


def load_full_incident(incident_id: str) -> Optional[Dict]:
    """Load full incident data from file system."""
    incidents_dir = os.path.join(get_agent_home(), "memory", "incidents")

    # Try direct path
    filepath = os.path.join(incidents_dir, f"{incident_id}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Search in directory
    if os.path.exists(incidents_dir):
        for filename in os.listdir(incidents_dir):
            if incident_id in filename and filename.endswith(".json"):
                try:
                    with open(os.path.join(incidents_dir, filename), "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    continue

    return None


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            min_severity: str (default "medium") - Minimum severity to process
            max_incidents: int (default 50) - Max incidents to process
            dry_run: bool (default False) - If True, don't create files
            incident_ids: List[str] (optional) - Specific incidents to process
        }
        tools: {
            query_memory: callable
            get_artifact: callable (optional, for full incident data)
        }
        context: {run_id, timeout}

    Returns:
        {
            success: bool,
            report: str,
            created_count: int,
            skipped_count: int,
            created_rules: List[dict],
            elapsed_seconds: float,
        }
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    # Parse args
    min_severity = args.get("min_severity", DEFAULT_CONFIG["min_severity"])
    max_incidents = args.get("max_incidents", DEFAULT_CONFIG["max_incidents"])
    dry_run = args.get("dry_run", DEFAULT_CONFIG["dry_run"])
    specific_ids = args.get("incident_ids", [])

    query_memory = tools.get("query_memory")
    get_artifact = tools.get("get_artifact")

    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    min_severity_rank = SEVERITY_RANK.get(min_severity, 1)

    # Load rules index for duplicate checking
    rules_index = {}
    index_path = get_index_path()
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                rules_index = json.load(f)
        except Exception:
            pass

    # ==============================
    # Phase 1: Query incidents
    # ==============================
    incident_ids_to_load = []

    if specific_ids:
        incident_ids_to_load = specific_ids
    else:
        # Query all incidents to get IDs
        try:
            result = query_memory(artifact_type="incident_rca", limit=max_incidents)
            items = []
            if isinstance(result, list):
                items = result
            elif isinstance(result, dict):
                items = result.get("results", result.get("artifacts", []))

            for item in items:
                inc_id = item.get("id", "")
                if inc_id:
                    incident_ids_to_load.append(inc_id)
        except Exception as e:
            return {"success": False, "error": f"Failed to query incidents: {e}"}

    # Load full incident data from files
    incidents = []
    for inc_id in incident_ids_to_load:
        full_incident = load_full_incident(inc_id)
        if full_incident:
            incidents.append(full_incident)

    if not incidents:
        return {
            "success": True,
            "report": "No incidents found to process.",
            "created_count": 0,
            "skipped_count": 0,
            "created_rules": [],
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    # ==============================
    # Phase 2: Filter and process
    # ==============================
    processed = []
    created = []
    skipped = []
    validated = []  # Candidates that got validation incremented
    errors = []

    for incident in incidents:
        if time.time() - start_time >= timeout * 0.9:
            break

        incident_id = incident.get("id", "unknown")
        data = incident.get("data", incident)

        severity = data.get("severity", "medium")
        severity_rank = SEVERITY_RANK.get(severity, 1)

        # Skip if below severity threshold
        if severity_rank < min_severity_rank:
            skipped.append({
                "incident_id": incident_id,
                "reason": f"Severity '{severity}' below threshold '{min_severity}'"
            })
            continue

        prevention = data.get("prevention", "")

        # Check if prevention is actionable
        is_actionable, reason = is_actionable_prevention(prevention)
        if not is_actionable:
            skipped.append({
                "incident_id": incident_id,
                "reason": f"Prevention not actionable: {reason}"
            })
            continue

        # Check if rule already exists (and increment candidate validations on recurrence)
        existing_rule, was_validated, val_msg = check_existing_rules(
            prevention, rules_index, incident_id, dry_run=dry_run
        )
        if existing_rule:
            validation_info = f" ({val_msg})" if val_msg else ""
            skipped.append({
                "incident_id": incident_id,
                "reason": f"Rule already exists: {existing_rule}{validation_info}"
            })
            # Track separately if validation was incremented
            if was_validated:
                validated.append({
                    "incident_id": incident_id,
                    "candidate_id": existing_rule,
                    "message": val_msg,
                })
            continue

        processed.append(incident)

        # Generate candidate rule
        try:
            candidate_rule = incident_to_candidate_rule(incident)

            # Save candidate
            success, result = save_candidate_rule(candidate_rule, dry_run=dry_run)

            if success:
                created.append({
                    "incident_id": incident_id,
                    "rule": candidate_rule,
                    "filepath": result,
                })
            else:
                errors.append({
                    "incident_id": incident_id,
                    "error": f"Failed to save: {result}"
                })
        except Exception as e:
            errors.append({
                "incident_id": incident_id,
                "error": str(e)
            })

    # ==============================
    # Phase 3: Generate report
    # ==============================
    report = format_report(processed, created, skipped, validated, errors, dry_run)

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "report": report,
        "created_count": len(created),
        "validated_count": len(validated),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "created_rules": [c["rule"] for c in created],
        "validated_candidates": [v["candidate_id"] for v in validated],
        "elapsed_seconds": elapsed,
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("incident_to_rule Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Algorithm:")
    print("  1. Query incidents with severity >= threshold")
    print("  2. Filter to actionable prevention fields")
    print("  3. Check for existing rules (avoid duplicates)")
    print("  4. Generate candidate rule from template")
    print("  5. Save to candidates/failures/")
    print()
    print("Severity levels: low < medium < high < critical")
    print()
    print("Default config:")
    for k, v in DEFAULT_CONFIG.items():
        print(f"  {k}: {v}")
    print()
    print("Banned prevention phrases (too vague):")
    for phrase in sorted(BANNED_PHRASES):
        print(f"  - '{phrase}'")
