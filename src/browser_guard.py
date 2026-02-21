"""
Browser Guard - Layer 4 Security
=================================
Sandboxes browser automation to prevent:
- Credential theft (fresh profiles, no password manager)
- File system escape (workspace-scoped downloads)
- Data exfiltration (network allowlist)
- State persistence (ephemeral sessions)

Design principle: Treat the browser like a raccoon with lockpicks.
It WILL try to escape. Make the cage strong enough that it can't.

Integration:
- All browser automation MUST go through BrowserSandbox
- Content fetched is tagged as UNTRUSTED (for Layer 6)
- Downloads restricted to workspace-scoped output directory
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import subprocess
import re

from time_utils import utc_now_iso


# ============================================================
# CONFIGURATION
# ============================================================

# Environment variables
BROWSER_SANDBOX_ENV = "DURO_BROWSER_SANDBOX"  # "strict", "standard", "disabled"
BROWSER_ALLOWLIST_ENV = "DURO_BROWSER_ALLOWLIST"  # Comma-separated domains

# Default sandbox mode
DEFAULT_SANDBOX_MODE = "strict"

# Audit log
AUDIT_DIR = Path.home() / ".agent" / "memory" / "audit"
BROWSER_AUDIT_FILE = AUDIT_DIR / "browser_sessions.jsonl"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

# Ephemeral profile directory (cleaned up after each session)
EPHEMERAL_PROFILES_DIR = Path.home() / ".agent" / "tmp" / "browser_profiles"
EPHEMERAL_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

# Download directory (workspace-scoped)
BROWSER_DOWNLOADS_DIR = Path.home() / ".agent" / "tmp" / "browser_downloads"
BROWSER_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SANDBOX CONFIGURATION
# ============================================================

@dataclass
class BrowserSandboxConfig:
    """Configuration for browser sandbox."""

    # Sandbox mode: "strict", "standard", "disabled"
    mode: str = "strict"

    # Network allowlist (empty = allow all in standard mode)
    # In strict mode, only these domains can be accessed
    domain_allowlist: List[str] = field(default_factory=list)

    # Domain blocklist (always blocked, even in standard mode)
    domain_blocklist: List[str] = field(default_factory=lambda: [
        # Credential/auth endpoints that should never be accessed by automation
        "accounts.google.com",
        "login.microsoftonline.com",
        "github.com/login",
        "auth0.com",
        # Banking/financial
        "*.bank.com",
        "paypal.com",
        "stripe.com/login",
    ])

    # File system restrictions
    downloads_dir: Path = field(default_factory=lambda: BROWSER_DOWNLOADS_DIR)
    max_download_size_mb: int = 100
    allowed_download_extensions: Set[str] = field(default_factory=lambda: {
        ".pdf", ".txt", ".csv", ".json", ".xml", ".html", ".htm",
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
        ".md", ".rst", ".yaml", ".yml",
    })

    # Browser restrictions
    disable_javascript: bool = False  # Only in paranoid mode
    disable_images: bool = False
    disable_cookies: bool = False  # Fresh profile handles this
    disable_local_storage: bool = True  # Strict mode
    disable_clipboard: bool = True  # Prevent clipboard exfiltration
    disable_password_manager: bool = True  # Always
    disable_autofill: bool = True  # Always

    # Session limits
    max_session_duration_seconds: int = 300  # 5 minutes
    max_pages_per_session: int = 50
    max_requests_per_session: int = 500

    # Content tagging
    tag_content_as_untrusted: bool = True  # For Layer 6


def get_sandbox_config() -> BrowserSandboxConfig:
    """Get sandbox configuration from environment or defaults."""
    mode = os.environ.get(BROWSER_SANDBOX_ENV, DEFAULT_SANDBOX_MODE).lower()

    # Parse domain allowlist from env
    allowlist_str = os.environ.get(BROWSER_ALLOWLIST_ENV, "")
    domain_allowlist = [d.strip() for d in allowlist_str.split(",") if d.strip()]

    config = BrowserSandboxConfig(mode=mode)

    if domain_allowlist:
        config.domain_allowlist = domain_allowlist

    # Mode-specific adjustments
    if mode == "disabled":
        # WARNING: No sandbox - only for testing
        config.disable_local_storage = False
        config.disable_clipboard = False
        config.tag_content_as_untrusted = False
    elif mode == "standard":
        # Reasonable defaults
        config.disable_local_storage = False
    elif mode == "strict":
        # Maximum paranoia
        config.max_session_duration_seconds = 120  # 2 minutes
        config.max_pages_per_session = 20

    return config


# ============================================================
# DOMAIN VALIDATION
# ============================================================

def normalize_domain(url_or_domain: str) -> str:
    """Extract and normalize domain from URL or domain string."""
    # Remove protocol
    domain = url_or_domain.lower()
    for prefix in ["https://", "http://", "www."]:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]

    # Remove path
    domain = domain.split("/")[0]

    # Remove port
    domain = domain.split(":")[0]

    return domain


def matches_domain_pattern(domain: str, pattern: str) -> bool:
    """Check if domain matches a pattern (supports wildcards)."""
    domain = normalize_domain(domain)
    pattern = normalize_domain(pattern)

    if pattern.startswith("*."):
        # Wildcard subdomain match
        suffix = pattern[2:]
        return domain == suffix or domain.endswith("." + suffix)
    else:
        # Exact match
        return domain == pattern


def check_domain_allowed(url: str, config: BrowserSandboxConfig) -> Tuple[bool, str]:
    """
    Check if a domain is allowed by the sandbox configuration.

    Returns (allowed, reason)
    """
    domain = normalize_domain(url)

    # Check blocklist first (always applies)
    for blocked in config.domain_blocklist:
        if matches_domain_pattern(domain, blocked):
            return False, f"Domain is blocklisted: {blocked}"

    # In disabled mode, allow all (after blocklist)
    if config.mode == "disabled":
        return True, "Sandbox disabled"

    # In strict mode with allowlist, must be in allowlist
    if config.mode == "strict" and config.domain_allowlist:
        for allowed in config.domain_allowlist:
            if matches_domain_pattern(domain, allowed):
                return True, f"Domain in allowlist: {allowed}"
        return False, f"Domain not in strict allowlist: {domain}"

    # Standard mode or strict without allowlist - allow
    return True, "Domain allowed"


# ============================================================
# EPHEMERAL PROFILE MANAGEMENT
# ============================================================

@dataclass
class BrowserProfile:
    """Ephemeral browser profile for sandboxed sessions."""
    profile_id: str
    profile_dir: Path
    created_at: str
    config: BrowserSandboxConfig

    # Session stats
    pages_visited: int = 0
    requests_made: int = 0
    downloads: List[str] = field(default_factory=list)

    # Content collected (tagged as UNTRUSTED)
    untrusted_content: List[Dict[str, Any]] = field(default_factory=list)


def create_ephemeral_profile(config: BrowserSandboxConfig = None) -> BrowserProfile:
    """
    Create a fresh ephemeral browser profile.

    The profile directory is created with restricted permissions
    and will be deleted after the session.
    """
    if config is None:
        config = get_sandbox_config()

    # Generate unique profile ID
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    random_suffix = hashlib.sha256(os.urandom(16)).hexdigest()[:8]
    profile_id = f"profile_{timestamp}_{random_suffix}"

    # Create profile directory
    profile_dir = EPHEMERAL_PROFILES_DIR / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (profile_dir / "downloads").mkdir(exist_ok=True)
    (profile_dir / "cache").mkdir(exist_ok=True)

    # Write profile config (for debugging/audit)
    config_file = profile_dir / "sandbox_config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump({
            "mode": config.mode,
            "domain_allowlist": config.domain_allowlist,
            "max_session_duration_seconds": config.max_session_duration_seconds,
            "max_pages_per_session": config.max_pages_per_session,
            "disable_clipboard": config.disable_clipboard,
            "disable_password_manager": config.disable_password_manager,
        }, f, indent=2)

    return BrowserProfile(
        profile_id=profile_id,
        profile_dir=profile_dir,
        created_at=utc_now_iso(),
        config=config,
    )


def cleanup_profile(profile: BrowserProfile) -> bool:
    """
    Clean up ephemeral profile after session.

    Removes all profile data to ensure no credentials or
    session state persists between runs.
    """
    try:
        if profile.profile_dir.exists():
            shutil.rmtree(profile.profile_dir)
        return True
    except Exception as e:
        print(f"[WARN] Failed to cleanup browser profile: {e}", file=sys.stderr)
        return False


def cleanup_old_profiles(max_age_hours: int = 1):
    """Clean up old profiles that weren't properly deleted."""
    try:
        now = datetime.now(timezone.utc)
        for profile_dir in EPHEMERAL_PROFILES_DIR.iterdir():
            if profile_dir.is_dir():
                # Check age based on directory name timestamp
                try:
                    dir_time = datetime.strptime(
                        profile_dir.name.split("_")[1] + "_" + profile_dir.name.split("_")[2],
                        "%Y%m%d_%H%M%S"
                    ).replace(tzinfo=timezone.utc)
                    age_hours = (now - dir_time).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        shutil.rmtree(profile_dir)
                        print(f"[INFO] Cleaned up old browser profile: {profile_dir.name}", file=sys.stderr)
                except (ValueError, IndexError):
                    # Can't parse timestamp, delete if old enough by mtime
                    mtime = datetime.fromtimestamp(profile_dir.stat().st_mtime, timezone.utc)
                    if (now - mtime).total_seconds() / 3600 > max_age_hours:
                        shutil.rmtree(profile_dir)
    except Exception as e:
        print(f"[WARN] Failed to cleanup old profiles: {e}", file=sys.stderr)


