#!/usr/bin/env python3
"""PreToolUse hook executor for hookify plugin.

This script is called by Claude Code before any tool executes.
It reads:
1. ~/.agent/rules/enforcement_patterns.json (hard rules with regex)
2. .claude/hookify.*.local.md files (hookify markdown rules)

Enforcement patterns are checked FIRST, then hookify rules.
"""

import os
import sys
import json
import re
import subprocess
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Debug mode - set HOOKIFY_DEBUG=1 to enable
DEBUG = os.environ.get('HOOKIFY_DEBUG', '').lower() in ('1', 'true', 'yes')

# Paths
HOME = Path.home()
AGENT_DIR = HOME / '.agent'
PATTERNS_FILE = AGENT_DIR / 'rules' / 'enforcement_patterns.json'
CACHE_DIR = AGENT_DIR / '.rule_cache'
READ_LEDGER = CACHE_DIR / 'read_ledger.json'
TELEMETRY_DIR = HOME / '.claude' / 'telemetry'

# Settings
LEDGER_TTL_MINUTES = 30  # "recent read" window

# Risky tools that should be blocked if bootstrap fails
RISKY_TOOLS = {'Bash', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}

# Bootstrap state
_bootstrap_ok = None
_bootstrap_error = None


def bootstrap_check() -> Tuple[bool, Optional[str]]:
    """Verify system integrity at startup. Fail closed if broken.

    Checks:
    1. Cache directory exists and is writable
    2. Enforcement patterns file is loadable (if exists)

    Returns (ok, error_message).
    """
    global _bootstrap_ok, _bootstrap_error

    # Return cached result if already checked
    if _bootstrap_ok is not None:
        return _bootstrap_ok, _bootstrap_error

    errors = []

    # 1. Ensure cache directory exists and is writable
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        test_file = CACHE_DIR / '.write_test'
        test_file.write_text('test', encoding='utf-8')
        test_file.unlink()
    except Exception as e:
        errors.append(f"Cache dir not writable: {e}")

    # 2. Ensure telemetry directory exists
    try:
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Telemetry dir not writable: {e}")

    # 3. Verify patterns file is valid JSON (if exists)
    if PATTERNS_FILE.exists():
        try:
            data = json.loads(PATTERNS_FILE.read_text(encoding='utf-8'))
            if 'enforcement_rules' not in data:
                errors.append("Patterns file missing 'enforcement_rules' key")
        except json.JSONDecodeError as e:
            errors.append(f"Patterns file invalid JSON: {e}")
        except Exception as e:
            errors.append(f"Patterns file unreadable: {e}")

    if errors:
        _bootstrap_ok = False
        _bootstrap_error = "; ".join(errors)
        debug_log(f"BOOTSTRAP FAILED: {_bootstrap_error}")
    else:
        _bootstrap_ok = True
        _bootstrap_error = None
        debug_log("Bootstrap OK")

    return _bootstrap_ok, _bootstrap_error


