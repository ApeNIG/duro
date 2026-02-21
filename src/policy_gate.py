"""
Policy Gate - Execution Path Enforcement
=========================================

The constitutional checkpoint for all tool calls.
If a tool can execute without passing through this gate, you don't have security.

Design principles:
- FAIL-CLOSED: If gate can't run, tools don't run
- LOG EVERYTHING: Every decision, even bypasses
- APPROVE THE ACTION: Not "the tool", but the exact call with args_hash
- REDACT SECRETS: Audit trail should be safe to share
- WORKSPACE SCOPED: File operations constrained to allowed directories
- BROWSER SANDBOXED: Web automation uses ephemeral profiles with domain restrictions

Security layers enforced:
- Layer 1: Autonomy ladder (permission levels)
- Layer 2: Workspace guard (path scoping, deny list)
- Layer 3: Secrets guard (no secrets in args/outputs)
- Layer 4: Browser guard (sandbox, domain allowlist/blocklist)
"""

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Import time utilities
from time_utils import utc_now, utc_now_iso

# Workspace guard (Layer 2 - path scoping)
WORKSPACE_GUARD_AVAILABLE = False
WORKSPACE_GUARD_ERROR = None
try:
    from workspace_guard import (
        check_workspace_constraints, get_workspace_config, get_workspace_status
    )
    WORKSPACE_GUARD_AVAILABLE = True
except ImportError as e:
    WORKSPACE_GUARD_ERROR = str(e)

# Secrets guard (Layer 3 - secrets out of prompts/logs)
SECRETS_GUARD_AVAILABLE = False
SECRETS_GUARD_ERROR = None
try:
    from secrets_guard import (
        check_secrets_policy, scan_arguments, redact_arguments as redact_arguments_secrets,
        create_secret_audit_entry, check_bash_secrets
    )
    SECRETS_GUARD_AVAILABLE = True
except ImportError as e:
    SECRETS_GUARD_ERROR = str(e)

# Browser guard (Layer 4 - browser sandbox)
BROWSER_GUARD_AVAILABLE = False
BROWSER_GUARD_ERROR = None
try:
    from browser_guard import (
        check_browser_policy, get_browser_status, get_sandbox_config,
        check_domain_allowed, normalize_domain
    )
    BROWSER_GUARD_AVAILABLE = True
except ImportError as e:
    BROWSER_GUARD_ERROR = str(e)

# Unified Audit Log (Layer 5 - tamper-evident logging)
UNIFIED_AUDIT_AVAILABLE = False
UNIFIED_AUDIT_ERROR = None
try:
    from audit_log import (
        append_event, build_gate_event, build_secrets_event, build_browser_event,
        build_workspace_event, build_intent_event, build_injection_event,
        EventType, Severity
    )
    UNIFIED_AUDIT_AVAILABLE = True
except ImportError as e:
    UNIFIED_AUDIT_ERROR = str(e)
    print(f"[WARN] Unified audit not available: {e}", file=sys.stderr)

# Intent Guard (Layer 6 - capability tokens)
INTENT_GUARD_AVAILABLE = False
INTENT_GUARD_ERROR = None
try:
    from intent_guard import (
        require_intent, get_current_intent, get_intent_status,
        INTENT_REQUIRED_TOOLS, on_user_message
    )
    INTENT_GUARD_AVAILABLE = True
except ImportError as e:
    INTENT_GUARD_ERROR = str(e)
    print(f"[WARN] Intent guard not available: {e}", file=sys.stderr)

# Prompt Firewall (Layer 6 - injection detection)
PROMPT_FIREWALL_AVAILABLE = False
PROMPT_FIREWALL_ERROR = None
try:
    from prompt_firewall import (
        detect_injection, get_firewall_status
    )
    PROMPT_FIREWALL_AVAILABLE = True
except ImportError as e:
    PROMPT_FIREWALL_ERROR = str(e)
    print(f"[WARN] Prompt firewall not available: {e}", file=sys.stderr)


# === CONFIGURATION ===

# Fail-closed by default. Set DURO_POLICY_BREAKGLASS=1 to override (logs loudly)
FAIL_CLOSED = True
BREAKGLASS_ENV = "DURO_POLICY_BREAKGLASS"

# Audit log location
AUDIT_DIR = Path.home() / ".agent" / "memory" / "audit"
GATE_AUDIT_FILE = AUDIT_DIR / "gate_decisions.jsonl"
DEBUG_ARGS_FILE = AUDIT_DIR / "gate_debug_args.jsonl"  # Restricted, redacted args
SECRETS_AUDIT_FILE = AUDIT_DIR / "secrets_detection.jsonl"  # Secret scan events

# Ensure audit directory exists
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


# === BYPASS SET ===
# Tools that skip the gate (introspection/meta only)
# Be VERY careful adding to this list

