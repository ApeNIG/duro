"""
Workspace Guard - Path Scoping and Traversal Protection
========================================================

Ensures all file operations stay within allowed workspaces.
Blocks path traversal attacks (.., symlinks, unicode tricks).

Layer 2 of security hardening roadmap.

Configuration:
- DURO_WORKSPACE env var: comma-separated allowed paths
- DURO_WORKSPACE_STRICT env var: if "1", block all paths outside workspace (default)
- Config file: ~/.agent/config/workspace.json

Path Validation:
1. Normalize path (resolve ., .., ~)
2. Resolve symlinks to real path
3. Check if real path is under an allowed workspace
4. Block unicode normalization attacks
"""

import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from time_utils import utc_now_iso


# === CONFIGURATION ===

# Environment variables
WORKSPACE_ENV = "DURO_WORKSPACE"
WORKSPACE_STRICT_ENV = "DURO_WORKSPACE_STRICT"

# Config file path
CONFIG_DIR = Path.home() / ".agent" / "config"
WORKSPACE_CONFIG_FILE = CONFIG_DIR / "workspace.json"

# Default workspaces (always allowed)
DEFAULT_WORKSPACES = [
    Path.home() / ".agent",  # Duro memory/config
]

# Strict mode by default (block all paths outside workspace)
DEFAULT_STRICT = True

# === CRITICAL PATH DENY LIST ===
# Paths that are NEVER allowed, even with approval (unless breakglass)
# These are system-critical paths that could compromise the machine
# On Windows, these are case-insensitive

def _get_deny_list() -> List[Path]:
    """
    Get platform-appropriate deny list.

    NOTE: This is an EXACT match list, not a prefix match.
    Only paths that are EXACTLY these or DIRECT children are denied.
    """
    deny_list = []

    if sys.platform == "win32":
        # Windows critical paths (NOT root - too broad)
        deny_list = [
            Path("C:/Windows"),
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
            Path("C:/ProgramData"),
            Path("C:/System Volume Information"),
            Path("C:/Recovery"),
            Path("C:/$Recycle.Bin"),
        ]

        # Also deny other users' home directories
        users_dir = Path("C:/Users")
        current_user = Path.home().name
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                if user_dir.is_dir() and user_dir.name.lower() != current_user.lower():
                    # Allow "Default" and "Public" but not other users
                    if user_dir.name.lower() not in ("default", "public", "default user", "all users"):
                        deny_list.append(user_dir)
    else:
        # Unix/Linux/macOS critical paths (NOT root - too broad)
        deny_list = [
            Path("/etc"),
            Path("/var"),
            Path("/usr"),
            Path("/bin"),
            Path("/sbin"),
            Path("/lib"),
            Path("/lib64"),
            Path("/boot"),
            Path("/root"),  # root user home
            Path("/sys"),
            Path("/proc"),
            Path("/dev"),
        ]

        # Deny other users' home directories
        home_parent = Path.home().parent
        current_user = Path.home().name
        if home_parent.exists():
            for user_dir in home_parent.iterdir():
                if user_dir.is_dir() and user_dir.name != current_user:
                    deny_list.append(user_dir)

    return deny_list


def is_in_deny_list(path: Path) -> Tuple[bool, str]:
    """
    Check if a path is in the critical deny list.

    Returns (is_denied, reason)
    """
    deny_list = _get_deny_list()

    try:
        resolved = path.resolve()

        for denied_path in deny_list:
            denied_resolved = denied_path.resolve() if denied_path.exists() else denied_path

            # Check if path is exactly the denied path or under it
            try:
                resolved.relative_to(denied_resolved)
                return True, f"Critical system path: {denied_path}"
            except ValueError:
                # Not under this denied path
                pass

            # On Windows, also do case-insensitive comparison
            if sys.platform == "win32":
                if str(resolved).lower() == str(denied_resolved).lower():
                    return True, f"Critical system path: {denied_path}"
                if str(resolved).lower().startswith(str(denied_resolved).lower() + "\\"):
                    return True, f"Critical system path: {denied_path}"

    except Exception as e:
        # If we can't check, err on the side of caution
        return True, f"Path validation error: {e}"

    return False, ""

