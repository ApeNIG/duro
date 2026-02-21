"""
Intent Guard - Layer 6 Security (Capability Tokens)
====================================================

The seatbelt lock. Untrusted content cannot mint new intentions.

Core principle: Tool calls must carry an intent token that originates
from a trusted source (user/system). Without a valid token, risky
tools are blocked.

This turns prompt injection from "a magic spell" into "a note on a napkin."

Design:
- Intent tokens are issued on user messages (trusted source)
- Tokens have TTL and scope (optional tool restrictions)
- Risky tools require valid intent token to execute
- Untrusted content (browser, web) cannot provide tokens
"""

import hashlib
import json
import os
import secrets
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from time_utils import utc_now, utc_now_iso

# Optional audit logging (Layer 5 integration)
AUDIT_AVAILABLE = False
try:
    from audit_log import (
        append_event, build_intent_event, EventType, Severity
    )
    AUDIT_AVAILABLE = True
except ImportError:
    pass  # Audit not available, logging disabled


# ============================================================
# CONFIGURATION
# ============================================================

# Default TTL for intent tokens (5 minutes)
DEFAULT_INTENT_TTL_SECONDS = 300

# Maximum TTL (30 minutes)
MAX_INTENT_TTL_SECONDS = 1800

# Environment variable to disable intent enforcement (testing only)
INTENT_BYPASS_ENV = "DURO_INTENT_BYPASS"

# Environment variable to control auto-start behavior (for trusted clients like Claude Code)
# DEFAULT: Auto-start is ENABLED for safe tools (learning/memory operations)
# Set DURO_INTENT_AUTO_START=0 to disable auto-start (require explicit on_user_message())
# This accommodates Claude Code which goes direct to tool calls without message hooks.
INTENT_AUTO_START_ENV = "DURO_INTENT_AUTO_START"

# Thread lock for token operations
_token_lock = threading.Lock()


# ============================================================
# TOOLS REQUIRING INTENT
# ============================================================

# High-risk tools that MUST have valid intent token
INTENT_REQUIRED_TOOLS: Set[str] = {
    # File operations
    "Write",
    "Edit",
    "NotebookEdit",

    # Shell execution
    "Bash",
    "mcp__superagi__shell_execute",
    "mcp__superagi__execute_python",

    # Web/browser (untrusted source)
    "WebFetch",
    "WebSearch",
    "mcp__superagi__web_search",
    "mcp__superagi__read_webpage",

    # Memory persistence
    "duro_store_fact",
    "duro_store_decision",
    "duro_store_incident",
    "duro_store_change",
    "duro_save_memory",
    "duro_save_learning",

    # Workspace changes
    "duro_workspace_add",

    # Destructive operations
    "duro_delete_artifact",
    "duro_batch_delete",

    # Authorization operations (CRITICAL: prevents model self-authorization)
    "duro_grant_approval",
}

# Tools that should log intent but not require it (medium risk)
INTENT_LOGGED_TOOLS: Set[str] = {
    "Read",
    "Glob",
    "Grep",
    "duro_query_memory",
    "duro_semantic_search",
}

# Tools from untrusted sources (browser, web)
UNTRUSTED_SOURCE_TOOLS: Set[str] = {
    "WebFetch",
    "WebSearch",
    "mcp__superagi__web_search",
    "mcp__superagi__read_webpage",
    "mcp__playwright__navigate",
    "mcp__playwright__screenshot",
}

# Tools safe for auto-start when DURO_INTENT_AUTO_START=1
# These are non-destructive memory/learning operations that should be frictionless
# EXCLUDES: Bash, destructive ops, authorization ops, web/untrusted sources
SAFE_AUTO_START_TOOLS: Set[str] = {
    # Memory persistence (non-destructive)
    "duro_store_fact",
    "duro_store_decision",
    "duro_store_incident",
    "duro_store_change",
    "duro_save_memory",
    "duro_save_learning",
    "duro_log_task",
    "duro_log_failure",
    "duro_store_checklist",
    "duro_store_design_ref",
    # Episode tracking
    "duro_create_episode",
    "duro_add_episode_action",
    "duro_close_episode",
    "duro_evaluate_episode",
    # Decision validation (non-destructive)
    "duro_validate_decision",
    "duro_link_decision",
    "duro_reinforce_fact",
    # Read-only operations (always safe)
    "duro_query_memory",
    "duro_semantic_search",
    "duro_get_artifact",
    "duro_list_artifacts",
    "duro_load_context",
    "duro_status",
    "duro_check_rules",
    "duro_list_rules",
    "duro_get_project",
    "duro_list_projects",
}


