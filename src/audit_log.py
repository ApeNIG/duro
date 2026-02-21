"""
Audit Log - Layer 5 Security
=============================

The court transcript. One log. One schema. Every security-relevant event.
Tamper-evident via hash chain, optionally HMAC-signed.

Design principles:
- SINGLE SOURCE OF TRUTH: All security events flow through here
- TAMPER-EVIDENT: Hash chain links each event to the previous
- OPTIONALLY SIGNED: HMAC prevents attackers from recomputing hashes
- CANONICAL: Stable JSON serialization for reproducible hashes
- CONCURRENT-SAFE: File locking prevents corruption

Events recorded:
- Gate decisions (allow/deny/need_approval)
- Secrets detection (pre and post execution)
- Workspace violations (path traversal, denylist hits)
- Browser sandbox events (domain blocks, session lifecycle)
- Output redaction events

Schema version: 1
"""

import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import threading

# Cross-platform file locking
# Windows: Use a separate lockfile for robust cross-process locking
# Unix: Use fcntl.flock on the actual file
LOCKFILE_PATH = None  # Set after AUDIT_DIR is defined

if sys.platform == "win32":
    import msvcrt
    import time

    def _get_lockfile_path():
        """Get lockfile path (deferred until AUDIT_DIR exists)."""
        global LOCKFILE_PATH
        if LOCKFILE_PATH is None:
            LOCKFILE_PATH = Path.home() / ".agent" / "memory" / "audit" / ".audit.lock"
        return LOCKFILE_PATH

    def _lock_file(f):
        """Acquire cross-process lock via lockfile."""
        lockfile = _get_lockfile_path()
        lockfile.parent.mkdir(parents=True, exist_ok=True)

        # Try to acquire exclusive lock on lockfile
        max_retries = 50
        retry_delay = 0.1
        for attempt in range(max_retries):
            try:
                # Open lockfile exclusively (fails if another process has it)
                lock_fd = os.open(str(lockfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(lock_fd, str(os.getpid()).encode())
                os.close(lock_fd)
                # Store lockfile handle on the file object for cleanup
                f._audit_lockfile = lockfile
                return
            except FileExistsError:
                # Lockfile exists, check if stale
                try:
                    mtime = lockfile.stat().st_mtime
                    if time.time() - mtime > 30:  # Stale after 30 seconds
                        lockfile.unlink()
                        continue
                except (FileNotFoundError, OSError):
                    continue
                time.sleep(retry_delay)
            except OSError as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise OSError(f"Failed to acquire audit lock after {max_retries} attempts: {e}")

        raise OSError(f"Failed to acquire audit lock after {max_retries} attempts")

    def _unlock_file(f):
        """Release cross-process lock by removing lockfile."""
        try:
            lockfile = getattr(f, '_audit_lockfile', None)
            if lockfile and lockfile.exists():
                lockfile.unlink()
        except Exception:
            pass  # Best effort cleanup
else:
    import fcntl
    def _lock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    def _unlock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

from time_utils import utc_now, utc_now_iso


# ============================================================
# CONFIGURATION
# ============================================================

# Audit log location
AUDIT_DIR = Path.home() / ".agent" / "memory" / "audit"
UNIFIED_AUDIT_FILE = AUDIT_DIR / "security_audit.jsonl"
AUDIT_HEAD_FILE = AUDIT_DIR / "audit_head.json"

# Rotation settings
MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
ROTATE_DAILY = True

# HMAC key (from environment)
HMAC_KEY_ENV = "DURO_AUDIT_HMAC_KEY"

# Genesis constant
GENESIS_HASH = "GENESIS"

# Schema version
SCHEMA_VERSION = 1

# Thread lock for concurrent appends
_append_lock = threading.Lock()

# Ensure audit directory exists
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# EVENT TYPES
# ============================================================

class EventType:
    """Standard event types for the audit log."""
    # Gate events
    GATE_DECISION = "gate.decision"
    GATE_BYPASS = "gate.bypass"
    GATE_BREAKGLASS = "gate.breakglass"

    # Secrets events
    SECRETS_BLOCKED = "secrets.blocked"
    SECRETS_DETECTED = "secrets.detected"
    SECRETS_OUTPUT_REDACTED = "secrets.output_redacted"

    # Workspace events
    WORKSPACE_VIOLATION = "workspace.violation"
    WORKSPACE_DENYLIST = "workspace.denylist"
    WORKSPACE_ADD = "workspace.add"
    WORKSPACE_TRAVERSAL = "workspace.traversal"

    # Browser events
    BROWSER_SESSION_START = "browser.session_start"
    BROWSER_SESSION_END = "browser.session_end"
    BROWSER_DOMAIN_BLOCKED = "browser.domain_blocked"
    BROWSER_DOWNLOAD_BLOCKED = "browser.download_blocked"

    # Intent events (Layer 6)
    INTENT_ISSUED = "intent.issued"
    INTENT_DENIED = "intent.denied"
    INTENT_CONSUMED = "intent.consumed"
    INTENT_EXPIRED = "intent.expired"

    # Prompt injection events (Layer 6)
    INJECTION_DETECTED = "injection.detected"
    INJECTION_BLOCKED = "injection.blocked"
    UNTRUSTED_CONTENT_RECEIVED = "untrusted.content_received"
    UNTRUSTED_CONTENT_WRAPPED = "untrusted.content_wrapped"

    # Approval events
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_CONSUMED = "approval.consumed"
    APPROVAL_EXPIRED = "approval.expired"

    # System events
    AUDIT_ROTATION = "audit.rotation"
    AUDIT_VERIFY = "audit.verify"


class Severity:
    """Event severity levels."""
    INFO = "info"
    WARN = "warn"
    HIGH = "high"
    CRITICAL = "critical"


class ActorKind:
    """Actor types."""
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


# ============================================================
# UNIFIED EVENT SCHEMA
# ============================================================

@dataclass
class AuditActor:
    """Actor performing the action."""
    kind: str = "agent"  # agent, user, system
    id: str = "duro"


@dataclass
class ChainInfo:
    """Hash chain information for tamper evidence."""
    prev: str = ""
    hash: str = ""
    sig: Optional[str] = None  # HMAC signature if key available


@dataclass
class AuditEvent:
    """
    Unified audit event schema.

    All security-relevant events conform to this schema.
    """
    # Header
    v: int = SCHEMA_VERSION
    ts: str = field(default_factory=utc_now_iso)
    event_id: str = ""
    event_type: str = ""
    severity: str = Severity.INFO
    actor: AuditActor = field(default_factory=AuditActor)

    # Tool context (if applicable)
    tool: Optional[str] = None
    domain: Optional[str] = None
    risk: Optional[str] = None

    # Decision (for gate events)
    decision: Optional[str] = None
    action_needed: Optional[str] = None
    reason: Optional[str] = None

    # Action identification
    action_id: Optional[str] = None
    args_hash: Optional[str] = None
    args_preview: Optional[Dict[str, Any]] = None

    # Output tracking
    output_hash: Optional[str] = None
    output_redacted: Optional[bool] = None

    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None

    # Hash chain (filled by append_event)
    chain: ChainInfo = field(default_factory=ChainInfo)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        d = {}
        for key, value in asdict(self).items():
            if value is not None:
                if isinstance(value, dict):
                    # Handle nested dataclasses
                    d[key] = value
                else:
                    d[key] = value
        return d

    def to_canonical_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for hash computation.

        Excludes chain.hash and chain.sig (which are computed from this).
        """
        d = self.to_dict()

        # Remove fields that are computed from the payload
        if "chain" in d:
            chain = d["chain"].copy()
            chain.pop("hash", None)
            chain.pop("sig", None)
            if chain:  # Only keep if there's still content
                d["chain"] = chain
            else:
                d.pop("chain", None)

        return d


# ============================================================
# EVENT ID GENERATION
# ============================================================

def generate_event_id() -> str:
    """Generate a unique event ID."""
    now = utc_now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    random_suffix = hashlib.sha256(os.urandom(8)).hexdigest()[:4]
    return f"evt_{timestamp}_{random_suffix}"


# ============================================================
# CANONICAL JSON
# ============================================================

def canonical_json(data: Dict[str, Any]) -> str:
    """
    Convert to canonical JSON for reproducible hashing.

    Rules:
    - Sorted keys
    - No whitespace
    - UTF-8 encoding
    """
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compute_payload_hash(event: AuditEvent) -> str:
    """Compute SHA-256 hash of event payload."""
    canonical = canonical_json(event.to_canonical_dict())
    return "sha256:" + hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# ============================================================
# HASH CHAIN
# ============================================================

def get_hmac_key() -> Optional[bytes]:
    """Get HMAC key from environment."""
    key_str = os.environ.get(HMAC_KEY_ENV, "").strip()
    if key_str:
        return key_str.encode('utf-8')
    return None


def compute_chain_hash(prev_hash: str, payload_hash: str) -> str:
    """Compute chain hash from previous hash and payload hash."""
    combined = f"{prev_hash}:{payload_hash}"
    return "sha256:" + hashlib.sha256(combined.encode('utf-8')).hexdigest()


def compute_hmac_signature(chain_hash: str, hmac_key: bytes) -> str:
    """Compute HMAC-SHA256 signature of chain hash."""
    sig = hmac.new(hmac_key, chain_hash.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"hmac-sha256:{sig}"


def compute_chain(event: AuditEvent, prev_hash: str) -> Tuple[str, Optional[str]]:
    """
    Compute chain hash and optional signature.

    Returns (chain_hash, signature or None)
    """
    payload_hash = compute_payload_hash(event)
    chain_hash = compute_chain_hash(prev_hash, payload_hash)

    hmac_key = get_hmac_key()
    sig = None
    if hmac_key:
        sig = compute_hmac_signature(chain_hash, hmac_key)

    return chain_hash, sig


# ============================================================
# HEAD MANAGEMENT
# ============================================================

def get_head() -> Tuple[str, str]:
    """
    Get the current head of the chain.

    Returns (prev_hash, last_event_id)
    """
    if not AUDIT_HEAD_FILE.exists():
        return GENESIS_HASH, ""

    try:
        with open(AUDIT_HEAD_FILE, "r", encoding="utf-8") as f:
            head = json.load(f)
        return head.get("hash", GENESIS_HASH), head.get("event_id", "")
    except Exception:
        return GENESIS_HASH, ""


def update_head(chain_hash: str, event_id: str):
    """Update the head file with new chain state."""
    head = {
        "hash": chain_hash,
        "event_id": event_id,
        "updated_at": utc_now_iso(),
    }
    with open(AUDIT_HEAD_FILE, "w", encoding="utf-8") as f:
        json.dump(head, f, indent=2)


# ============================================================
# LOG ROTATION
# ============================================================

def should_rotate() -> bool:
    """Check if the log file should be rotated."""
    if not UNIFIED_AUDIT_FILE.exists():
        return False

    # Size-based rotation
    if UNIFIED_AUDIT_FILE.stat().st_size > MAX_LOG_SIZE_BYTES:
        return True

    # Daily rotation
    if ROTATE_DAILY:
        mtime = datetime.fromtimestamp(UNIFIED_AUDIT_FILE.stat().st_mtime, timezone.utc)
        now = utc_now()
        if mtime.date() < now.date():
            return True

    return False


def rotate_log():
    """Rotate the log file, preserving chain continuity."""
    if not UNIFIED_AUDIT_FILE.exists():
        return

    # Generate archive filename
    timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"security_audit_{timestamp}.jsonl"
    archive_path = AUDIT_DIR / archive_name

    # Move current log to archive
    UNIFIED_AUDIT_FILE.rename(archive_path)

    # Get current head for continuity
    prev_hash, last_event_id = get_head()

    # Log rotation event (will be first in new file)
    rotation_event = AuditEvent(
        event_type=EventType.AUDIT_ROTATION,
        severity=Severity.INFO,
        actor=AuditActor(kind=ActorKind.SYSTEM, id="audit"),
        reason=f"Rotated from {archive_name}",
        metadata={
            "archived_file": archive_name,
            "previous_event_id": last_event_id,
            "continuity_hash": prev_hash,
        },
        tags=["audit", "rotation"],
    )

    # This will create the new file with the rotation event
    # The chain continues from the previous head
    _append_event_internal(rotation_event, prev_hash)


# ============================================================
# APPEND EVENT
# ============================================================

def _append_event_internal(event: AuditEvent, prev_hash: str) -> str:
    """Internal append without lock (called by rotate_log)."""
    # Generate event ID if not set
    if not event.event_id:
        event.event_id = generate_event_id()

    # Set prev hash
    event.chain.prev = prev_hash

    # Compute chain hash and signature
    chain_hash, sig = compute_chain(event, prev_hash)
    event.chain.hash = chain_hash
    event.chain.sig = sig

    # Append to log file
    with open(UNIFIED_AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    # Update head
    update_head(chain_hash, event.event_id)

    return event.event_id


def append_event(event: AuditEvent) -> str:
    """
    Append an event to the unified audit log.

    Thread-safe with file locking.

    Returns the event_id.
    """
    with _append_lock:
        # Check rotation
        if should_rotate():
            rotate_log()

        # Get current head
        prev_hash, _ = get_head()

        return _append_event_internal(event, prev_hash)


# ============================================================
# QUERY LOG
# ============================================================

def query_log(
    limit: int = 100,
    event_type: Optional[str] = None,
    tool: Optional[str] = None,
    decision: Optional[str] = None,
    severity: Optional[str] = None,
    since: Optional[str] = None,
    tags: Optional[List[str]] = None,
    include_archives: bool = False,
) -> List[Dict[str, Any]]:
    """
    Query the audit log with filters.

    Returns events newest first.
    """
    events = []

    # Collect log files to search
    log_files = []
    if UNIFIED_AUDIT_FILE.exists():
        log_files.append(UNIFIED_AUDIT_FILE)

    if include_archives:
        for archive in sorted(AUDIT_DIR.glob("security_audit_*.jsonl"), reverse=True):
            log_files.append(archive)

    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)

                        # Apply filters
                        if event_type and record.get("event_type") != event_type:
                            continue
                        if tool and record.get("tool") != tool:
                            continue
                        if decision and record.get("decision") != decision:
                            continue
                        if severity and record.get("severity") != severity:
                            continue
                        if since and record.get("ts", "") < since:
                            continue
                        if tags:
                            record_tags = record.get("tags", [])
                            if not any(t in record_tags for t in tags):
                                continue

                        events.append(record)

                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue

    # Sort by timestamp descending and limit
    events.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return events[:limit]


def get_recent_events(n: int = 20) -> List[Dict[str, Any]]:
    """Get the N most recent events (tail)."""
    return query_log(limit=n)


# ============================================================
# VERIFY LOG
# ============================================================

@dataclass
class VerifyResult:
    """Result of log verification."""
    valid: bool
    total_events: int
    verified_events: int
    first_broken_line: Optional[int] = None
    first_broken_event_id: Optional[str] = None
    error: Optional[str] = None
    signed: bool = False
    signature_valid: bool = False


def verify_log(path: Optional[Path] = None) -> VerifyResult:
    """
    Verify the hash chain integrity of the audit log.

    Returns a VerifyResult with details.
    """
    log_path = path or UNIFIED_AUDIT_FILE

    if not log_path.exists():
        return VerifyResult(
            valid=True,
            total_events=0,
            verified_events=0,
        )

    hmac_key = get_hmac_key()

    total = 0
    verified = 0
    prev_hash = GENESIS_HASH
    signed = False
    sig_valid = True

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                total += 1

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    return VerifyResult(
                        valid=False,
                        total_events=total,
                        verified_events=verified,
                        first_broken_line=line_num,
                        error=f"Invalid JSON at line {line_num}",
                    )

                chain = record.get("chain", {})
                stored_prev = chain.get("prev", "")
                stored_hash = chain.get("hash", "")
                stored_sig = chain.get("sig")

                # Check prev hash continuity
                if stored_prev != prev_hash:
                    return VerifyResult(
                        valid=False,
                        total_events=total,
                        verified_events=verified,
                        first_broken_line=line_num,
                        first_broken_event_id=record.get("event_id"),
                        error=f"Chain break at line {line_num}: expected prev={prev_hash[:20]}..., got {stored_prev[:20]}...",
                    )

                # Reconstruct event and compute expected hash
                # We need to rebuild the event without chain.hash and chain.sig
                event_dict = record.copy()
                if "chain" in event_dict:
                    event_dict["chain"] = {"prev": stored_prev}

                canonical = canonical_json(event_dict)
                payload_hash = "sha256:" + hashlib.sha256(canonical.encode('utf-8')).hexdigest()
                expected_hash = compute_chain_hash(prev_hash, payload_hash)

                if stored_hash != expected_hash:
                    return VerifyResult(
                        valid=False,
                        total_events=total,
                        verified_events=verified,
                        first_broken_line=line_num,
                        first_broken_event_id=record.get("event_id"),
                        error=f"Hash mismatch at line {line_num}",
                    )

                # Verify signature if present and we have the key
                if stored_sig:
                    signed = True
                    if hmac_key:
                        expected_sig = compute_hmac_signature(stored_hash, hmac_key)
                        if stored_sig != expected_sig:
                            sig_valid = False

                verified += 1
                prev_hash = stored_hash

        return VerifyResult(
            valid=True,
            total_events=total,
            verified_events=verified,
            signed=signed,
            signature_valid=sig_valid if signed else False,
        )

    except Exception as e:
        return VerifyResult(
            valid=False,
            total_events=total,
            verified_events=verified,
            error=str(e),
        )


# ============================================================
# AUDIT STATS
# ============================================================

def get_audit_stats() -> Dict[str, Any]:
    """Get audit log statistics."""
    stats = {
        "log_file": str(UNIFIED_AUDIT_FILE),
        "head_file": str(AUDIT_HEAD_FILE),
        "log_exists": UNIFIED_AUDIT_FILE.exists(),
        "log_size_bytes": 0,
        "total_events": 0,
        "by_event_type": {},
        "by_severity": {},
        "by_decision": {},
        "signed": False,
        "hmac_key_available": get_hmac_key() is not None,
    }

    if not UNIFIED_AUDIT_FILE.exists():
        return stats

    stats["log_size_bytes"] = UNIFIED_AUDIT_FILE.stat().st_size

    try:
        with open(UNIFIED_AUDIT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    stats["total_events"] += 1

                    event_type = record.get("event_type", "unknown")
                    stats["by_event_type"][event_type] = stats["by_event_type"].get(event_type, 0) + 1

                    severity = record.get("severity", "unknown")
                    stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1

                    decision = record.get("decision")
                    if decision:
                        stats["by_decision"][decision] = stats["by_decision"].get(decision, 0) + 1

                    if record.get("chain", {}).get("sig"):
                        stats["signed"] = True

                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return stats


# ============================================================
# CONVENIENCE BUILDERS
# ============================================================

def build_gate_event(
    tool_name: str,
    decision: str,
    reason: str,
    risk_level: str,
    domain: str,
    action_id: str,
    args_hash: str,
    args_preview: Optional[Dict[str, Any]] = None,
    action_needed: str = "none",
    bypass: bool = False,
    breakglass: bool = False,
    error: Optional[str] = None,
) -> AuditEvent:
    """Build a gate decision audit event."""
    # Determine event type and severity
    if breakglass:
        event_type = EventType.GATE_BREAKGLASS
        severity = Severity.HIGH
    elif bypass:
        event_type = EventType.GATE_BYPASS
        severity = Severity.INFO
    else:
        event_type = EventType.GATE_DECISION
        if decision == "DENY":
            severity = Severity.WARN
        elif decision == "NEED_APPROVAL":
            severity = Severity.WARN
        else:
            severity = Severity.INFO

    tags = ["policy-gate"]
    if error:
        tags.append("error")

    return AuditEvent(
        event_type=event_type,
        severity=severity,
        tool=tool_name,
        domain=domain,
        risk=risk_level,
        decision=decision,
        action_needed=action_needed,
        reason=reason,
        action_id=action_id,
        args_hash=args_hash,
        args_preview=args_preview,
        tags=tags,
        metadata={"error": error} if error else None,
    )


def build_secrets_event(
    event_type: str,
    tool_name: str,
    action: str,
    reason: str,
    match_count: int = 0,
    patterns: Optional[List[str]] = None,
    output_hash: Optional[str] = None,
    output_redacted: bool = False,
) -> AuditEvent:
    """Build a secrets detection audit event."""
    severity = Severity.WARN if event_type == EventType.SECRETS_BLOCKED else Severity.INFO

    return AuditEvent(
        event_type=event_type,
        severity=severity,
        tool=tool_name,
        reason=reason,
        output_hash=output_hash,
        output_redacted=output_redacted,
        tags=["secrets", action],
        metadata={
            "match_count": match_count,
            "patterns": patterns or [],
        },
    )


def build_workspace_event(
    event_type: str,
    path: str,
    reason: str,
    tool_name: Optional[str] = None,
    severity: str = Severity.WARN,
) -> AuditEvent:
    """Build a workspace violation audit event."""
    return AuditEvent(
        event_type=event_type,
        severity=severity,
        tool=tool_name,
        reason=reason,
        tags=["workspace"],
        metadata={"path": path},
    )


def build_browser_event(
    event_type: str,
    url: Optional[str] = None,
    session_id: Optional[str] = None,
    reason: Optional[str] = None,
    severity: str = Severity.INFO,
) -> AuditEvent:
    """Build a browser sandbox audit event."""
    metadata = {}
    if url:
        metadata["url"] = url
    if session_id:
        metadata["session_id"] = session_id

    return AuditEvent(
        event_type=event_type,
        severity=severity,
        reason=reason,
        tags=["browser"],
        metadata=metadata if metadata else None,
    )


def build_intent_event(
    event_type: str,
    tool_name: Optional[str] = None,
    token_id: Optional[str] = None,
    args_hash: Optional[str] = None,
    reason: Optional[str] = None,
    severity: str = Severity.INFO,
) -> AuditEvent:
    """Build an intent guard audit event (Layer 6)."""
    metadata = {}
    if token_id:
        # Truncate token_id for logging (don't leak full capability)
        metadata["token_id"] = token_id[:20] + "..." if len(token_id) > 20 else token_id
    if args_hash:
        metadata["args_hash"] = args_hash

    return AuditEvent(
        event_type=event_type,
        severity=severity,
        tool=tool_name,
        reason=reason,
        tags=["intent", "layer6"],
        metadata=metadata if metadata else None,
    )


def build_injection_event(
    event_type: str,
    source_id: str,
    domain: str,
    severity_detected: Optional[str] = None,
    patterns: Optional[List[str]] = None,
    content_hash: Optional[str] = None,
    reason: Optional[str] = None,
    severity: str = Severity.WARN,
) -> AuditEvent:
    """
    Build a prompt injection detection audit event (Layer 6).

    Note: Never log raw content - only metadata and hashes.
    """
    metadata = {
        "source_id": source_id,
        "domain": domain,
    }
    if severity_detected:
        metadata["severity_detected"] = severity_detected
    if patterns:
        metadata["patterns"] = patterns[:5]  # Limit for log size
    if content_hash:
        metadata["content_hash"] = content_hash

    # Severity escalation based on detection
    if severity_detected == "critical":
        severity = Severity.CRITICAL
    elif severity_detected == "high":
        severity = Severity.HIGH

    return AuditEvent(
        event_type=event_type,
        severity=severity,
        reason=reason,
        tags=["injection", "layer6", "untrusted"],
        metadata=metadata,
    )


def build_untrusted_content_event(
    event_type: str,
    source_id: str,
    domain: str,
    tool_name: str,
    content_hash: str,
    vault_stored: bool = False,
    severity: str = Severity.INFO,
) -> AuditEvent:
    """Build an untrusted content audit event (Layer 6)."""
    return AuditEvent(
        event_type=event_type,
        severity=severity,
        tool=tool_name,
        tags=["untrusted", "layer6"],
        metadata={
            "source_id": source_id,
            "domain": domain,
            "content_hash": content_hash,
            "vault_stored": vault_stored,
        },
    )