GATE_BYPASS_TOOLS: Set[str] = {
    # Autonomy introspection (checking permission shouldn't require permission)
    "duro_can_execute",
    "duro_check_permission",
    "duro_autonomy_status",
    "duro_get_reputation",
    "duro_classify_action",

    # Status/health (read-only, no secrets)
    "duro_status",
    "duro_health_check",
    "duro_list_rules",
    "duro_list_skills",
    "duro_list_projects",
    "duro_list_constitutions",
    "duro_list_archives",
    "duro_list_artifacts",
    "duro_list_episodes",
    "duro_list_repairs",
    "duro_list_runs",

    # Context loading - READ-SENSITIVE but allowed (no secrets exposed)
    # NOTE: If duro_load_context ever returns secrets, move to gated
    "duro_load_context",
}

# Read-only tools that should be gated but at low risk level
READ_SENSITIVE_TOOLS: Set[str] = {
    "duro_query_memory",
    "duro_semantic_search",
    "duro_get_artifact",
    "duro_proactive_recall",
    "duro_query_archive",
    "duro_get_episode",
    "duro_get_run",
    "duro_get_related",
    "duro_get_validation_history",
}

# Browser-related tools that need sandbox enforcement (Layer 4)
BROWSER_TOOLS: Set[str] = {
    # Built-in web tools
    "WebFetch",
    "WebSearch",
    # Superagi MCP tools
    "mcp__superagi__web_search",
    "mcp__superagi__read_webpage",
    # Playwright/browser automation (if added)
    "mcp__playwright__navigate",
    "mcp__playwright__screenshot",
    "mcp__playwright__click",
    "mcp__playwright__fill",
}


# === REDACTION ===

# Keys that should ALWAYS be redacted
SENSITIVE_KEYS = {
    "password", "token", "secret", "api_key", "apikey", "api-key",
    "authorization", "auth", "cookie", "session", "bearer",
    "private_key", "privatekey", "private-key", "credentials",
    "access_token", "refresh_token", "id_token", "jwt",
    "client_secret", "webhook_secret", "signing_key",
}

# Patterns for high-entropy strings (likely tokens)
HIGH_ENTROPY_PATTERN = re.compile(r'^[A-Za-z0-9+/=_-]{32,}$')

# Workspace root for relative path logging
WORKSPACE_ROOT = Path.home()


def _is_sensitive_key(key: str) -> bool:
    """Check if a key name indicates sensitive data."""
    key_lower = key.lower().replace("-", "_")
    return any(s in key_lower for s in SENSITIVE_KEYS)


def _is_high_entropy(value: str) -> bool:
    """Check if a string looks like a token (high entropy, long)."""
    if not isinstance(value, str):
        return False
    if len(value) < 32:
        return False
    return bool(HIGH_ENTROPY_PATTERN.match(value))


def _redact_path(path: str) -> str:
    """Convert absolute path to workspace-relative for logging."""
    try:
        p = Path(path)
        if p.is_absolute():
            try:
                return str(p.relative_to(WORKSPACE_ROOT))
            except ValueError:
                # Not under workspace, return last 3 components
                parts = p.parts[-3:] if len(p.parts) > 3 else p.parts
                return ".../" + "/".join(parts)
        return path
    except Exception:
        return "[path-redacted]"


def redact_value(key: str, value: Any, depth: int = 0) -> Any:
    """
    Recursively redact sensitive values.

    Rules:
    - Sensitive keys -> "[REDACTED]"
    - High-entropy strings -> "[REDACTED:token-like]"
    - Paths -> workspace-relative
    - Nested dicts/lists -> recurse
    """
    if depth > 10:
        return "[max-depth]"

    # Check key sensitivity
    if _is_sensitive_key(key):
        return "[REDACTED]"

    # Handle different types
    if isinstance(value, dict):
        return {k: redact_value(k, v, depth + 1) for k, v in value.items()}

    if isinstance(value, list):
        return [redact_value(key, item, depth + 1) for item in value]

    if isinstance(value, str):
        # High-entropy string detection
        if _is_high_entropy(value):
            return "[REDACTED:token-like]"

        # Path-like strings
        if key.lower() in ("path", "file_path", "file", "directory", "dir", "folder"):
            return _redact_path(value)
        if "/" in value or "\\" in value:
            # Might be a path - check if it looks like one
            if len(value) > 10 and (value.startswith("/") or value.startswith("C:") or value.startswith("~")):
                return _redact_path(value)

    return value


