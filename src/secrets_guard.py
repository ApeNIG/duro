"""
Secrets Guard - Layer 3 Security
================================
Prevents secrets from leaking into prompts, logs, and memory artifacts.

Key Principles:
- Secrets NEVER appear in prompts, audit logs, or memory
- Structured metadata + hashes for auditability
- Multiple detection patterns (API keys, tokens, passwords, PII)
- Fail-safe: uncertain patterns marked for review

Integration:
- Called by policy_gate.py before tool execution
- Redacts arguments for audit trail
- Blocks tools that would expose secrets
"""

import re
import hashlib
import os
from typing import Dict, Any, Tuple, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import json


# ============================================================
# SECRET PATTERNS
# ============================================================

@dataclass
class SecretPattern:
    """Definition of a secret pattern to detect."""
    name: str
    pattern: re.Pattern
    severity: str  # 'critical', 'high', 'medium'
    description: str


# Compiled patterns for performance
SECRET_PATTERNS: List[SecretPattern] = [
    # API Keys (generic)
    SecretPattern(
        name="generic_api_key",
        pattern=re.compile(r'(?i)(api[_-]?key|apikey)["\s:=]+["\']?([a-zA-Z0-9_\-]{20,})["\']?'),
        severity="critical",
        description="Generic API key pattern"
    ),

    # AWS
    SecretPattern(
        name="aws_access_key",
        pattern=re.compile(r'(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])'),
        severity="critical",
        description="AWS Access Key ID"
    ),
    SecretPattern(
        name="aws_secret_key",
        pattern=re.compile(r'(?i)(aws[_-]?secret|secret[_-]?access[_-]?key)["\s:=]+["\']?([a-zA-Z0-9/+=]{40})["\']?'),
        severity="critical",
        description="AWS Secret Access Key"
    ),

    # OpenAI / Anthropic
    SecretPattern(
        name="openai_api_key",
        pattern=re.compile(r'sk-[a-zA-Z0-9]{20,}'),
        severity="critical",
        description="OpenAI API Key"
    ),
    SecretPattern(
        name="anthropic_api_key",
        pattern=re.compile(r'sk-ant-[a-zA-Z0-9\-]{20,}'),
        severity="critical",
        description="Anthropic API Key"
    ),

    # GitHub
    SecretPattern(
        name="github_pat",
        pattern=re.compile(r'ghp_[a-zA-Z0-9]{36}'),
        severity="critical",
        description="GitHub Personal Access Token"
    ),
    SecretPattern(
        name="github_oauth",
        pattern=re.compile(r'gho_[a-zA-Z0-9]{36}'),
        severity="critical",
        description="GitHub OAuth Token"
    ),

    # Stripe
    SecretPattern(
        name="stripe_secret_key",
        pattern=re.compile(r'sk_(live|test)_[a-zA-Z0-9]{24,}'),
        severity="critical",
        description="Stripe Secret Key"
    ),
    SecretPattern(
        name="stripe_publishable_key",
        pattern=re.compile(r'pk_(live|test)_[a-zA-Z0-9]{24,}'),
        severity="high",
        description="Stripe Publishable Key"
    ),

    # Database URLs
    SecretPattern(
        name="database_url",
        pattern=re.compile(r'(?i)(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@[^\s"\']+'),
        severity="critical",
        description="Database connection string with credentials"
    ),

    # JWT
    SecretPattern(
        name="jwt_token",
        pattern=re.compile(r'eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}'),
        severity="high",
        description="JWT Token"
    ),

    # Private Keys
    SecretPattern(
        name="private_key",
        pattern=re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'),
        severity="critical",
        description="Private Key Header"
    ),

    # Passwords in common formats
    SecretPattern(
        name="password_assignment",
        pattern=re.compile(r'(?i)(password|passwd|pwd|secret)["\s:=]+["\']?([^\s"\']{8,})["\']?'),
        severity="high",
        description="Password assignment"
    ),

    # Bearer tokens
    SecretPattern(
        name="bearer_token",
        pattern=re.compile(r'(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}'),
        severity="high",
        description="Bearer token"
    ),

    # Basic auth
    SecretPattern(
        name="basic_auth",
        pattern=re.compile(r'(?i)basic\s+[a-zA-Z0-9+/=]{20,}'),
        severity="high",
        description="Basic auth header"
    ),

    # Slack tokens
    SecretPattern(
        name="slack_token",
        pattern=re.compile(r'xox[baprs]-[a-zA-Z0-9\-]{10,}'),
        severity="critical",
        description="Slack token"
    ),

    # Discord tokens
    SecretPattern(
        name="discord_token",
        pattern=re.compile(r'[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27}'),
        severity="critical",
        description="Discord token"
    ),

    # SSH keys (partial - just the key material start)
    SecretPattern(
        name="ssh_key",
        pattern=re.compile(r'ssh-(?:rsa|ed25519|dss)\s+[A-Za-z0-9+/=]{50,}'),
        severity="high",
        description="SSH public key (may indicate private key nearby)"
    ),

    # Google Cloud
    SecretPattern(
        name="gcp_api_key",
        pattern=re.compile(r'AIza[0-9A-Za-z\-_]{35}'),
        severity="critical",
        description="Google Cloud API Key"
    ),

    # Azure
    SecretPattern(
        name="azure_connection_string",
        pattern=re.compile(r'(?i)DefaultEndpointsProtocol=https?;AccountName=[^;]+;AccountKey=[^;]+'),
        severity="critical",
        description="Azure Storage connection string"
    ),

    # Generic secrets in env format
    SecretPattern(
        name="env_secret",
        pattern=re.compile(r'(?i)^([A-Z_]+(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIALS|AUTH))[=:]\s*(.{8,})$', re.MULTILINE),
        severity="medium",
        description="Environment variable with secret-like name"
    ),
]