# Audit log for workspace violations
AUDIT_DIR = Path.home() / ".agent" / "memory" / "audit"
WORKSPACE_AUDIT_FILE = AUDIT_DIR / "workspace_violations.jsonl"

# Ensure directories exist
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


# === DANGEROUS PATTERNS ===

# Path traversal patterns
TRAVERSAL_PATTERNS = [
    r'\.\.',           # Parent directory
    r'\.\./',          # Parent with slash
    r'/\.\./',         # Embedded parent
    r'\\\.\.\\',       # Windows backslash variant
]

# Compiled regex for efficiency
TRAVERSAL_REGEX = re.compile('|'.join(TRAVERSAL_PATTERNS))

# Unicode confusables that could bypass path checks
# These characters look like slashes or dots but aren't
UNICODE_CONFUSABLES = {
    '\u2024': '.',     # One dot leader
    '\u2025': '..',    # Two dot leader
    '\uFE52': '.',     # Small full stop
    '\uFF0E': '.',     # Fullwidth full stop
    '\u2215': '/',     # Division slash
    '\u2044': '/',     # Fraction slash
    '\uFF0F': '/',     # Fullwidth solidus
    '\u29F8': '/',     # Big solidus
    '\u29F9': '\\',    # Big reverse solidus
    '\uFF3C': '\\',    # Fullwidth reverse solidus
    '\uFE68': '\\',    # Small reverse solidus
}

# High-risk path patterns (even within workspace)
HIGH_RISK_PATHS = [
    r'\.env',          # Environment files
    r'\.git/config',   # Git config
    r'id_rsa',         # SSH keys
    r'\.ssh/',         # SSH directory
    r'credentials',    # Credential files
    r'secrets?\.json', # Secret files
    r'\.aws/',         # AWS credentials
    r'\.kube/config',  # Kubernetes config
]

HIGH_RISK_REGEX = re.compile('|'.join(HIGH_RISK_PATHS), re.IGNORECASE)


# === TOOL PATH EXTRACTION ===

# Maps tool names to their path argument keys
# This tells the guard where to find paths in tool arguments
TOOL_PATH_ARGS: Dict[str, List[str]] = {
    # Duro tools with paths
    "duro_run_skill": ["args.path", "args.file_path"],

    # File operation tools (hypothetical, for when they're added)
    "file_read": ["path", "file_path"],
    "file_write": ["path", "file_path"],
    "file_delete": ["path", "file_path"],
    "file_move": ["source", "destination", "src", "dst"],
    "file_copy": ["source", "destination", "src", "dst"],

    # Bash command parsing (special case)
    "bash_command": ["command"],  # Needs special parsing
    "shell_exec": ["command"],

    # SuperAGI tools
    "mcp__superagi__workspace_write": ["filename"],
    "mcp__superagi__workspace_read": ["filename"],
}

# Tools that should NEVER access files outside workspace
FILE_TOOLS: Set[str] = {
    "file_read", "file_write", "file_delete", "file_move", "file_copy",
    "mcp__superagi__workspace_write", "mcp__superagi__workspace_read",
}


# === WORKSPACE CONFIGURATION ===

@dataclass
class WorkspaceConfig:
    """Workspace configuration with allowed paths."""
    workspaces: List[Path] = field(default_factory=list)
    strict: bool = True
    high_risk_require_approval: bool = True
    loaded_from: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspaces": [str(w) for w in self.workspaces],
            "strict": self.strict,
            "high_risk_require_approval": self.high_risk_require_approval,
            "loaded_from": self.loaded_from,
        }