def make_bootstrap_failure_response(error: str) -> Dict:
    """Create a blocking response for bootstrap failure."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny"
        },
        "systemMessage": f"**[SYSTEM INTEGRITY]**\n\n[BLOCKED] Hook bootstrap failed. Risky operations disabled until fixed.\n\nError: {error}\n\nFix the issue and retry."
    }


def debug_log(msg: str) -> None:
    """Log debug message to stderr if DEBUG is enabled."""
    if DEBUG:
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[hookify {timestamp}] {msg}", file=sys.stderr)


def telemetry_log(tool_name: str, tool_input: Dict, decision: str, rule_matched: str = None) -> None:
    """Log tool execution to telemetry file (S8 invariant)."""
    try:
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        log_file = TELEMETRY_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"

        summary = ""
        if tool_name == 'Bash':
            summary = tool_input.get('command', '')[:200]
        elif tool_name in ['Edit', 'Write', 'MultiEdit']:
            summary = tool_input.get('file_path', '')
        elif tool_name == 'Read':
            summary = tool_input.get('file_path', '')
        else:
            summary = str(tool_input)[:200]

        entry = {
            "ts": datetime.now().isoformat(),
            "tool": tool_name,
            "summary": summary,
            "decision": decision,
            "rule": rule_matched
        }

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception:
        pass


# ============================================================================
# ENFORCEMENT PATTERNS (from ~/.agent/rules/enforcement_patterns.json)
# ============================================================================

def load_enforcement_patterns() -> List[Dict]:
    """Load enforcement patterns from JSON file."""
    if not PATTERNS_FILE.exists():
        debug_log(f"No enforcement patterns file at {PATTERNS_FILE}")
        return []

    try:
        data = json.loads(PATTERNS_FILE.read_text(encoding='utf-8'))
        rules = data.get('enforcement_rules', [])

        # Precompile regex patterns
        for rule in rules:
            compiled = []
            for p in rule.get('patterns', []):
                try:
                    pattern = p.get('regex', p) if isinstance(p, dict) else p
                    flags = re.IGNORECASE if (isinstance(p, dict) and p.get('flags', '').lower() == 'i') else 0
                    compiled.append({
                        'regex': re.compile(pattern, flags),
                        'description': p.get('description', pattern) if isinstance(p, dict) else pattern
                    })
                except re.error as e:
                    debug_log(f"Invalid regex '{pattern}': {e}")
            rule['_compiled'] = compiled

        debug_log(f"Loaded {len(rules)} enforcement rules")
        return rules
    except Exception as e:
        debug_log(f"Error loading enforcement patterns: {e}")
        return []


def check_enforcement_patterns(tool_name: str, tool_input: Dict) -> Optional[Dict]:
    """Check tool call against enforcement patterns.

    Returns blocking response dict if blocked, None if allowed.
    """
    rules = load_enforcement_patterns()

    for rule in rules:
        rule_tool = rule.get('tool', '')
        if rule_tool and rule_tool != tool_name:
            continue

        action = rule.get('action', 'block')

        # For Bash tool - check command against patterns
        if tool_name == 'Bash':
            command = tool_input.get('command', '')

            for p in rule.get('_compiled', []):
                if p['regex'].search(command):
                    msg = rule.get('message', 'Command blocked by enforcement rule.')
                    rule_name = rule.get('name', rule.get('id', 'enforcement'))

                    debug_log(f"BLOCKED by {rule_name}: matched '{p['description']}'")

                    if action == 'block':
                        return make_block_response(
                            rule_name,
                            msg,
                            f"Pattern: {p['description']}"
                        )
                    else:
                        return make_warn_response(rule_name, msg)

        # For Edit tool - check read-before-edit
        if tool_name == 'Edit' and rule.get('id') == 'read_before_edit':
            file_path = tool_input.get('file_path', '')
            if file_path:
                ok, reason = check_read_before_edit(file_path)
                if not ok:
                    return make_block_response(
                        'Read Before Edit',
                        rule.get('message', 'File must be read before editing.'),
                        reason
                    )

    return None


def make_block_response(rule_name: str, message: str, detail: str = None) -> Dict:
    """Create a blocking response."""
    full_msg = f"**[{rule_name}]**\n\n[BLOCKED] {message}"
    if detail:
        full_msg += f"\n\n{detail}"

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny"
        },
        "systemMessage": full_msg
    }


def make_warn_response(rule_name: str, message: str) -> Dict:
    """Create a warning response (allows operation)."""
    return {
        "systemMessage": f"**[{rule_name}]**\n\n[WARNING] {message}"
    }


# ============================================================================
# READ-BEFORE-EDIT LEDGER
# ============================================================================

def ensure_cache_dir() -> None:
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_read_ledger() -> Dict:
    """Load the read ledger."""
    if not READ_LEDGER.exists():
        return {}
    try:
        return json.loads(READ_LEDGER.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_read_ledger(ledger: Dict) -> None:
    """Save the read ledger."""
    ensure_cache_dir()
    READ_LEDGER.write_text(json.dumps(ledger, indent=2), encoding='utf-8')


def record_read(file_path: str, content_hash: str = None) -> None:
    """Record a file read in the ledger."""
    ledger = load_read_ledger()

    # Normalize path
    normalized = str(Path(file_path).resolve())

    ledger[normalized] = {
        "hash": content_hash or "unknown",
        "ts": datetime.utcnow().isoformat() + "Z"
    }

    # Prune old entries (older than 2x TTL)
    cutoff = datetime.utcnow() - timedelta(minutes=LEDGER_TTL_MINUTES * 2)
    ledger = {
        k: v for k, v in ledger.items()
        if datetime.fromisoformat(v['ts'].replace('Z', '')) > cutoff
    }

    save_read_ledger(ledger)
    debug_log(f"Recorded read: {normalized}")


def check_read_before_edit(file_path: str) -> Tuple[bool, str]:
    """Check if file was recently read.

    Returns (ok, reason).
    """
    ledger = load_read_ledger()
    normalized = str(Path(file_path).resolve())

    entry = ledger.get(normalized)
    if not entry:
        return False, f"No prior Read recorded for: {file_path}"

    try:
        ts = datetime.fromisoformat(entry['ts'].replace('Z', ''))
    except Exception:
        return False, "Read ledger timestamp invalid."

    if datetime.utcnow() - ts > timedelta(minutes=LEDGER_TTL_MINUTES):
        return False, f"Last Read is older than {LEDGER_TTL_MINUTES} minutes."

    return True, ""


# ============================================================================
# SECRETS-IN-GIT SCANNING
# ============================================================================

SECRET_PATTERNS = [
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
    (r'sk-[a-zA-Z0-9]{20,}', 'OpenAI API Key'),
    (r'ghp_[a-zA-Z0-9]{36}', 'GitHub PAT'),
    (r'-----BEGIN (RSA |DSA |EC )?PRIVATE KEY-----', 'Private Key'),
    (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*[\'"][^\'"]{10,}[\'"]', 'API Key Assignment'),
    (r'(?i)(password|passwd)\s*[:=]\s*[\'"][^\'"]+[\'"]', 'Password Assignment'),
    (r'(?i)(secret|token)\s*[:=]\s*[\'"][^\'"]{10,}[\'"]', 'Secret/Token Assignment'),
]

SENSITIVE_FILE_PATTERNS = [
    (r'\.env$', '.env file'),
    (r'credentials\.json$', 'Credentials file'),
    (r'.*\.pem$', 'PEM key file'),
    (r'id_rsa', 'SSH private key'),
    (r'\.p12$|\.pfx$', 'Certificate file'),
]


def check_secrets_in_staged_diff() -> Tuple[bool, str]:
    """Check staged git diff for secrets.

    Returns (has_secrets, pattern_matched).
    """
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached'],
            capture_output=True,
            text=True,
            timeout=5
        )
        diff = result.stdout

        for pattern, name in SECRET_PATTERNS:
            if re.search(pattern, diff):
                return True, name

        return False, ""
    except Exception as e:
        debug_log(f"Error checking staged diff: {e}")
        return False, ""


def check_sensitive_file(command: str) -> Tuple[bool, str]:
    """Check if git add/commit involves sensitive files.

    Returns (is_sensitive, file_pattern).
    """
    # Extract files from git add command
    if 'git add' in command or 'git commit' in command:
        for pattern, name in SENSITIVE_FILE_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True, name

    return False, ""


# ============================================================================
# HOOKIFY RULES (fallback to original system)
# ============================================================================

# Add plugin root to Python path for imports
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT')
if PLUGIN_ROOT and PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

try:
    from core.config_loader import load_rules
    from core.rule_engine import RuleEngine
    HOOKIFY_AVAILABLE = True
except ImportError as e:
    debug_log(f"Hookify import error: {e}")
    HOOKIFY_AVAILABLE = False


def check_hookify_rules(tool_name: str, tool_input: Dict, input_data: Dict) -> Optional[Dict]:
    """Check against hookify markdown rules.

    Returns response dict if rule matched, None otherwise.
    """
    if not HOOKIFY_AVAILABLE:
        return None

    # Determine event type
    event = None
    if tool_name == 'Bash':
        event = 'bash'
    elif tool_name in ['Edit', 'Write', 'MultiEdit']:
        event = 'file'

    # Load and evaluate rules
    rules = load_rules(event=event)
    debug_log(f"Loaded {len(rules)} hookify rules for event '{event}'")

    engine = RuleEngine()
    result = engine.evaluate_rules(rules, input_data)

    if result:
        return result

    return None


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point for PreToolUse hook."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})

        # --- BOOTSTRAP CHECK: Fail closed if system integrity broken ---
        bootstrap_ok, bootstrap_error = bootstrap_check()
        if not bootstrap_ok and tool_name in RISKY_TOOLS:
            telemetry_log(tool_name, tool_input, 'deny', 'BOOTSTRAP_FAILURE')
            print(json.dumps(make_bootstrap_failure_response(bootstrap_error)), file=sys.stdout)
            sys.exit(0)

        # FAST PATH: Skip rule evaluation for MCP tools
        if tool_name.startswith('mcp__'):
            debug_log(f"MCP tool fast-path: {tool_name}")
            telemetry_log(tool_name, tool_input, 'allow', None)
            print(json.dumps({}), file=sys.stdout)
            sys.exit(0)

        debug_log(f"Tool: {tool_name}")
        if tool_name == 'Bash':
            debug_log(f"Command: {tool_input.get('command', '')[:100]}")

        # --- Handle READ tool: record in ledger ---
        if tool_name == 'Read':
            file_path = tool_input.get('file_path', '')
            if file_path:
                # Compute simple hash of request (we don't have content yet)
                content_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
                record_read(file_path, content_hash)
            telemetry_log(tool_name, tool_input, 'allow', None)
            print(json.dumps({}), file=sys.stdout)
            sys.exit(0)

        # --- Check enforcement patterns (FIRST) ---
        result = check_enforcement_patterns(tool_name, tool_input)
        if result:
            decision = result.get('hookSpecificOutput', {}).get('permissionDecision', 'allow')
            rule_name = None
            if 'systemMessage' in result:
                msg = result['systemMessage']
                if '**[' in msg and ']**' in msg:
                    rule_name = msg.split('**[')[1].split(']**')[0]

            telemetry_log(tool_name, tool_input, decision, rule_name)
            print(json.dumps(result), file=sys.stdout)
            sys.exit(0)

        # --- Check secrets in git operations ---
        if tool_name == 'Bash':
            command = tool_input.get('command', '')

            # Check for sensitive files in git add
            is_sensitive, file_type = check_sensitive_file(command)
            if is_sensitive:
                result = make_block_response(
                    'Secrets in Git',
                    f'Attempting to add sensitive file type: {file_type}',
                    'Remove sensitive files from staging before committing.'
                )
                telemetry_log(tool_name, tool_input, 'deny', 'Secrets in Git')
                print(json.dumps(result), file=sys.stdout)
                sys.exit(0)

            # Check staged diff for secrets on git commit
            if re.search(r'\bgit\s+commit\b', command, re.IGNORECASE):
                has_secrets, pattern = check_secrets_in_staged_diff()
                if has_secrets:
                    result = make_block_response(
                        'Secrets in Git',
                        f'Staged diff contains potential secret: {pattern}',
                        'Remove secrets from staged changes before committing.'
                    )
                    telemetry_log(tool_name, tool_input, 'deny', 'Secrets in Git')
                    print(json.dumps(result), file=sys.stdout)
                    sys.exit(0)

        # --- Check hookify rules (fallback) ---
        result = check_hookify_rules(tool_name, tool_input, input_data)
        if result:
            decision = result.get('hookSpecificOutput', {}).get('permissionDecision', 'allow')
            rule_name = None
            if 'systemMessage' in result:
                msg = result['systemMessage']
                if '**[' in msg and ']**' in msg:
                    rule_name = msg.split('**[')[1].split(']**')[0]

            telemetry_log(tool_name, tool_input, decision, rule_name)
            print(json.dumps(result), file=sys.stdout)
            sys.exit(0)

        # --- Default: allow ---
        telemetry_log(tool_name, tool_input, 'allow', None)
        print(json.dumps({}), file=sys.stdout)

    except Exception as e:
        debug_log(f"ERROR: {type(e).__name__}: {e}")
        error_output = {
            "systemMessage": f"Hookify error: {str(e)}"
        }
        print(json.dumps(error_output), file=sys.stdout)

    finally:
        # ALWAYS exit 0 - never block operations due to hook errors
        sys.exit(0)


if __name__ == '__main__':
    main()