# PII Patterns (medium severity - warn but don't block by default)
PII_PATTERNS: List[SecretPattern] = [
    SecretPattern(
        name="email",
        pattern=re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
        severity="medium",
        description="Email address"
    ),
    SecretPattern(
        name="phone_us",
        pattern=re.compile(r'(?<!\d)(?:\+1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}(?!\d)'),
        severity="medium",
        description="US phone number"
    ),
    SecretPattern(
        name="ssn",
        pattern=re.compile(r'(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)'),
        severity="high",
        description="US Social Security Number"
    ),
    SecretPattern(
        name="credit_card",
        pattern=re.compile(r'(?<!\d)(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9][0-9])[0-9]{12})(?!\d)'),
        severity="critical",
        description="Credit card number"
    ),
]


# ============================================================
# DETECTION RESULT
# ============================================================

@dataclass
class SecretMatch:
    """A detected secret in content."""
    pattern_name: str
    severity: str
    location: str  # field name or context
    redacted_preview: str  # First 4 chars + *** + last 2 chars
    hash: str  # SHA256 hash of the secret for correlation


@dataclass
class SecretScanResult:
    """Result of scanning for secrets."""
    has_secrets: bool
    matches: List[SecretMatch] = field(default_factory=list)
    blocked: bool = False  # True if critical secret found
    redacted_content: Optional[str] = None  # Content with secrets redacted


# ============================================================
# CORE FUNCTIONS
# ============================================================

def compute_secret_hash(secret: str) -> str:
    """Hash a secret for correlation without exposing it."""
    return hashlib.sha256(secret.encode()).hexdigest()[:16]


def redact_secret(secret: str, prefix_len: int = 4, suffix_len: int = 2) -> str:
    """Redact a secret, preserving enough for identification."""
    if len(secret) <= prefix_len + suffix_len + 3:
        return "***REDACTED***"
    return f"{secret[:prefix_len]}***{secret[-suffix_len:]}"