def load_workspace_config() -> WorkspaceConfig:
    """
    Load workspace configuration from environment and config file.

    Priority:
    1. DURO_WORKSPACE env var (comma-separated paths)
    2. Config file (~/.agent/config/workspace.json)
    3. Default workspaces
    """
    config = WorkspaceConfig()

    # Start with defaults
    config.workspaces = list(DEFAULT_WORKSPACES)

    # Check config file
    if WORKSPACE_CONFIG_FILE.exists():
        try:
            with open(WORKSPACE_CONFIG_FILE, "r", encoding="utf-8") as f:
                file_config = json.load(f)

            if "workspaces" in file_config:
                for ws in file_config["workspaces"]:
                    path = Path(ws).expanduser().resolve()
                    if path not in config.workspaces:
                        config.workspaces.append(path)

            if "strict" in file_config:
                config.strict = bool(file_config["strict"])

            if "high_risk_require_approval" in file_config:
                config.high_risk_require_approval = bool(file_config["high_risk_require_approval"])

            config.loaded_from = "config_file"
        except Exception as e:
            print(f"[WARN] Failed to load workspace config: {e}", file=sys.stderr)

    # Check environment variable (overrides file)
    env_workspaces = os.environ.get(WORKSPACE_ENV, "").strip()
    if env_workspaces:
        for ws in env_workspaces.split(","):
            ws = ws.strip()
            if ws:
                path = Path(ws).expanduser().resolve()
                if path not in config.workspaces:
                    config.workspaces.append(path)
        config.loaded_from = "environment"

    # Check strict mode env
    strict_env = os.environ.get(WORKSPACE_STRICT_ENV, "").strip()
    if strict_env:
        config.strict = strict_env == "1"

    return config


def save_workspace_config(config: WorkspaceConfig) -> bool:
    """Save workspace configuration to config file."""
    try:
        with open(WORKSPACE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2)
        return True
    except Exception as e:
        print(f"[WARN] Failed to save workspace config: {e}", file=sys.stderr)
        return False


# Global config (loaded once)
_workspace_config: Optional[WorkspaceConfig] = None


def get_workspace_config() -> WorkspaceConfig:
    """Get the current workspace configuration (cached)."""
    global _workspace_config
    if _workspace_config is None:
        _workspace_config = load_workspace_config()
    return _workspace_config


def reload_workspace_config() -> WorkspaceConfig:
    """Force reload of workspace configuration."""
    global _workspace_config
    _workspace_config = load_workspace_config()
    return _workspace_config


# Safe parent directories for workspace additions (no approval needed)
# Adding workspaces outside these requires approval
SAFE_WORKSPACE_PARENTS: List[Path] = [
    Path.home(),  # User's home directory and subdirs are safe
]


def is_safe_workspace_addition(path: Path) -> Tuple[bool, str]:
    """
    Check if adding a workspace is "safe" (no approval needed).

    Safe = subdirectory of user's home directory.
    Unsafe = system directories, other users, root paths.

    Returns (is_safe, reason)
    """
    try:
        resolved = path.resolve()

        # Check if it's under a safe parent
        for safe_parent in SAFE_WORKSPACE_PARENTS:
            try:
                resolved.relative_to(safe_parent)
                return True, f"Subdirectory of {safe_parent}"
            except ValueError:
                continue

        # Not under any safe parent - this is privilege escalation
        return False, f"Path {resolved} is outside safe directories (requires approval)"

    except Exception as e:
        return False, f"Path validation failed: {e}"


def add_workspace(path: str, force: bool = False) -> Tuple[bool, str, bool]:
    """
    Add a workspace path to the configuration.

    Args:
        path: Directory path to add
        force: If True, skip safety check (requires prior approval)

    Returns:
        (success, message, requires_approval)

    If requires_approval=True, caller should request approval before
    calling again with force=True.
    """
    config = get_workspace_config()
    resolved = Path(path).expanduser().resolve()

    if not resolved.exists():
        return False, f"Path does not exist: {resolved}", False

    if not resolved.is_dir():
        return False, f"Path is not a directory: {resolved}", False

    if resolved in config.workspaces:
        return True, f"Path already in workspaces: {resolved}", False

    # CRITICAL: Check deny list BEFORE anything else
    # Even force=True cannot override this (only breakglass can)
    is_denied, deny_reason = is_in_deny_list(resolved)
    if is_denied:
        breakglass_active = os.environ.get("DURO_POLICY_BREAKGLASS", "").strip() == "1"
        if not breakglass_active:
            return False, f"DENIED: {deny_reason} (only breakglass can override)", False

    # Check if this is a safe addition
    if not force:
        is_safe, reason = is_safe_workspace_addition(resolved)
        if not is_safe:
            return False, reason, True  # Requires approval

    config.workspaces.append(resolved)
    save_workspace_config(config)

    # Log this addition (it's a privilege change)
    log_workspace_addition(str(resolved), force)

    return True, f"Added workspace: {resolved}", False