def redact_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Redact all sensitive data from arguments dict."""
    return {k: redact_value(k, v) for k, v in arguments.items()}


# Internal keys excluded from args hashing
# These are metadata injected by the system, not user-visible arguments
INTERNAL_ARG_KEYS = {
    "_intent_id",
    "_origin",
    "_source_id",
    "__duro_internal",
}


def compute_args_hash(arguments: Dict[str, Any]) -> str:
    """
    Compute stable hash of arguments for approval matching.

    Uses canonical JSON (sorted keys) for determinism.
    Excludes internal keys (like _intent_id) that would break
    approval scope matching and audit consistency.
    """
    # Defensive: ensure arguments is a dict
    if not isinstance(arguments, dict):
        return hashlib.sha256(str(arguments).encode()).hexdigest()[:16]

    # Filter out internal keys
    filtered = {k: v for k, v in arguments.items() if k not in INTERNAL_ARG_KEYS}
    canonical = json.dumps(filtered, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def create_safe_summary(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Create a tiny human-readable summary of the action.

    Examples:
    - duro_delete_artifact: "artifact=fact_123abc"
    - duro_store_fact: "claim='User prefers...'"
    - duro_query_memory: "search='security', limit=10"
    """
    # Defensive: ensure arguments is a dict
    if not isinstance(arguments, dict):
        return f"(invalid args type: {type(arguments).__name__})"

    summaries = []

    # Tool-specific summaries
    if "artifact_id" in arguments:
        summaries.append(f"artifact={arguments['artifact_id'][:20]}")
    if "path" in arguments or "file_path" in arguments:
        path = arguments.get("path") or arguments.get("file_path")
        summaries.append(f"path={_redact_path(path)}")
    if "claim" in arguments:
        claim = arguments["claim"][:40] + "..." if len(arguments.get("claim", "")) > 40 else arguments.get("claim", "")
        summaries.append(f"claim='{claim}'")
    if "decision" in arguments:
        dec = arguments["decision"][:40] + "..." if len(arguments.get("decision", "")) > 40 else arguments.get("decision", "")
        summaries.append(f"decision='{dec}'")
    if "search_text" in arguments or "query" in arguments:
        q = arguments.get("search_text") or arguments.get("query")
        summaries.append(f"search='{q[:30]}'")
    if "limit" in arguments:
        summaries.append(f"limit={arguments['limit']}")
    if "skill_name" in arguments:
        summaries.append(f"skill={arguments['skill_name']}")

    if not summaries:
        # Fallback: list first 2 keys
        keys = list(arguments.keys())[:2]
        summaries = [f"{k}=..." for k in keys]

    return ", ".join(summaries) if summaries else "(no args)"


# === GATE DECISION ===

@dataclass
class GateDecision:
    """Result of policy gate evaluation."""
    allowed: bool
    action_needed: str  # "none", "approve", "downgrade"
    reason: str
    tool_name: str
    risk_level: str  # "read", "plan", "safe", "risk", "critical"
    domain: str
    args_hash: str
    safe_summary: str
    logged_at: str = field(default_factory=utc_now_iso)
    bypass: bool = False
    breakglass: bool = False
    error: Optional[str] = None

    def to_audit_record(self) -> Dict[str, Any]:
        """Convert to audit log format."""
        return {
            "ts": self.logged_at,
            "tool": self.tool_name,
            "risk": self.risk_level,
            "domain": self.domain,
            "decision": "ALLOW" if self.allowed else ("NEED_APPROVAL" if self.action_needed == "approve" else "DENY"),
            "reason": self.reason,
            "args_hash": self.args_hash,
            "safe_summary": self.safe_summary,
            "bypass": self.bypass,
            "breakglass": self.breakglass,
            "error": self.error,
        }

    def to_block_message(self) -> str:
        """Format message for blocked tool calls."""
        lines = ["## Policy Gate Blocked\n"]
        lines.append(f"**Tool:** `{self.tool_name}`")
        lines.append(f"**Risk Level:** {self.risk_level}")
        lines.append(f"**Domain:** {self.domain}")
        lines.append(f"**Action Needed:** {self.action_needed}")
        lines.append(f"**Reason:** {self.reason}")
        lines.append(f"**Args Hash:** `{self.args_hash}`")
        lines.append("")

        if self.action_needed == "approve":
            lines.append("To proceed, request approval:")
            lines.append(f"```")
            lines.append(f"duro_grant_approval(")
            lines.append(f"  action_id=\"{self.tool_name}:{self.args_hash}\",")
            lines.append(f"  reason=\"<why this action is needed>\"")
            lines.append(f")")
            lines.append(f"```")
        elif self.action_needed == "downgrade":
            lines.append("This action exceeds current autonomy level. Consider:")
            lines.append("- Using a safer alternative")
            lines.append("- Building reputation in this domain first")

        return "\n".join(lines)


# === AUDIT LOGGING ===