def scan_string(content: str, include_pii: bool = False) -> SecretScanResult:
    """
    Scan a string for secrets.

    Args:
        content: String to scan
        include_pii: Whether to include PII patterns

    Returns:
        SecretScanResult with matches and blocking recommendation
    """
    matches = []
    patterns = SECRET_PATTERNS + (PII_PATTERNS if include_pii else [])
    has_critical = False

    for sp in patterns:
        for match in sp.pattern.finditer(content):
            # Get the actual secret value (might be in a group)
            if match.groups():
                # Use last non-None group (usually the actual secret)
                secret_value = next((g for g in reversed(match.groups()) if g), match.group(0))
            else:
                secret_value = match.group(0)

            matches.append(SecretMatch(
                pattern_name=sp.name,
                severity=sp.severity,
                location=f"char {match.start()}-{match.end()}",
                redacted_preview=redact_secret(secret_value),
                hash=compute_secret_hash(secret_value)
            ))

            if sp.severity == "critical":
                has_critical = True

    return SecretScanResult(
        has_secrets=len(matches) > 0,
        matches=matches,
        blocked=has_critical
    )


def scan_arguments(arguments: Dict[str, Any], include_pii: bool = False) -> SecretScanResult:
    """
    Scan tool arguments for secrets.

    Args:
        arguments: Dictionary of tool arguments
        include_pii: Whether to include PII patterns

    Returns:
        SecretScanResult with all matches
    """
    all_matches = []
    has_critical = False

    def scan_value(value: Any, path: str = "") -> None:
        nonlocal has_critical

        if isinstance(value, str):
            result = scan_string(value, include_pii)
            for match in result.matches:
                match.location = f"{path}: {match.location}" if path else match.location
                all_matches.append(match)
            if result.blocked:
                has_critical = True

        elif isinstance(value, dict):
            for k, v in value.items():
                scan_value(v, f"{path}.{k}" if path else k)

        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                scan_value(v, f"{path}[{i}]")

    scan_value(arguments)

    return SecretScanResult(
        has_secrets=len(all_matches) > 0,
        matches=all_matches,
        blocked=has_critical
    )