def normalize_tool_name(tool_name: str) -> str:
    """
    Normalize tool name by stripping MCP prefixes.

    Handles: mcp__duro__duro_save_learning -> duro_save_learning
    """
    # Strip common MCP prefixes
    prefixes = ["mcp__duro__", "mcp__superagi__", "mcp__"]
    for prefix in prefixes:
        if tool_name.startswith(prefix):
            return tool_name[len(prefix):]
    return tool_name


# ============================================================
# INTENT TOKEN
# ============================================================

@dataclass
class IntentToken:
    """
    Capability token representing user/system intent.

    Tokens are issued on trusted user messages and allow
    execution of risky tools within their scope and TTL.

    CRITICAL: Tokens are bound to user turns via turn_id.
    A token from turn A cannot authorize actions in turn B.
    """
    token_id: str
    issued_at: str
    expires_at: str
    source: str  # "user", "system", "approval"
    turn_id: Optional[str] = None  # User turn this token is bound to
    scope: Optional[List[str]] = None  # Optional tool restrictions
    message_hash: Optional[str] = None  # Hash of originating message
    consumed: bool = False
    consumed_by: Optional[str] = None
    consumed_at: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid (not expired, not consumed)."""
        if self.consumed:
            return False
        now = utc_now()
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return now < expires

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        now = utc_now()
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return now >= expires

    def allows_tool(self, tool_name: str) -> bool:
        """Check if this token allows the specified tool."""
        if not self.is_valid:
            return False
        # No scope = all tools allowed
        if self.scope is None:
            return True
        return tool_name in self.scope

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "token_id": self.token_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "source": self.source,
            "turn_id": self.turn_id,
            "scope": self.scope,
            "message_hash": self.message_hash,
            "consumed": self.consumed,
            "consumed_by": self.consumed_by,
            "consumed_at": self.consumed_at,
        }


# ============================================================
# INTENT STORE
# ============================================================

class IntentStore:
    """
    In-memory store for active intent tokens.

    Tokens are ephemeral - they don't persist across restarts.
    This is intentional: restart = fresh intent required.
    """

    def __init__(self):
        self._tokens: Dict[str, IntentToken] = {}
        self._current_intent: Optional[str] = None
        self._lock = threading.RLock()  # RLock allows reentrant acquisition (get_stats -> get_current)

    def issue(
        self,
        source: str = "user",
        ttl_seconds: int = DEFAULT_INTENT_TTL_SECONDS,
        scope: Optional[List[str]] = None,
        message_hash: Optional[str] = None,
        turn_id: Optional[str] = None,
    ) -> IntentToken:
        """
        Issue a new intent token.

        Args:
            source: Origin of intent ("user", "system", "approval")
            ttl_seconds: Time-to-live in seconds
            scope: Optional list of allowed tools
            message_hash: Optional hash of originating message
            turn_id: User turn this token is bound to

        Returns:
            New IntentToken
        """
        with self._lock:
            # Cap TTL
            ttl = min(ttl_seconds, MAX_INTENT_TTL_SECONDS)

            # Generate token ID
            now = utc_now()
            random_suffix = hashlib.sha256(os.urandom(16)).hexdigest()[:8]
            token_id = f"intent_{now.strftime('%Y%m%d_%H%M%S')}_{random_suffix}"

            # Calculate expiration
            expires = now + timedelta(seconds=ttl)

            token = IntentToken(
                token_id=token_id,
                issued_at=utc_now_iso(),
                expires_at=expires.isoformat().replace("+00:00", "Z"),
                source=source,
                turn_id=turn_id,
                scope=scope,
                message_hash=message_hash,
            )

            # Store token
            self._tokens[token_id] = token
            self._current_intent = token_id

            # Cleanup expired tokens
            self._cleanup_expired()

            return token

    def verify(self, token_id: str) -> Tuple[bool, str]:
        """
        Verify an intent token.

        Returns (valid, reason)
        """
        with self._lock:
            if token_id not in self._tokens:
                return False, "Token not found"

            token = self._tokens[token_id]

            if token.consumed:
                return False, f"Token already consumed by {token.consumed_by}"

            if token.is_expired:
                return False, "Token expired"

            return True, "Valid"

    def verify_for_tool(self, token_id: str, tool_name: str) -> Tuple[bool, str]:
        """
        Verify token is valid for a specific tool.

        Returns (valid, reason)
        """
        valid, reason = self.verify(token_id)
        if not valid:
            return False, reason

        token = self._tokens[token_id]
        if not token.allows_tool(tool_name):
            return False, f"Token scope does not allow {tool_name}"

        return True, "Valid for tool"

    def consume(self, token_id: str, consumed_by: str) -> bool:
        """
        Consume (invalidate) a token after use.

        For one-shot tokens, call this after successful tool execution.
        Returns True if consumed, False if already consumed/invalid.
        """
        with self._lock:
            if token_id not in self._tokens:
                return False

            token = self._tokens[token_id]
            if token.consumed:
                return False

            token.consumed = True
            token.consumed_by = consumed_by
            token.consumed_at = utc_now_iso()
            return True

    def get_current(self) -> Optional[IntentToken]:
        """Get the current (most recent valid) intent token."""
        with self._lock:
            if self._current_intent and self._current_intent in self._tokens:
                token = self._tokens[self._current_intent]
                if token.is_valid:
                    return token

            # Find most recent valid token
            valid_tokens = [t for t in self._tokens.values() if t.is_valid]
            if valid_tokens:
                # Sort by issued_at descending
                valid_tokens.sort(key=lambda t: t.issued_at, reverse=True)
                self._current_intent = valid_tokens[0].token_id
                return valid_tokens[0]

            return None

    def get(self, token_id: str) -> Optional[IntentToken]:
        """Get a specific token by ID."""
        with self._lock:
            return self._tokens.get(token_id)

    def list_active(self) -> List[IntentToken]:
        """List all active (valid) tokens."""
        with self._lock:
            return [t for t in self._tokens.values() if t.is_valid]

    def revoke_all(self) -> int:
        """Revoke all tokens. Returns count revoked."""
        with self._lock:
            count = len(self._tokens)
            self._tokens.clear()
            self._current_intent = None
            return count

    def _cleanup_expired(self):
        """Remove expired tokens (internal, called with lock held)."""
        expired = [
            tid for tid, token in self._tokens.items()
            if token.is_expired
        ]
        for tid in expired:
            del self._tokens[tid]
        if self._current_intent in expired:
            self._current_intent = None

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about intent tokens."""
        with self._lock:
            total = len(self._tokens)
            valid = len([t for t in self._tokens.values() if t.is_valid])
            expired = len([t for t in self._tokens.values() if t.is_expired])
            consumed = len([t for t in self._tokens.values() if t.consumed])

            return {
                "total_tokens": total,
                "valid_tokens": valid,
                "expired_tokens": expired,
                "consumed_tokens": consumed,
                "current_intent": self._current_intent,
                "has_valid_intent": self.get_current() is not None,
            }