def _log_gate_decision(decision: GateDecision, arguments: Dict[str, Any] = None):
    """
    Log gate decision to unified audit trail.

    Uses Layer 5 unified audit with hash chain if available,
    falls back to legacy file-based logging otherwise.
    """
    try:
        # Prepare redacted args preview
        args_preview = None
        if arguments is not None:
            args_preview = redact_arguments(arguments)

        # Use unified audit if available
        if UNIFIED_AUDIT_AVAILABLE:
            # Build action_id for scoped approvals
            action_id = f"{decision.tool_name}:{decision.args_hash}"

            event = build_gate_event(
                tool_name=decision.tool_name,
                decision="ALLOW" if decision.allowed else ("NEED_APPROVAL" if decision.action_needed == "approve" else "DENY"),
                reason=decision.reason,
                risk_level=decision.risk_level,
                domain=decision.domain,
                action_id=action_id,
                args_hash=decision.args_hash,
                args_preview=args_preview,
                action_needed=decision.action_needed,
                bypass=decision.bypass,
                breakglass=decision.breakglass,
                error=decision.error,
            )
            append_event(event)
        else:
            # Fallback to legacy logging
            with open(GATE_AUDIT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(decision.to_audit_record()) + "\n")

            if arguments is not None:
                debug_record = {
                    "ts": decision.logged_at,
                    "tool": decision.tool_name,
                    "args_hash": decision.args_hash,
                    "args_redacted": args_preview,
                }
                with open(DEBUG_ARGS_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(debug_record) + "\n")

    except Exception as e:
        # Logging should never break the gate
        print(f"[WARN] Gate audit log failed: {e}", file=sys.stderr)


def _log_secret_detection(tool_name: str, scan_result: Any, action: str, reason: str):
    """
    Log secret detection event to unified audit trail.

    Only metadata is logged - never the actual secrets.
    """
    if not SECRETS_GUARD_AVAILABLE:
        return

    try:
        # Extract metadata from scan result
        match_count = len(scan_result.matches) if hasattr(scan_result, 'matches') else 0
        patterns = []
        if hasattr(scan_result, 'matches'):
            patterns = list(set(m.pattern_name for m in scan_result.matches))

        # Use unified audit if available
        if UNIFIED_AUDIT_AVAILABLE:
            event_type = EventType.SECRETS_BLOCKED if action == "blocked" else EventType.SECRETS_DETECTED
            event = build_secrets_event(
                event_type=event_type,
                tool_name=tool_name,
                action=action,
                reason=reason,
                match_count=match_count,
                patterns=patterns,
            )
            append_event(event)
        else:
            # Fallback to legacy logging
            audit_entry = create_secret_audit_entry(tool_name, scan_result, action, reason)
            with open(SECRETS_AUDIT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry) + "\n")

    except Exception as e:
        # Logging should never break the gate
        print(f"[WARN] Secrets audit log failed: {e}", file=sys.stderr)


def _log_browser_violation(tool_name: str, url: str, reason: str):
    """
    Log browser sandbox violation to unified audit trail.
    """
    if not UNIFIED_AUDIT_AVAILABLE:
        return

    try:
        event = build_browser_event(
            event_type=EventType.BROWSER_DOMAIN_BLOCKED,
            url=url,
            reason=reason,
            severity=Severity.WARN,
        )
        # Add tool context
        event.tool = tool_name
        append_event(event)
    except Exception as e:
        print(f"[WARN] Browser audit log failed: {e}", file=sys.stderr)


def _log_workspace_violation(tool_name: str, path: str, reason: str, event_type: str = None):
    """
    Log workspace violation to unified audit trail.
    """
    if not UNIFIED_AUDIT_AVAILABLE:
        return

    try:
        ev_type = event_type or EventType.WORKSPACE_VIOLATION
        event = build_workspace_event(
            event_type=ev_type,
            path=path,
            reason=reason,
            tool_name=tool_name,
            severity=Severity.WARN,
        )
        append_event(event)
    except Exception as e:
        print(f"[WARN] Workspace audit log failed: {e}", file=sys.stderr)


# === MAIN GATE FUNCTION ===