def redact_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redact secrets from arguments for safe logging.

    Returns a deep copy with secrets replaced by [REDACTED:hash].
    """
    def redact_value(value: Any) -> Any:
        if isinstance(value, str):
            result = scan_string(value)
            if result.matches:
                # Replace each match with redacted version
                redacted = value
                for match in sorted(result.matches, key=lambda m: int(m.location.split()[1].split('-')[0]), reverse=True):
                    # Extract original position
                    start, end = map(int, match.location.replace('char ', '').split('-'))
                    redacted = redacted[:start] + f"[REDACTED:{match.hash}]" + redacted[end:]
                return redacted
            return value

        elif isinstance(value, dict):
            return {k: redact_value(v) for k, v in value.items()}

        elif isinstance(value, list):
            return [redact_value(v) for v in value]

        elif isinstance(value, tuple):
            return tuple(redact_value(v) for v in value)

        return value

    return redact_value(arguments)


# ============================================================
# TOOL INTEGRATION
# ============================================================

# Tools that should NEVER receive secrets
SENSITIVE_TOOLS: Set[str] = {
    # Memory/logging tools - secrets should never persist
    "duro_save_memory",
    "duro_save_learning",
    "duro_log_task",
    "duro_log_failure",
    "duro_store_fact",
    "duro_store_decision",
    "duro_store_incident",
    "duro_store_change",
    "duro_extract_learnings",

    # Web/external tools - secrets could leak
    "web_search",
    "web_fetch",
    "mcp__superagi__web_search",
    "mcp__superagi__read_webpage",
}

# Tools that may legitimately use secrets (but should still redact in logs)
SECRET_HANDLING_TOOLS: Set[str] = {
    "Bash",  # May set env vars
    "Write",  # May write config files
    "Edit",   # May edit config files
    "mcp__superagi__shell_execute",
    "mcp__render__update_environment_variables",
    "mcp__render__create_web_service",  # envVars parameter
}

# Fields that commonly contain secrets (for targeted scanning)
SENSITIVE_FIELDS: Set[str] = {
    "password", "passwd", "pwd", "secret", "token", "key", "api_key",
    "apikey", "auth", "credential", "credentials", "private_key",
    "access_key", "secret_key", "connection_string", "bearer",
}


def check_secrets_policy(tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, str, Optional[SecretScanResult]]:
    """
    Check if a tool call violates secrets policy.

    Returns:
        Tuple of (allowed, reason, scan_result)
        - allowed: True if the call should proceed
        - reason: Human-readable explanation
        - scan_result: The scan result for logging
    """
    # Scan arguments for secrets
    scan_result = scan_arguments(arguments, include_pii=True)

    if not scan_result.has_secrets:
        return True, "No secrets detected", scan_result

    # Build summary of what was found
    severity_counts = {}
    for match in scan_result.matches:
        severity_counts[match.severity] = severity_counts.get(match.severity, 0) + 1

    summary = ", ".join(f"{count} {sev}" for sev, count in severity_counts.items())

    # Check if tool is in sensitive list (secrets should never go here)
    if tool_name in SENSITIVE_TOOLS:
        return False, f"Secrets detected in arguments to {tool_name} (memory/logging tool). Found: {summary}", scan_result

    # Check if critical secrets in non-secret-handling tools
    if scan_result.blocked and tool_name not in SECRET_HANDLING_TOOLS:
        return False, f"Critical secrets detected in arguments to {tool_name}. Found: {summary}", scan_result

    # Allow but warn for secret-handling tools
    if tool_name in SECRET_HANDLING_TOOLS:
        return True, f"Secrets detected but {tool_name} may legitimately handle them. Found: {summary}", scan_result

    # Medium/high severity in other tools - warn but allow
    return True, f"Potential secrets detected. Found: {summary}", scan_result


# ============================================================
# AUDIT LOGGING
# ============================================================

def create_secret_audit_entry(
    tool_name: str,
    scan_result: SecretScanResult,
    action: str,  # "blocked", "allowed", "redacted"
    reason: str
) -> Dict[str, Any]:
    """
    Create an audit log entry for secret detection.

    This entry is safe to log - no actual secrets, just metadata.
    """
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": "secret_scan",
        "tool": tool_name,
        "action": action,
        "reason": reason,
        "match_count": len(scan_result.matches),
        "severities": list(set(m.severity for m in scan_result.matches)),
        "pattern_names": list(set(m.pattern_name for m in scan_result.matches)),
        "hashes": [m.hash for m in scan_result.matches],  # For correlation
    }


# ============================================================
# ENVIRONMENT VARIABLE HANDLING
# ============================================================

# Env vars that are OK to reference (not secrets themselves)
SAFE_ENV_VARS: Set[str] = {
    "PATH", "HOME", "USER", "SHELL", "TERM", "LANG", "TZ",
    "PWD", "OLDPWD", "HOSTNAME", "DISPLAY",
    "DURO_WORKSPACE", "DURO_POLICY_BREAKGLASS",
    "PYTHONPATH", "NODE_PATH", "GOPATH",
}


def detect_env_var_exposure(command: str) -> List[str]:
    """
    Detect if a bash command would expose secret env vars.

    Returns list of potentially exposed secret env vars.
    """
    exposed = []

    # Pattern: echo $VAR, printenv VAR, env | grep VAR
    echo_pattern = re.compile(r'(?:echo|printf)\s+.*\$([A-Z_][A-Z0-9_]*)')
    for match in echo_pattern.finditer(command):
        var = match.group(1)
        if var not in SAFE_ENV_VARS:
            # Check if it looks like a secret name
            if any(secret_word in var.upper() for secret_word in ['KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'AUTH', 'CREDENTIAL']):
                exposed.append(var)

    # Pattern: printenv without filter (dumps all)
    if re.search(r'\bprintenv\s*$', command) or re.search(r'\bprintenv\s*\|', command):
        exposed.append("ALL_ENV_VARS")

    # Pattern: env without filter
    if re.search(r'\benv\s*$', command) or re.search(r'\benv\s*\|(?!\s*grep\s+-v)', command):
        exposed.append("ALL_ENV_VARS")

    return exposed


def check_bash_secrets(command: str) -> Tuple[bool, str]:
    """
    Check if a bash command would expose secrets.

    Returns:
        Tuple of (allowed, reason)
    """
    # Check for env var exposure
    exposed = detect_env_var_exposure(command)
    if exposed:
        if "ALL_ENV_VARS" in exposed:
            return False, "Command would dump all environment variables, potentially exposing secrets"
        return False, f"Command would expose potentially secret env vars: {', '.join(exposed)}"

    # Check for secrets in the command itself
    scan_result = scan_string(command)
    if scan_result.blocked:
        return False, "Command contains embedded secrets"

    return True, "No secret exposure detected"


# ============================================================
# OUTPUT SCANNING AND REDACTION (Post-Execution)
# ============================================================

@dataclass
class OutputScanResult:
    """Result of scanning tool output for secrets."""
    had_secrets: bool
    redacted_output: str
    matches: List[SecretMatch] = field(default_factory=list)
    redaction_count: int = 0


def scan_and_redact_output(output: str, tool_name: str = "") -> OutputScanResult:
    """
    Scan tool output for secrets and redact them.

    This is the POST-EXECUTION counterpart to check_secrets_policy.
    Tool outputs can leak secrets even if arguments were clean:
    - Bash prints env vars
    - CLI outputs signed URLs
    - Read tool returns file contents with secrets

    Returns:
        OutputScanResult with redacted output and metadata
    """
    if not output or not isinstance(output, str):
        return OutputScanResult(had_secrets=False, redacted_output=output or "")

    # Scan for secrets
    scan_result = scan_string(output, include_pii=False)

    if not scan_result.has_secrets:
        return OutputScanResult(had_secrets=False, redacted_output=output)

    # Redact each match (process in reverse order to preserve positions)
    redacted = output
    sorted_matches = sorted(
        scan_result.matches,
        key=lambda m: int(m.location.split()[1].split('-')[0]) if 'char' in m.location else 0,
        reverse=True
    )

    redaction_count = 0
    for match in sorted_matches:
        try:
            # Extract position from location string "char X-Y"
            if 'char' in match.location:
                pos_str = match.location.replace('char ', '')
                start, end = map(int, pos_str.split('-'))
                # Redact with hash for correlation
                redacted = redacted[:start] + f"[REDACTED:{match.hash}]" + redacted[end:]
                redaction_count += 1
        except (ValueError, IndexError):
            # If we can't parse position, skip (shouldn't happen)
            continue

    return OutputScanResult(
        had_secrets=True,
        redacted_output=redacted,
        matches=scan_result.matches,
        redaction_count=redaction_count
    )


def create_output_audit_entry(
    tool_name: str,
    scan_result: OutputScanResult,
    output_hash: str,
) -> Dict[str, Any]:
    """
    Create an audit log entry for output redaction.

    Only metadata is logged - never the actual secrets or full output.
    """
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": "output_redaction",
        "tool": tool_name,
        "had_secrets": scan_result.had_secrets,
        "redaction_count": scan_result.redaction_count,
        "output_hash": output_hash,  # Hash of ORIGINAL output for correlation
        "severities": list(set(m.severity for m in scan_result.matches)),
        "pattern_names": list(set(m.pattern_name for m in scan_result.matches)),
        "secret_hashes": [m.hash for m in scan_result.matches],
    }


def compute_output_hash(output: str) -> str:
    """Compute hash of output for audit correlation."""
    return hashlib.sha256(output.encode()).hexdigest()[:16]


# Tools whose output should ALWAYS be scanned (high leak risk)
HIGH_RISK_OUTPUT_TOOLS: Set[str] = {
    "Bash",
    "Read",
    "Grep",
    "mcp__superagi__shell_execute",
    "mcp__superagi__workspace_read",
    "mcp__render__query_render_postgres",
    "mcp__render__list_logs",
}

# Tools whose output should NEVER contain secrets (if they do, something is wrong)
CLEAN_OUTPUT_EXPECTED: Set[str] = {
    "duro_status",
    "duro_health_check",
    "duro_list_rules",
    "duro_list_skills",
    "Glob",  # Just file paths
}


def should_scan_output(tool_name: str) -> bool:
    """
    Determine if a tool's output should be scanned for secrets.

    Conservative: scan everything except known-clean tools.
    """
    if tool_name in CLEAN_OUTPUT_EXPECTED:
        return False
    # Default: scan everything else
    return True