# Global intent store
_intent_store = IntentStore()


# ============================================================
# PUBLIC API
# ============================================================

def issue_intent(
    source: str = "user",
    ttl_seconds: int = DEFAULT_INTENT_TTL_SECONDS,
    scope: Optional[List[str]] = None,
    message_hash: Optional[str] = None,
    turn_id: Optional[str] = None,
) -> IntentToken:
    """
    Issue a new intent token.

    Call this on each user message to establish trusted intent.
    The turn_id binds this token to a specific user turn.
    """
    return _intent_store.issue(source, ttl_seconds, scope, message_hash, turn_id)


def verify_intent(token_id: str) -> Tuple[bool, str]:
    """Verify an intent token is valid."""
    return _intent_store.verify(token_id)


def get_current_intent() -> Optional[IntentToken]:
    """Get the current valid intent token."""
    return _intent_store.get_current()


def get_intent_store() -> IntentStore:
    """Get the global intent store."""
    return _intent_store


def require_intent(
    tool_name: str,
    arguments: Dict[str, Any],
    intent_id: Optional[str] = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Check if a tool call has valid intent.

    Args:
        tool_name: The tool being called
        arguments: Tool arguments (may contain intent_id)
        intent_id: Explicit intent ID (overrides arguments)

    Returns:
        (allowed, reason, action_needed)
        action_needed is "none", "intent", or "approval"
    """
    # Normalize tool name to handle MCP prefixes
    normalized_tool = normalize_tool_name(tool_name)

    # DEBUG: Log what we're checking
    print(f"[INTENT DEBUG] require_intent called: original={tool_name}, normalized={normalized_tool}", file=sys.stderr)

    # Check bypass mode
    if os.environ.get(INTENT_BYPASS_ENV, "").strip() == "1":
        return True, "Intent bypass active (testing)", "none"

    # Tools that don't require intent
    if normalized_tool not in INTENT_REQUIRED_TOOLS:
        return True, "Tool does not require intent", "none"

    # Get session context
    session = get_session_context()

    # AUTO-START: For trusted clients (like Claude Code) that go direct to tool calls
    # without message hooks, auto-start a user turn on first tool call.
    #
    # SAFETY CONSTRAINTS:
    # 1. Never auto-start in untrusted context (browser/web output active)
    # 2. Only auto-start for safe tools (no Bash, delete, approval ops)
    # 3. Fail-closed if constraints not met
    print(f"[INTENT DEBUG] current_user_turn_id={session.current_user_turn_id}", file=sys.stderr)
    if session.current_user_turn_id is None:
        # BLOCK: Untrusted context cannot trigger auto-start
        if session.last_tool_output_untrusted:
            return False, "Untrusted context; cannot auto-start user turn", "intent"

        # AUTO-START DEFAULT: Enable for safe tools unless explicitly disabled
        # This accommodates Claude Code which goes direct to tool calls without message hooks.
        # Set DURO_INTENT_AUTO_START=0 to disable.
        auto_start_disabled = os.environ.get(INTENT_AUTO_START_ENV, "").strip() == "0"

        if auto_start_disabled:
            # Explicitly disabled - require on_user_message() hook
            return False, "No user turn started; on_user_message() not called (auto-start disabled)", "intent"

        # Only auto-start for safe tools (non-destructive memory/learning operations)
        if normalized_tool not in SAFE_AUTO_START_TOOLS:
            return False, f"Tool {normalized_tool} not in SAFE_AUTO_START_TOOLS; requires explicit user turn", "intent"

        # Auto-start user turn and issue intent
        print(f"[INTENT DEBUG] Auto-starting for safe tool: {normalized_tool}", file=sys.stderr)
        token = on_user_message(f"[auto-start] Tool call: {normalized_tool}")
        session = get_session_context()  # Refresh after turn start
        print(f"[INTENT DEBUG] Auto-start complete. Token={token.token_id if token else None}, turn_id={session.current_user_turn_id}", file=sys.stderr)

        # Log the auto-start for audit trail
        if AUDIT_AVAILABLE:
            event = build_intent_event(
                event_type=EventType.INTENT_ISSUED,
                token_id=token.token_id,
                reason=f"Auto-started user turn for {normalized_tool} (safe tool auto-start)",
                severity=Severity.INFO,
            )
            append_event(event)

        # IMMEDIATE SUCCESS for safe auto-start tools
        # We just created a valid token, so trust it immediately
        # This avoids edge cases where get_current_intent() might not find the token
        if token and token.is_valid:
            return True, f"Auto-started intent for safe tool: {token.token_id[:20]}...", "none"

    # Get intent ID from argument or parameter
    tid = intent_id or arguments.get("_intent_id") or arguments.get("intent_id")

    # Check for current valid intent (implicit)
    if not tid:
        current = get_current_intent()
        print(f"[INTENT DEBUG] get_current_intent returned: {current.token_id if current else None}", file=sys.stderr)
        if current:
            allows = current.allows_tool(normalized_tool)
            print(f"[INTENT DEBUG] allows_tool({normalized_tool})={allows}, is_valid={current.is_valid}, scope={current.scope}", file=sys.stderr)
            if allows:
                tid = current.token_id

    # FALLBACK: If we have an active turn but expired intent, re-issue for safe tools
    # This handles the case where a long conversation causes intent to expire mid-turn
    if not tid and session.current_user_turn_id and normalized_tool in SAFE_AUTO_START_TOOLS:
        print(f"[INTENT DEBUG] Re-issuing intent for safe tool (expired within turn): {normalized_tool}", file=sys.stderr)
        token = issue_intent(
            source="user",
            message_hash=session.current_user_turn_hash,
            turn_id=session.current_user_turn_id,
        )
        if token and token.is_valid:
            return True, f"Re-issued intent for safe tool: {token.token_id[:20]}...", "none"

    if not tid:
        print(f"[INTENT DEBUG] BLOCKED - no valid intent token for {normalized_tool}", file=sys.stderr)
        return False, "No intent token provided", "intent"

    # Verify the token
    valid, reason = _intent_store.verify_for_tool(tid, normalized_tool)
    if not valid:
        return False, f"Invalid intent: {reason}", "intent"

    # Verify token is bound to current user turn
    # This prevents "wrong token, right TTL" attacks
    token = _intent_store.get(tid)
    if not token:
        return False, "Token not found in store", "intent"

    # STRICT: Tokens MUST have turn_id binding
    # Unbound tokens (turn_id=None) are denied - no grace period
    # This catches: old tokens, bugs where turn_id wasn't passed, etc.
    if not token.turn_id:
        return False, "Token missing turn binding (unbound tokens not allowed)", "intent"

    if token.turn_id != session.current_user_turn_id:
        return False, f"Intent from wrong turn (token: {token.turn_id[:15]}..., current: {session.current_user_turn_id[:15]}...)", "intent"

    return True, f"Intent verified: {tid[:20]}...", "none"


def check_tool_origin(
    tool_name: str,
    origin: str,
    source_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Check if a tool call from a given origin is allowed.

    Args:
        tool_name: The tool being called
        origin: "user", "system", or "untrusted"
        source_id: Source identifier for untrusted content

    Returns:
        (allowed, reason)
    """
    # Normalize tool name to handle MCP prefixes
    normalized_tool = normalize_tool_name(tool_name)

    if origin == "user" or origin == "system":
        return True, "Trusted origin"

    if origin == "untrusted":
        # Untrusted origin cannot call risky tools
        if normalized_tool in INTENT_REQUIRED_TOOLS:
            return False, f"Untrusted origin cannot call {normalized_tool}"

        # Log but allow for read-only tools
        if normalized_tool in INTENT_LOGGED_TOOLS:
            return True, "Untrusted origin, logged"

        return True, "Untrusted origin, allowed for this tool"

    return False, f"Unknown origin: {origin}"


def get_intent_status() -> Dict[str, Any]:
    """Get current intent system status."""
    stats = _intent_store.get_stats()
    current = get_current_intent()

    status = {
        "bypass_active": os.environ.get(INTENT_BYPASS_ENV, "").strip() == "1",
        "has_valid_intent": current is not None,
        **stats,
    }

    if current:
        status["current_token"] = {
            "token_id": current.token_id,
            "source": current.source,
            "expires_at": current.expires_at,
            "scope": current.scope,
        }

    return status


def revoke_all_intents() -> int:
    """Revoke all intent tokens. Returns count revoked."""
    return _intent_store.revoke_all()


# ============================================================
# SESSION CONTEXT TRACKING
# ============================================================

@dataclass
class SessionContext:
    """
    Tracks session state for origin determination.

    Used to automatically set _origin based on "last tool
    output was untrusted" state.

    CRITICAL: Intent is tied to user turns, not tool calls.
    The model cannot self-authorize by calling tools.
    """
    last_tool_output_untrusted: bool = False
    last_untrusted_source_id: Optional[str] = None
    last_untrusted_domain: Optional[str] = None
    untrusted_content_hashes: Set[str] = field(default_factory=set)

    # User turn tracking - intent is scoped to user turns
    current_user_turn_id: Optional[str] = None
    current_user_turn_hash: Optional[str] = None
    intent_issued_for_turn: bool = False

    def mark_untrusted_output(
        self,
        source_id: str,
        domain: Optional[str] = None,
        content_hash: Optional[str] = None,
    ):
        """Mark that the last tool output was untrusted."""
        self.last_tool_output_untrusted = True
        self.last_untrusted_source_id = source_id
        self.last_untrusted_domain = domain
        if content_hash:
            self.untrusted_content_hashes.add(content_hash)

    def clear_untrusted(self):
        """Clear untrusted state (on new user message)."""
        self.last_tool_output_untrusted = False
        self.last_untrusted_source_id = None
        self.last_untrusted_domain = None

    def start_new_user_turn(self, message_hash: Optional[str] = None) -> str:
        """
        Start a new user turn. Called when user message arrives.

        Returns the turn_id for this turn.
        """
        # Generate turn ID with proper entropy (64 bits)
        now = utc_now()
        random_suffix = secrets.token_hex(8)  # 16 hex chars = 64 bits
        turn_id = f"turn_{now.strftime('%Y%m%d_%H%M%S')}_{random_suffix}"

        self.current_user_turn_id = turn_id
        self.current_user_turn_hash = message_hash
        self.intent_issued_for_turn = False
        self.clear_untrusted()

        return turn_id

    def get_inferred_origin(self) -> str:
        """Infer origin based on session state."""
        if self.last_tool_output_untrusted:
            return "untrusted"
        return "user"


# Global session context
_session_context = SessionContext()


def get_session_context() -> SessionContext:
    """Get the global session context."""
    return _session_context


def mark_untrusted_output(
    source_id: str,
    domain: Optional[str] = None,
    content_hash: Optional[str] = None,
):
    """Mark last tool output as untrusted."""
    _session_context.mark_untrusted_output(source_id, domain, content_hash)


def on_user_message(message_content: Optional[str] = None) -> IntentToken:
    """
    Called when a new user message is received.

    This is the ONLY place where intent should be minted.
    Do NOT call this from tool execution paths.

    Args:
        message_content: The user message content (used for scoping)

    Returns:
        Fresh IntentToken for this user turn
    """
    # Compute message hash for scoping
    message_hash = None
    if message_content:
        message_hash = hashlib.sha256(message_content.encode()).hexdigest()[:16]

    # Start new user turn
    turn_id = _session_context.start_new_user_turn(message_hash)

    # Issue intent for this turn, bound to turn_id
    token = issue_intent(source="user", message_hash=message_hash, turn_id=turn_id)
    _session_context.intent_issued_for_turn = True

    # Log intent issuance (Layer 5 audit)
    if AUDIT_AVAILABLE:
        event = build_intent_event(
            event_type=EventType.INTENT_ISSUED,
            token_id=token.token_id,
            reason=f"Intent issued for user turn {turn_id[:20]}...",
            severity=Severity.INFO,
        )
        append_event(event)

    return token


def ensure_intent_for_current_user_turn() -> Optional[IntentToken]:
    """
    Ensure intent exists for the current user turn (idempotent).

    Call this from tool execution paths instead of on_user_message().
    It will NOT mint new intent - only returns existing valid intent
    if one exists for the current turn.

    Returns:
        Current valid intent if one exists, None otherwise
    """
    # If session has untrusted output, no intent can be provided
    if _session_context.last_tool_output_untrusted:
        return None

    # If no user turn has started, no intent available
    if not _session_context.current_user_turn_id:
        return None

    # Return current valid intent (already issued for this turn)
    return get_current_intent()