# ============================================================
# DOWNLOAD VALIDATION
# ============================================================

def validate_download(
    filename: str,
    size_bytes: int,
    config: BrowserSandboxConfig
) -> Tuple[bool, str]:
    """
    Validate if a download should be allowed.

    Returns (allowed, reason)
    """
    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in config.allowed_download_extensions:
        return False, f"File extension not allowed: {ext}"

    # Check size
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > config.max_download_size_mb:
        return False, f"File too large: {size_mb:.1f}MB > {config.max_download_size_mb}MB limit"

    # Check filename for suspicious patterns
    suspicious_patterns = [
        r"\.exe$", r"\.dll$", r"\.bat$", r"\.cmd$", r"\.ps1$",
        r"\.vbs$", r"\.js$", r"\.msi$", r"\.scr$",
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            return False, f"Suspicious file type blocked: {filename}"

    return True, "Download allowed"


def get_safe_download_path(
    filename: str,
    profile: BrowserProfile
) -> Path:
    """
    Get a safe path for downloading a file.

    Returns path within the profile's downloads directory.
    """
    # Sanitize filename
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
    safe_name = safe_name[:200]  # Limit length

    # Ensure uniqueness
    base = Path(safe_name).stem
    ext = Path(safe_name).suffix
    target = profile.profile_dir / "downloads" / safe_name

    counter = 1
    while target.exists():
        target = profile.profile_dir / "downloads" / f"{base}_{counter}{ext}"
        counter += 1

    return target


# ============================================================
# CONTENT TAGGING (for Layer 6)
# ============================================================

@dataclass
class UntrustedContent:
    """Content fetched from browser, tagged as untrusted."""
    source_url: str
    content_type: str  # "html", "text", "json", "screenshot"
    content_hash: str
    fetched_at: str
    profile_id: str

    # The actual content (may be redacted for audit)
    content: str = ""

    # Metadata
    http_status: int = 200
    content_length: int = 0

    def to_audit_record(self) -> Dict[str, Any]:
        """Create audit record (no actual content)."""
        return {
            "ts": self.fetched_at,
            "event": "browser_content_fetched",
            "source_url": self.source_url,
            "content_type": self.content_type,
            "content_hash": self.content_hash,
            "content_length": self.content_length,
            "http_status": self.http_status,
            "profile_id": self.profile_id,
            "tag": "UNTRUSTED",
        }


def tag_as_untrusted(
    content: str,
    source_url: str,
    content_type: str,
    profile: BrowserProfile,
    http_status: int = 200,
) -> UntrustedContent:
    """
    Tag content fetched from browser as UNTRUSTED.

    This tagging is used by Layer 6 (prompt injection defense)
    to ensure browser content is treated as data, not instructions.
    """
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    tagged = UntrustedContent(
        source_url=source_url,
        content_type=content_type,
        content_hash=content_hash,
        fetched_at=utc_now_iso(),
        profile_id=profile.profile_id,
        content=content,
        http_status=http_status,
        content_length=len(content),
    )

    # Add to profile's untrusted content list
    profile.untrusted_content.append(tagged.to_audit_record())

    return tagged


# ============================================================
# SESSION MANAGEMENT
# ============================================================

@dataclass
class BrowserSession:
    """Active browser session within sandbox."""
    session_id: str
    profile: BrowserProfile
    started_at: str
    config: BrowserSandboxConfig

    # State
    is_active: bool = True
    urls_visited: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def check_limits(self) -> Tuple[bool, str]:
        """Check if session has exceeded limits."""
        # Check page count
        if self.profile.pages_visited >= self.config.max_pages_per_session:
            return False, f"Page limit exceeded: {self.profile.pages_visited}"

        # Check request count
        if self.profile.requests_made >= self.config.max_requests_per_session:
            return False, f"Request limit exceeded: {self.profile.requests_made}"

        # Check session duration
        start = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        if elapsed > self.config.max_session_duration_seconds:
            return False, f"Session timeout: {elapsed:.0f}s"

        return True, "Within limits"

    def record_page_visit(self, url: str):
        """Record a page visit."""
        self.profile.pages_visited += 1
        self.urls_visited.append(url)

    def record_request(self):
        """Record a network request."""
        self.profile.requests_made += 1

    def to_audit_record(self) -> Dict[str, Any]:
        """Create audit record for session."""
        return {
            "ts": utc_now_iso(),
            "event": "browser_session",
            "session_id": self.session_id,
            "profile_id": self.profile.profile_id,
            "started_at": self.started_at,
            "mode": self.config.mode,
            "pages_visited": self.profile.pages_visited,
            "requests_made": self.profile.requests_made,
            "downloads": len(self.profile.downloads),
            "urls_visited": self.urls_visited[:10],  # First 10 only
            "errors": self.errors[:5],  # First 5 only
            "is_active": self.is_active,
        }


def create_session(config: BrowserSandboxConfig = None) -> BrowserSession:
    """Create a new sandboxed browser session."""
    if config is None:
        config = get_sandbox_config()

    # Clean up old profiles first
    cleanup_old_profiles()

    # Create ephemeral profile
    profile = create_ephemeral_profile(config)

    # Generate session ID
    session_id = f"session_{profile.profile_id}"

    session = BrowserSession(
        session_id=session_id,
        profile=profile,
        started_at=utc_now_iso(),
        config=config,
    )

    # Log session start
    _log_browser_event({
        "ts": session.started_at,
        "event": "session_started",
        "session_id": session_id,
        "profile_id": profile.profile_id,
        "mode": config.mode,
    })

    return session


def end_session(session: BrowserSession) -> Dict[str, Any]:
    """End a browser session and clean up."""
    session.is_active = False

    # Create final audit record
    audit_record = session.to_audit_record()
    audit_record["event"] = "session_ended"

    # Log session end
    _log_browser_event(audit_record)

    # Clean up profile
    cleanup_profile(session.profile)

    return audit_record


def _log_browser_event(event: Dict[str, Any]):
    """Log browser event to audit file."""
    try:
        with open(BROWSER_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        print(f"[WARN] Failed to log browser event: {e}", file=sys.stderr)


# ============================================================
# BROWSER LAUNCH ARGUMENTS
# ============================================================

def get_chromium_sandbox_args(
    profile: BrowserProfile,
    config: BrowserSandboxConfig
) -> List[str]:
    """
    Get Chromium command-line arguments for sandboxed execution.

    These args work with Chrome, Chromium, Edge, and Playwright.
    """
    args = [
        # Profile isolation
        f"--user-data-dir={profile.profile_dir}",

        # Disable features that could leak data
        "--disable-sync",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-component-extensions-with-background-pages",
        "--disable-background-timer-throttling",

        # Disable password/autofill (always)
        "--disable-save-password-bubble",
        "--password-store=basic",
        "--disable-autofill-keyboard-accessory-view",

        # Security
        "--disable-client-side-phishing-detection",
        "--safebrowsing-disable-auto-update",

        # Downloads
        f"--download-default-directory={profile.profile_dir / 'downloads'}",

        # Performance/stability
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
    ]

    if config.disable_clipboard:
        args.append("--disable-clipboard-read")
        args.append("--disable-clipboard-write")

    if config.disable_local_storage:
        args.append("--disable-local-storage")

    if config.disable_javascript:
        args.append("--disable-javascript")

    if config.disable_images:
        args.append("--disable-images")

    return args


def get_playwright_context_options(
    profile: BrowserProfile,
    config: BrowserSandboxConfig
) -> Dict[str, Any]:
    """
    Get Playwright browser context options for sandboxed execution.
    """
    options = {
        # Use ephemeral profile
        "user_data_dir": str(profile.profile_dir),

        # Disable persistence
        "accept_downloads": True,
        "downloads_path": str(profile.profile_dir / "downloads"),

        # Viewport (consistent for screenshots)
        "viewport": {"width": 1280, "height": 720},

        # Disable features
        "java_script_enabled": not config.disable_javascript,
        "bypass_csp": False,
        "ignore_https_errors": False,

        # Permissions (deny all by default)
        "permissions": [],

        # Geolocation (disabled)
        "geolocation": None,

        # No service workers
        "service_workers": "block",
    }

    return options


# ============================================================
# POLICY GATE INTEGRATION
# ============================================================

def check_browser_policy(
    url: str,
    action: str,  # "navigate", "download", "screenshot", etc.
    config: BrowserSandboxConfig = None
) -> Tuple[bool, str]:
    """
    Check if a browser action is allowed by policy.

    Returns (allowed, reason)
    """
    if config is None:
        config = get_sandbox_config()

    # Check domain allowlist/blocklist
    domain_allowed, domain_reason = check_domain_allowed(url, config)
    if not domain_allowed:
        return False, domain_reason

    # Action-specific checks
    if action == "download":
        # Downloads require additional validation when the file is received
        pass

    return True, "Browser action allowed"


def get_browser_status() -> Dict[str, Any]:
    """Get current browser sandbox status."""
    config = get_sandbox_config()

    # Count active profiles
    active_profiles = 0
    if EPHEMERAL_PROFILES_DIR.exists():
        active_profiles = len(list(EPHEMERAL_PROFILES_DIR.iterdir()))

    # Get recent sessions from audit log
    recent_sessions = []
    if BROWSER_AUDIT_FILE.exists():
        try:
            with open(BROWSER_AUDIT_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()[-10:]  # Last 10 events
            for line in lines:
                try:
                    event = json.loads(line)
                    if event.get("event") in ("session_started", "session_ended"):
                        recent_sessions.append(event)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    return {
        "mode": config.mode,
        "domain_allowlist": config.domain_allowlist,
        "domain_blocklist_count": len(config.domain_blocklist),
        "active_profiles": active_profiles,
        "downloads_dir": str(config.downloads_dir),
        "max_download_size_mb": config.max_download_size_mb,
        "max_session_duration_seconds": config.max_session_duration_seconds,
        "max_pages_per_session": config.max_pages_per_session,
        "disable_clipboard": config.disable_clipboard,
        "disable_password_manager": config.disable_password_manager,
        "tag_content_as_untrusted": config.tag_content_as_untrusted,
        "recent_sessions": recent_sessions[-5:],
    }