def log_workspace_addition(path: str, was_forced: bool):
    """Log workspace addition to audit trail."""
    try:
        record = {
            "ts": utc_now_iso(),
            "event": "workspace_added",
            "path": path,
            "forced": was_forced,
        }
        with open(WORKSPACE_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"[WARN] Workspace audit log failed: {e}", file=sys.stderr)


# === PATH VALIDATION ===

@dataclass
class PathValidation:
    """Result of path validation."""
    valid: bool
    normalized_path: Optional[Path]
    reason: str
    risk_level: str = "safe"  # safe, elevated, high_risk, blocked
    workspace_match: Optional[Path] = None
    requires_approval: bool = False


def normalize_unicode(path_str: str) -> str:
    """
    Normalize unicode to catch confusable characters.

    Converts lookalike characters to their ASCII equivalents
    before path processing.
    """
    # First, apply NFKC normalization (compatibility decomposition)
    normalized = unicodedata.normalize('NFKC', path_str)

    # Then replace known confusables
    for confusable, replacement in UNICODE_CONFUSABLES.items():
        normalized = normalized.replace(confusable, replacement)

    return normalized


def check_traversal(path_str: str) -> Tuple[bool, str]:
    """
    Check for path traversal attempts.

    Returns (has_traversal, pattern_found)
    """
    # Check raw string first
    if '..' in path_str:
        return True, ".."

    # Check regex patterns
    match = TRAVERSAL_REGEX.search(path_str)
    if match:
        return True, match.group()

    return False, ""


def resolve_path_safely(path_str: str) -> Tuple[Optional[Path], str]:
    """
    Safely resolve a path, catching symlink tricks.

    Returns (resolved_path, error_message)
    """
    try:
        # Normalize unicode first
        path_str = normalize_unicode(path_str)

        # Expand user (~) and resolve
        path = Path(path_str).expanduser()

        # Check for traversal BEFORE resolving
        has_traversal, pattern = check_traversal(str(path))
        if has_traversal:
            return None, f"Path traversal detected: {pattern}"

        # Resolve to absolute path (follows symlinks)
        resolved = path.resolve()

        # Check for traversal AFTER resolving (symlink tricks)
        has_traversal, pattern = check_traversal(str(resolved))
        if has_traversal:
            return None, f"Symlink traversal detected: {pattern}"

        return resolved, ""

    except Exception as e:
        return None, f"Path resolution failed: {e}"


def is_path_in_workspace(path: Path, workspaces: List[Path]) -> Tuple[bool, Optional[Path]]:
    """
    Check if a path is within any allowed workspace.

    Returns (is_in_workspace, matching_workspace)
    """
    for workspace in workspaces:
        try:
            # Check if path is relative to workspace
            path.relative_to(workspace)
            return True, workspace
        except ValueError:
            continue
    return False, None


def check_high_risk(path_str: str) -> Tuple[bool, str]:
    """
    Check if path matches high-risk patterns.

    Returns (is_high_risk, pattern_matched)
    """
    match = HIGH_RISK_REGEX.search(path_str)
    if match:
        return True, match.group()
    return False, ""