def policy_gate(
    tool_name: str,
    arguments: Dict[str, Any],
    autonomy_available: bool = True,
    check_action_fn = None,
    classify_domain_fn = None,
    classify_risk_fn = None,
    get_enforcer_fn = None,
) -> GateDecision:
    """
    Central policy gate. EVERY tool call must pass through here.

    This is the constitutional checkpoint. If you can call a tool without
    hitting this function, you don't have policy enforcement.

    Args:
        tool_name: MCP tool being called
        arguments: Tool arguments (must be dict, will be normalized if not)
        autonomy_available: Whether autonomy system is loaded
        check_action_fn: Function to check action permission (from autonomy_ladder)
        classify_domain_fn: Function to classify action domain
        classify_risk_fn: Function to classify action risk
        get_enforcer_fn: Function to get autonomy enforcer (for approval tokens)

    Returns:
        GateDecision with allowed=True/False
    """
    # Defensive: normalize arguments to dict
    if not isinstance(arguments, dict):
        print(f"[WARN] policy_gate received non-dict arguments: {type(arguments).__name__}", file=sys.stderr)
        arguments = {"_raw": str(arguments)} if arguments else {}

    timestamp = utc_now_iso()
    args_hash = compute_args_hash(arguments)
    safe_summary = create_safe_summary(tool_name, arguments)

    # === CHECK BREAKGLASS ===
    breakglass_active = os.environ.get(BREAKGLASS_ENV, "").strip() == "1"
    if breakglass_active:
        print(f"[BREAKGLASS] Policy gate bypassed for: {tool_name}", file=sys.stderr)
        decision = GateDecision(
            allowed=True,
            action_needed="none",
            reason="BREAKGLASS override active",
            tool_name=tool_name,
            risk_level="unknown",
            domain="unknown",
            args_hash=args_hash,
            safe_summary=safe_summary,
            logged_at=timestamp,
            bypass=False,
            breakglass=True,
        )
        _log_gate_decision(decision, arguments)
        return decision

    # === CHECK BYPASS SET ===
    if tool_name in GATE_BYPASS_TOOLS:
        decision = GateDecision(
            allowed=True,
            action_needed="none",
            reason=f"bypass: introspection tool",
            tool_name=tool_name,
            risk_level="read",
            domain="meta",
            args_hash=args_hash,
            safe_summary=safe_summary,
            logged_at=timestamp,
            bypass=True,
        )
        _log_gate_decision(decision, arguments)
        return decision

    # === FAIL-CLOSED CHECK ===
    if not autonomy_available:
        if FAIL_CLOSED:
            decision = GateDecision(
                allowed=False,
                action_needed="downgrade",
                reason="FAIL-CLOSED: Autonomy system unavailable",
                tool_name=tool_name,
                risk_level="unknown",
                domain="unknown",
                args_hash=args_hash,
                safe_summary=safe_summary,
                logged_at=timestamp,
                error="autonomy_unavailable",
            )
            _log_gate_decision(decision, arguments)
            return decision
        else:
            # Fail-open (not recommended)
            print(f"[WARN] Autonomy unavailable, allowing {tool_name} (fail-open mode)", file=sys.stderr)
            decision = GateDecision(
                allowed=True,
                action_needed="none",
                reason="Autonomy unavailable, fail-open mode",
                tool_name=tool_name,
                risk_level="unknown",
                domain="unknown",
                args_hash=args_hash,
                safe_summary=safe_summary,
                logged_at=timestamp,
                error="autonomy_unavailable_failopen",
            )
            _log_gate_decision(decision, arguments)
            return decision

    # === CLASSIFY ACTION ===
    try:
        # Get risk level
        from autonomy_ladder import ActionRisk
        if classify_risk_fn:
            risk = classify_risk_fn(tool_name, arguments)
        else:
            risk = ActionRisk.from_action(tool_name, arguments)
        risk_level = risk.value if hasattr(risk, 'value') else str(risk)

        # Get domain
        if classify_domain_fn:
            domain = classify_domain_fn(tool_name)
        else:
            from autonomy_ladder import classify_action_domain
            domain = classify_action_domain(tool_name)

    except Exception as e:
        # Classification error = DENY (fail-closed)
        decision = GateDecision(
            allowed=False,
            action_needed="downgrade",
            reason=f"FAIL-CLOSED: Classification error: {e}",
            tool_name=tool_name,
            risk_level="unknown",
            domain="unknown",
            args_hash=args_hash,
            safe_summary=safe_summary,
            logged_at=timestamp,
            error=f"classification_error: {e}",
        )
        _log_gate_decision(decision, arguments)
        return decision

    # === CHECK PERMISSION ===
    try:
        # Build scoped action_id for approval token lookup
        action_id = f"{tool_name}:{args_hash}"

        # check_action signature: check_action(action, context=None, action_id=None, consume_token=True)
        # It classifies domain and risk internally
        if check_action_fn:
            # Pass tool_name as action, arguments as context (for risk hints)
            # Pass scoped action_id so approval tokens are matched correctly
            permission = check_action_fn(tool_name, arguments, action_id, False)  # Don't consume yet
        else:
            from autonomy_ladder import check_action
            permission = check_action(tool_name, arguments, action_id, False)

        # Check for active approval token (separate from check_action's internal check)
        has_approval = False
        if get_enforcer_fn:
            enforcer = get_enforcer_fn()
            if enforcer and hasattr(enforcer, 'approval_tokens'):
                token = enforcer.approval_tokens.get(action_id)
                if token and hasattr(token, 'is_valid') and token.is_valid:
                    has_approval = True

        # Determine final decision
        # IMPORTANT: If allowed via token, we must CONSUME IT NOW (one-shot)
        # We called check_action with consume_token=False, so token is still valid

        if permission.allowed:
            # Check if this was allowed via a token that we need to consume
            if hasattr(permission, 'allowed_via_token') and permission.allowed_via_token:
                # CONSUME THE ONE-SHOT TOKEN NOW (fail-closed if it errors)
                try:
                    if get_enforcer_fn:
                        enforcer = get_enforcer_fn()
                        consumed = enforcer.use_approval(action_id, used_by=f"gate_{tool_name}")
                        if not consumed:
                            # Token vanished between check and consume (race condition)
                            decision = GateDecision(
                                allowed=False,
                                action_needed="approve",
                                reason="Approval token expired or already consumed",
                                tool_name=tool_name,
                                risk_level=risk_level,
                                domain=domain,
                                args_hash=args_hash,
                                safe_summary=safe_summary,
                                logged_at=timestamp,
                                error="token_consumed_race",
                            )
                            _log_gate_decision(decision, arguments)
                            return decision
                    # Token consumed successfully - allow the action
                    decision = GateDecision(
                        allowed=True,
                        action_needed="none",
                        reason=f"Allowed via one-shot approval (token consumed)",
                        tool_name=tool_name,
                        risk_level=risk_level,
                        domain=domain,
                        args_hash=args_hash,
                        safe_summary=safe_summary,
                        logged_at=timestamp,
                    )
                except Exception as e:
                    # Token consumption error = DENY (fail-closed)
                    decision = GateDecision(
                        allowed=False,
                        action_needed="approve",
                        reason=f"FAIL-CLOSED: Token consumption error: {e}",
                        tool_name=tool_name,
                        risk_level=risk_level,
                        domain=domain,
                        args_hash=args_hash,
                        safe_summary=safe_summary,
                        logged_at=timestamp,
                        error=f"token_consume_error: {e}",
                    )
                    _log_gate_decision(decision, arguments)
                    return decision
            else:
                # Allowed without needing approval token
                decision = GateDecision(
                    allowed=True,
                    action_needed="none",
                    reason=permission.reason if hasattr(permission, 'reason') else "allowed",
                    tool_name=tool_name,
                    risk_level=risk_level,
                    domain=domain,
                    args_hash=args_hash,
                    safe_summary=safe_summary,
                    logged_at=timestamp,
                )
        elif hasattr(permission, 'requires_approval') and permission.requires_approval:
            # Action requires approval and no valid token exists
            # (If a token existed, check_action would have returned allowed=True with allowed_via_token=True)
            decision = GateDecision(
                allowed=False,
                action_needed="approve",
                reason=permission.reason if hasattr(permission, 'reason') else "requires approval",
                tool_name=tool_name,
                risk_level=risk_level,
                domain=domain,
                args_hash=args_hash,
                safe_summary=safe_summary,
                logged_at=timestamp,
            )
        else:
            # Denied outright (not even approval can help)
            decision = GateDecision(
                allowed=False,
                action_needed="downgrade",
                reason=permission.reason if hasattr(permission, 'reason') else "denied",
                tool_name=tool_name,
                risk_level=risk_level,
                domain=domain,
                args_hash=args_hash,
                safe_summary=safe_summary,
                logged_at=timestamp,
            )

        # === WORKSPACE CONSTRAINTS (Layer 2) ===
        # If action is allowed, check if paths are within workspace
        if decision.allowed and WORKSPACE_GUARD_AVAILABLE:
            try:
                ws_allowed, ws_reason, ws_requires_approval = check_workspace_constraints(
                    tool_name, arguments
                )

                if not ws_allowed:
                    # Extract path for logging
                    path_arg = arguments.get("path") or arguments.get("file_path") or ""

                    # Log workspace violation to unified audit
                    _log_workspace_violation(tool_name, path_arg, ws_reason)

                    # Workspace violation - block
                    decision = GateDecision(
                        allowed=False,
                        action_needed="downgrade",
                        reason=f"Workspace violation: {ws_reason}",
                        tool_name=tool_name,
                        risk_level=risk_level,
                        domain=domain,
                        args_hash=args_hash,
                        safe_summary=safe_summary,
                        logged_at=timestamp,
                        error="workspace_violation",
                    )
                elif ws_requires_approval and not has_approval:
                    # High-risk path - require approval
                    decision = GateDecision(
                        allowed=False,
                        action_needed="approve",
                        reason=f"High-risk path requires approval: {ws_reason}",
                        tool_name=tool_name,
                        risk_level="high_risk",
                        domain=domain,
                        args_hash=args_hash,
                        safe_summary=safe_summary,
                        logged_at=timestamp,
                    )
                # else: workspace check passed, keep original decision

            except Exception as e:
                # Workspace check error = DENY (fail-closed)
                decision = GateDecision(
                    allowed=False,
                    action_needed="downgrade",
                    reason=f"FAIL-CLOSED: Workspace check error: {e}",
                    tool_name=tool_name,
                    risk_level=risk_level,
                    domain=domain,
                    args_hash=args_hash,
                    safe_summary=safe_summary,
                    logged_at=timestamp,
                    error=f"workspace_error: {e}",
                )

        # === SECRETS CONSTRAINTS (Layer 3) ===
        # Check for secrets in arguments - never let them leak to logs/memory
        if decision.allowed and SECRETS_GUARD_AVAILABLE:
            try:
                # Special handling for Bash commands
                if tool_name == "Bash" and "command" in arguments:
                    bash_allowed, bash_reason = check_bash_secrets(arguments["command"])
                    if not bash_allowed:
                        decision = GateDecision(
                            allowed=False,
                            action_needed="downgrade",
                            reason=f"Secrets policy violation: {bash_reason}",
                            tool_name=tool_name,
                            risk_level=risk_level,
                            domain=domain,
                            args_hash=args_hash,
                            safe_summary=safe_summary,
                            logged_at=timestamp,
                            error="secrets_bash_violation",
                        )

                # General secrets check for all tools
                if decision.allowed:
                    secrets_allowed, secrets_reason, scan_result = check_secrets_policy(
                        tool_name, arguments
                    )

                    if not secrets_allowed:
                        # Log the secret detection (metadata only, no actual secrets)
                        if scan_result and scan_result.has_secrets:
                            _log_secret_detection(tool_name, scan_result, "blocked", secrets_reason)

                        decision = GateDecision(
                            allowed=False,
                            action_needed="downgrade",
                            reason=f"Secrets policy violation: {secrets_reason}",
                            tool_name=tool_name,
                            risk_level=risk_level,
                            domain=domain,
                            args_hash=args_hash,
                            safe_summary=safe_summary,
                            logged_at=timestamp,
                            error="secrets_violation",
                        )
                    elif scan_result and scan_result.has_secrets:
                        # Allowed but secrets detected - log for audit
                        _log_secret_detection(tool_name, scan_result, "allowed", secrets_reason)

            except Exception as e:
                # Secrets check error = DENY (fail-closed)
                decision = GateDecision(
                    allowed=False,
                    action_needed="downgrade",
                    reason=f"FAIL-CLOSED: Secrets check error: {e}",
                    tool_name=tool_name,
                    risk_level=risk_level,
                    domain=domain,
                    args_hash=args_hash,
                    safe_summary=safe_summary,
                    logged_at=timestamp,
                    error=f"secrets_error: {e}",
                )

        # === BROWSER SANDBOX CONSTRAINTS (Layer 4) ===
        # Check if browser tools are accessing allowed domains
        if decision.allowed and BROWSER_GUARD_AVAILABLE and tool_name in BROWSER_TOOLS:
            try:
                # Extract URL from arguments
                url = None
                if "url" in arguments:
                    url = arguments["url"]
                elif "query" in arguments and tool_name in ("WebSearch", "mcp__superagi__web_search"):
                    # Search queries don't have URLs to validate
                    url = None

                if url:
                    browser_allowed, browser_reason = check_browser_policy(
                        url=url,
                        action="navigate",
                        config=get_sandbox_config()
                    )

                    if not browser_allowed:
                        # Log browser violation to unified audit
                        _log_browser_violation(tool_name, url, browser_reason)

                        decision = GateDecision(
                            allowed=False,
                            action_needed="downgrade",
                            reason=f"Browser sandbox violation: {browser_reason}",
                            tool_name=tool_name,
                            risk_level=risk_level,
                            domain=domain,
                            args_hash=args_hash,
                            safe_summary=safe_summary,
                            logged_at=timestamp,
                            error="browser_sandbox_violation",
                        )

            except Exception as e:
                # Browser check error = DENY (fail-closed)
                decision = GateDecision(
                    allowed=False,
                    action_needed="downgrade",
                    reason=f"FAIL-CLOSED: Browser sandbox check error: {e}",
                    tool_name=tool_name,
                    risk_level=risk_level,
                    domain=domain,
                    args_hash=args_hash,
                    safe_summary=safe_summary,
                    logged_at=timestamp,
                    error=f"browser_error: {e}",
                )

        # === INTENT GUARD (Layer 6) ===
        # Tools that require intent tokens must have valid, unexpired intent
        # This enforces that untrusted content cannot trigger risky tool calls
        if decision.allowed and INTENT_GUARD_AVAILABLE:
            try:
                # Check if this tool requires intent and if we have valid intent
                intent_allowed, intent_reason, intent_action = require_intent(
                    tool_name, arguments
                )

                if not intent_allowed:
                    # No valid intent for this tool call
                    decision = GateDecision(
                        allowed=False,
                        action_needed=intent_action or "approve",
                        reason=f"Intent required: {intent_reason}",
                        tool_name=tool_name,
                        risk_level=risk_level,
                        domain=domain,
                        args_hash=args_hash,
                        safe_summary=safe_summary,
                        logged_at=timestamp,
                        error="intent_required",
                    )

                    # Log intent denial to unified audit (Layer 6 → Layer 5)
                    if UNIFIED_AUDIT_AVAILABLE:
                        intent_event = build_intent_event(
                            event_type=EventType.INTENT_DENIED,
                            tool_name=tool_name,
                            args_hash=args_hash,
                            reason=intent_reason,
                            severity=Severity.WARN,
                        )
                        append_event(intent_event)
                else:
                    # Intent verified successfully - log consumption
                    if UNIFIED_AUDIT_AVAILABLE and tool_name in INTENT_REQUIRED_TOOLS:
                        current = get_current_intent()
                        intent_event = build_intent_event(
                            event_type=EventType.INTENT_CONSUMED,
                            tool_name=tool_name,
                            token_id=current.token_id if current else None,
                            args_hash=args_hash,
                            reason=intent_reason,
                            severity=Severity.INFO,
                        )
                        append_event(intent_event)

            except Exception as e:
                # Intent check error = DENY (fail-closed)
                decision = GateDecision(
                    allowed=False,
                    action_needed="downgrade",
                    reason=f"FAIL-CLOSED: Intent guard check error: {e}",
                    tool_name=tool_name,
                    risk_level=risk_level,
                    domain=domain,
                    args_hash=args_hash,
                    safe_summary=safe_summary,
                    logged_at=timestamp,
                    error=f"intent_error: {e}",
                )

        _log_gate_decision(decision, arguments)
        return decision

    except Exception as e:
        # Permission check error = DENY (fail-closed)
        decision = GateDecision(
            allowed=False,
            action_needed="downgrade",
            reason=f"FAIL-CLOSED: Permission check error: {e}",
            tool_name=tool_name,
            risk_level=risk_level,
            domain=domain,
            args_hash=args_hash,
            safe_summary=safe_summary,
            logged_at=timestamp,
            error=f"permission_error: {e}",
        )
        _log_gate_decision(decision, arguments)
        return decision


# === APPROVAL SCOPING ===

def create_scoped_approval_id(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Create approval ID scoped to the exact action.

    Format: {tool_name}:{args_hash}
    """
    args_hash = compute_args_hash(arguments)
    return f"{tool_name}:{args_hash}"


def validate_approval_scope(
    approval_id: str,
    tool_name: str,
    arguments: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Validate that an approval token matches the exact action.

    Returns (valid, reason)
    """
    expected_id = create_scoped_approval_id(tool_name, arguments)

    if approval_id == expected_id:
        return True, "exact match"

    # Check if it's a tool-level approval (less secure, legacy support)
    if approval_id == tool_name:
        return True, "tool-level approval (legacy, not recommended)"

    return False, f"approval scope mismatch: expected {expected_id}, got {approval_id}"


# === QUERY AUDIT LOG ===

def query_gate_audit(
    limit: int = 100,
    tool_filter: str = None,
    decision_filter: str = None,
    since: str = None,
) -> List[Dict[str, Any]]:
    """
    Query the gate audit log.

    Args:
        limit: Max records to return
        tool_filter: Filter by tool name (exact match)
        decision_filter: Filter by decision (ALLOW/DENY/NEED_APPROVAL)
        since: ISO timestamp to filter from

    Returns:
        List of audit records, newest first
    """
    if not GATE_AUDIT_FILE.exists():
        return []

    records = []
    with open(GATE_AUDIT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)

                # Apply filters
                if tool_filter and record.get("tool") != tool_filter:
                    continue
                if decision_filter and record.get("decision") != decision_filter:
                    continue
                if since and record.get("ts", "") < since:
                    continue

                records.append(record)
            except json.JSONDecodeError:
                continue

    # Return newest first, limited
    records.reverse()
    return records[:limit]


def get_layer6_status() -> Dict[str, Any]:
    """Get Layer 6 (intent guard + prompt firewall) status."""
    status = {
        "intent_guard_available": INTENT_GUARD_AVAILABLE,
        "intent_guard_error": INTENT_GUARD_ERROR,
        "prompt_firewall_available": PROMPT_FIREWALL_AVAILABLE,
        "prompt_firewall_error": PROMPT_FIREWALL_ERROR,
    }

    if INTENT_GUARD_AVAILABLE:
        try:
            status["intent_status"] = get_intent_status()
        except Exception as e:
            status["intent_status_error"] = str(e)

    if PROMPT_FIREWALL_AVAILABLE:
        try:
            status["firewall_status"] = get_firewall_status()
        except Exception as e:
            status["firewall_status_error"] = str(e)

    return status


def get_gate_stats() -> Dict[str, Any]:
    """Get summary statistics from gate audit log."""
    if not GATE_AUDIT_FILE.exists():
        return {"total": 0, "by_decision": {}, "by_tool": {}}

    total = 0
    by_decision = {}
    by_tool = {}
    bypasses = 0
    breakglass = 0
    errors = 0

    with open(GATE_AUDIT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                total += 1

                decision = record.get("decision", "UNKNOWN")
                by_decision[decision] = by_decision.get(decision, 0) + 1

                tool = record.get("tool", "unknown")
                by_tool[tool] = by_tool.get(tool, 0) + 1

                if record.get("bypass"):
                    bypasses += 1
                if record.get("breakglass"):
                    breakglass += 1
                if record.get("error"):
                    errors += 1

            except json.JSONDecodeError:
                continue

    return {
        "total": total,
        "by_decision": by_decision,
        "by_tool": dict(sorted(by_tool.items(), key=lambda x: -x[1])[:10]),  # Top 10
        "bypasses": bypasses,
        "breakglass_uses": breakglass,
        "errors": errors,
    }