def validate_path(
    path_str: str,
    tool_name: str = None,
    config: WorkspaceConfig = None,
) -> PathValidation:
    """
    Validate a path against workspace constraints.

    This is the main entry point for path validation.

    Args:
        path_str: The path to validate
        tool_name: The tool requesting access (for logging)
        config: Workspace configuration (uses global if not provided)

    Returns:
        PathValidation with result details
    """
    if config is None:
        config = get_workspace_config()

    # Step 1: Resolve path safely
    resolved, error = resolve_path_safely(path_str)
    if resolved is None:
        return PathValidation(
            valid=False,
            normalized_path=None,
            reason=error,
            risk_level="blocked",
        )

    # Step 1.5: Check critical deny list (ALWAYS blocked, even with approval)
    is_denied, deny_reason = is_in_deny_list(resolved)
    if is_denied:
        return PathValidation(
            valid=False,
            normalized_path=resolved,
            reason=f"DENIED: {deny_reason}",
            risk_level="critical",
        )

    # Step 2: Check if in workspace
    in_workspace, workspace_match = is_path_in_workspace(resolved, config.workspaces)

    if not in_workspace:
        if config.strict:
            return PathValidation(
                valid=False,
                normalized_path=resolved,
                reason=f"Path outside allowed workspaces: {resolved}",
                risk_level="blocked",
            )
        else:
            # Non-strict mode: allow but flag as elevated risk
            return PathValidation(
                valid=True,
                normalized_path=resolved,
                reason=f"Path outside workspace (non-strict mode): {resolved}",
                risk_level="elevated",
                requires_approval=True,
            )

    # Step 3: Check for high-risk patterns
    is_high_risk, risk_pattern = check_high_risk(str(resolved))
    if is_high_risk:
        if config.high_risk_require_approval:
            return PathValidation(
                valid=True,  # Allow but require approval
                normalized_path=resolved,
                reason=f"High-risk path pattern: {risk_pattern}",
                risk_level="high_risk",
                workspace_match=workspace_match,
                requires_approval=True,
            )
        else:
            return PathValidation(
                valid=True,
                normalized_path=resolved,
                reason=f"High-risk path (approval not required): {risk_pattern}",
                risk_level="elevated",
                workspace_match=workspace_match,
            )

    # Step 4: Valid path within workspace
    return PathValidation(
        valid=True,
        normalized_path=resolved,
        reason="Path within workspace",
        risk_level="safe",
        workspace_match=workspace_match,
    )


# === TOOL ARGUMENT PATH EXTRACTION ===

def extract_paths_from_args(
    tool_name: str,
    arguments: Dict[str, Any],
) -> List[Tuple[str, str]]:
    """
    Extract path arguments from tool arguments.

    Returns list of (arg_key, path_value) tuples.
    """
    paths = []

    # Get path argument keys for this tool
    path_keys = TOOL_PATH_ARGS.get(tool_name, [])

    # Also check common path-like keys
    common_keys = ["path", "file_path", "filepath", "filename", "file", "directory", "dir"]

    all_keys = set(path_keys + common_keys)

    for key in all_keys:
        # Handle nested keys (e.g., "args.path")
        if "." in key:
            parts = key.split(".")
            value = arguments
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break
            if value and isinstance(value, str):
                paths.append((key, value))
        else:
            if key in arguments and isinstance(arguments[key], str):
                paths.append((key, arguments[key]))

    return paths


def validate_tool_paths(
    tool_name: str,
    arguments: Dict[str, Any],
    config: WorkspaceConfig = None,
) -> List[PathValidation]:
    """
    Validate all paths in tool arguments.

    Returns list of PathValidation results for each path found.
    """
    paths = extract_paths_from_args(tool_name, arguments)
    validations = []

    for arg_key, path_value in paths:
        validation = validate_path(path_value, tool_name, config)
        # Add the argument key to the reason for context
        validation.reason = f"[{arg_key}] {validation.reason}"
        validations.append(validation)

    return validations


# === BASH COMMAND PATH EXTRACTION ===

# Patterns to extract paths from bash commands
BASH_PATH_PATTERNS = [
    # File operations
    r'(?:cat|head|tail|less|more|vim|nano|code)\s+([^\s|>&;]+)',
    r'(?:rm|rmdir|unlink)\s+(?:-[rf]+\s+)?([^\s|>&;]+)',
    r'(?:cp|mv)\s+(?:-[a-z]+\s+)?([^\s|>&;]+)\s+([^\s|>&;]+)',
    r'(?:mkdir|touch)\s+(?:-[a-z]+\s+)?([^\s|>&;]+)',
    r'(?:chmod|chown)\s+(?:[^\s]+\s+)?([^\s|>&;]+)',

    # Redirections
    r'>\s*([^\s|>&;]+)',
    r'>>\s*([^\s|>&;]+)',
    r'<\s*([^\s|>&;]+)',

    # Common path-like arguments
    r'--(?:file|path|output|input|config)=([^\s|>&;]+)',
    r'-(?:f|o|i|c)\s+([^\s|>&;]+)',
]

BASH_PATH_REGEX = [re.compile(p) for p in BASH_PATH_PATTERNS]


def extract_paths_from_bash(command: str) -> List[str]:
    """
    Extract potential file paths from a bash command.

    This is heuristic - may have false positives/negatives.
    """
    paths = []

    for pattern in BASH_PATH_REGEX:
        matches = pattern.findall(command)
        for match in matches:
            if isinstance(match, tuple):
                paths.extend(match)
            else:
                paths.append(match)

    # Filter out obvious non-paths
    filtered = []
    for p in paths:
        p = p.strip('"\'')
        if not p:
            continue
        if p.startswith('-'):
            continue
        if p in ('|', '&', ';', '>', '<', '>>', '&&', '||'):
            continue
        # Looks like a path
        if '/' in p or '\\' in p or p.startswith('~') or p.startswith('.'):
            filtered.append(p)
        # Could be a relative file
        elif '.' in p and not p.startswith('http'):
            filtered.append(p)

    return list(set(filtered))


def validate_bash_command(
    command: str,
    config: WorkspaceConfig = None,
) -> List[PathValidation]:
    """
    Validate paths extracted from a bash command.

    Returns list of PathValidation results for each path found.
    """
    paths = extract_paths_from_bash(command)
    validations = []

    for path_value in paths:
        validation = validate_path(path_value, "bash_command", config)
        validation.reason = f"[bash: {path_value}] {validation.reason}"
        validations.append(validation)

    return validations


# === AUDIT LOGGING ===

def log_workspace_violation(
    tool_name: str,
    path: str,
    validation: PathValidation,
    arguments: Dict[str, Any] = None,
):
    """Log a workspace violation to the audit trail."""
    try:
        record = {
            "ts": utc_now_iso(),
            "tool": tool_name,
            "path": path,
            "reason": validation.reason,
            "risk_level": validation.risk_level,
            "valid": validation.valid,
            "requires_approval": validation.requires_approval,
        }

        with open(WORKSPACE_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    except Exception as e:
        print(f"[WARN] Workspace audit log failed: {e}", file=sys.stderr)


# === INTEGRATION WITH POLICY GATE ===

def check_workspace_constraints(
    tool_name: str,
    arguments: Dict[str, Any],
    config: WorkspaceConfig = None,
) -> Tuple[bool, str, bool]:
    """
    Check workspace constraints for a tool call.

    This is the main integration point with policy_gate.

    Args:
        tool_name: The tool being called
        arguments: Tool arguments
        config: Workspace configuration

    Returns:
        (allowed, reason, requires_approval)
    """
    if config is None:
        config = get_workspace_config()

    # Special handling for bash commands
    if tool_name in ("bash_command", "shell_exec", "mcp__superagi__shell_execute"):
        command = arguments.get("command", "")
        validations = validate_bash_command(command, config)
    else:
        validations = validate_tool_paths(tool_name, arguments, config)

    # No paths found - allow
    if not validations:
        return True, "No paths to validate", False

    # Check all validations
    blocked = []
    requires_approval = False

    for v in validations:
        if not v.valid:
            blocked.append(v.reason)
            log_workspace_violation(tool_name, str(v.normalized_path or "unknown"), v, arguments)
        elif v.requires_approval:
            requires_approval = True

    if blocked:
        return False, "; ".join(blocked), False

    if requires_approval:
        reasons = [v.reason for v in validations if v.requires_approval]
        return True, "; ".join(reasons), True

    return True, "All paths within workspace", False


# === WORKSPACE STATUS ===

def get_workspace_status() -> Dict[str, Any]:
    """Get current workspace configuration status."""
    config = get_workspace_config()

    return {
        "workspaces": [str(w) for w in config.workspaces],
        "strict": config.strict,
        "high_risk_require_approval": config.high_risk_require_approval,
        "loaded_from": config.loaded_from,
        "config_file": str(WORKSPACE_CONFIG_FILE),
        "config_file_exists": WORKSPACE_CONFIG_FILE.exists(),
    }
