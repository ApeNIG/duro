"""
Skill Runner - The spine for all Duro skill execution.

Core responsibilities:
1. Validate skill arguments against schema
2. Enforce path allowlist (security)
3. Enforce file size limits and timeouts
4. Standardize all results
5. Progress callbacks for long-running skills

Every skill runs through this. It's the trust layer.
"""

import os
import re
import time
import fnmatch
import shutil
import subprocess
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union, Protocol, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import json


# === Configuration ===

MAX_FILE_SIZE_KB = 500  # Default max file size to process
DEFAULT_TIMEOUT_MS = 30000  # 30 seconds
RULE_TIMEOUT_MS = 5000  # Per-rule timeout

# Safe base directories (skills can only access files under these)
ALLOWED_ROOTS = [
    Path.home() / "Desktop" / "BUILD",
    Path.home() / ".agent",
    Path.home() / "stride-server",
    Path.home() / "homecoach",
]


# === Pre-Check System ===

@dataclass
class PreCheckResult:
    """Result of a pre-check."""
    check_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PreCheckRunner:
    """
    Runs pre-checks before skill execution.

    Supported checks:
    - ffmpeg_available: Check if ffmpeg is installed and working
    - network_available: Check basic network connectivity
    - dependency_installed:<package>: Check if a Python package is installed
    - mcp_pencil_available: Check if Pencil MCP server is accessible (always passes in skill context)
    - git_repo: Check if current directory is a git repository

    Usage:
        checker = PreCheckRunner()
        results = checker.run_checks(["ffmpeg_available", "network_available"])
        if all(r.passed for r in results):
            # proceed with skill execution
    """

    # Cache for expensive checks (cleared per session)
    _cache: Dict[str, PreCheckResult] = {}
    _cache_ttl_seconds: int = 300  # 5 minutes
    _cache_timestamps: Dict[str, float] = {}

    def __init__(self, cache_enabled: bool = True):
        self.cache_enabled = cache_enabled

    def _get_cached(self, check_name: str) -> Optional[PreCheckResult]:
        """Get cached result if valid."""
        if not self.cache_enabled:
            return None
        if check_name in self._cache:
            timestamp = self._cache_timestamps.get(check_name, 0)
            if time.time() - timestamp < self._cache_ttl_seconds:
                return self._cache[check_name]
            # Expired - remove from cache
            del self._cache[check_name]
            del self._cache_timestamps[check_name]
        return None

    def _set_cached(self, check_name: str, result: PreCheckResult) -> None:
        """Cache a result."""
        if self.cache_enabled:
            self._cache[check_name] = result
            self._cache_timestamps[check_name] = time.time()

    def clear_cache(self) -> None:
        """Clear the pre-check cache."""
        self._cache.clear()
        self._cache_timestamps.clear()

    def run_check(self, check_name: str) -> PreCheckResult:
        """Run a single pre-check."""
        # Check cache first
        cached = self._get_cached(check_name)
        if cached:
            return cached

        # Parse check name
        if check_name.startswith("dependency_installed:"):
            package = check_name.split(":", 1)[1]
            result = self._check_dependency_installed(package)
        elif check_name == "ffmpeg_available":
            result = self._check_ffmpeg()
        elif check_name == "network_available":
            result = self._check_network()
        elif check_name == "mcp_pencil_available":
            result = self._check_mcp_pencil()
        elif check_name == "git_repo":
            result = self._check_git_repo()
        else:
            result = PreCheckResult(
                check_name=check_name,
                passed=False,
                message=f"Unknown pre-check: {check_name}"
            )

        # Cache and return
        self._set_cached(check_name, result)
        return result

    def run_checks(self, checks: List[str]) -> List[PreCheckResult]:
        """Run multiple pre-checks."""
        return [self.run_check(check) for check in checks]

    def _check_ffmpeg(self) -> PreCheckResult:
        """Check if ffmpeg is installed and get version."""
        try:
            # Try to find ffmpeg
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                return PreCheckResult(
                    check_name="ffmpeg_available",
                    passed=False,
                    message="ffmpeg not found in PATH",
                    details={"searched_path": os.environ.get("PATH", "")}
                )

            # Get version
            try:
                result = subprocess.run(
                    [ffmpeg_path, "-version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
                # Parse version: "ffmpeg version 6.0 Copyright..."
                version_match = re.search(r"ffmpeg version (\S+)", version_line)
                version = version_match.group(1) if version_match else version_line

                return PreCheckResult(
                    check_name="ffmpeg_available",
                    passed=True,
                    message=f"ffmpeg {version} available",
                    details={
                        "path": ffmpeg_path,
                        "version": version,
                        "version_line": version_line
                    }
                )
            except subprocess.TimeoutExpired:
                return PreCheckResult(
                    check_name="ffmpeg_available",
                    passed=False,
                    message="ffmpeg found but version check timed out",
                    details={"path": ffmpeg_path}
                )
            except Exception as e:
                return PreCheckResult(
                    check_name="ffmpeg_available",
                    passed=False,
                    message=f"ffmpeg found but version check failed: {e}",
                    details={"path": ffmpeg_path}
                )

        except Exception as e:
            return PreCheckResult(
                check_name="ffmpeg_available",
                passed=False,
                message=f"ffmpeg check failed: {e}"
            )

    def _check_network(self) -> PreCheckResult:
        """Check basic network connectivity."""
        try:
            # Try to connect to a reliable host
            hosts = [
                ("8.8.8.8", 53),  # Google DNS
                ("1.1.1.1", 53),  # Cloudflare DNS
            ]

            for host, port in hosts:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    result = sock.connect_ex((host, port))
                    sock.close()

                    if result == 0:
                        return PreCheckResult(
                            check_name="network_available",
                            passed=True,
                            message="Network connectivity confirmed",
                            details={"tested_host": host, "port": port}
                        )
                except Exception:
                    continue

            return PreCheckResult(
                check_name="network_available",
                passed=False,
                message="No network connectivity - could not reach DNS servers",
                details={"tested_hosts": [h[0] for h in hosts]}
            )

        except Exception as e:
            return PreCheckResult(
                check_name="network_available",
                passed=False,
                message=f"Network check failed: {e}"
            )

    def _check_dependency_installed(self, package: str) -> PreCheckResult:
        """Check if a Python package is installed."""
        try:
            import importlib

            # Handle package name normalization (e.g., edge-tts -> edge_tts)
            module_name = package.replace("-", "_")

            try:
                module = importlib.import_module(module_name)
                version = getattr(module, "__version__", "unknown")

                return PreCheckResult(
                    check_name=f"dependency_installed:{package}",
                    passed=True,
                    message=f"{package} installed (version: {version})",
                    details={"package": package, "version": version, "module": module_name}
                )
            except ImportError:
                # Try alternative import paths
                try:
                    # Some packages use different import names
                    __import__(package)
                    return PreCheckResult(
                        check_name=f"dependency_installed:{package}",
                        passed=True,
                        message=f"{package} installed",
                        details={"package": package}
                    )
                except ImportError:
                    return PreCheckResult(
                        check_name=f"dependency_installed:{package}",
                        passed=False,
                        message=f"Package {package} not installed. Install with: pip install {package}",
                        details={"package": package, "install_command": f"pip install {package}"}
                    )

        except Exception as e:
            return PreCheckResult(
                check_name=f"dependency_installed:{package}",
                passed=False,
                message=f"Dependency check failed: {e}"
            )

    def _check_mcp_pencil(self) -> PreCheckResult:
        """Check if Pencil MCP server is available."""
        # In the skill context, we assume MCP tools are available if we're running
        # This is a soft check - skills that require Pencil should handle errors gracefully
        return PreCheckResult(
            check_name="mcp_pencil_available",
            passed=True,
            message="MCP Pencil assumed available (skill context)",
            details={"note": "Actual availability depends on MCP server configuration"}
        )

    def _check_git_repo(self) -> PreCheckResult:
        """Check if current directory is a git repository."""
        try:
            # Check for .git directory
            git_dir = Path.cwd() / ".git"
            if git_dir.is_dir():
                return PreCheckResult(
                    check_name="git_repo",
                    passed=True,
                    message="Git repository detected",
                    details={"git_dir": str(git_dir)}
                )

            # Check using git command
            git_path = shutil.which("git")
            if git_path:
                result = subprocess.run(
                    [git_path, "rev-parse", "--git-dir"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    return PreCheckResult(
                        check_name="git_repo",
                        passed=True,
                        message="Git repository detected",
                        details={"git_dir": result.stdout.strip()}
                    )

            return PreCheckResult(
                check_name="git_repo",
                passed=False,
                message="Not a git repository",
                details={"cwd": str(Path.cwd())}
            )

        except Exception as e:
            return PreCheckResult(
                check_name="git_repo",
                passed=False,
                message=f"Git repo check failed: {e}"
            )


# Global pre-check runner instance
_pre_check_runner: Optional[PreCheckRunner] = None


def get_pre_check_runner() -> PreCheckRunner:
    """Get or create the global PreCheckRunner instance."""
    global _pre_check_runner
    if _pre_check_runner is None:
        _pre_check_runner = PreCheckRunner()
    return _pre_check_runner


def run_pre_checks(checks: List[str]) -> Tuple[bool, List[PreCheckResult]]:
    """
    Convenience function to run pre-checks.

    Args:
        checks: List of check names to run

    Returns:
        Tuple of (all_passed, results)
    """
    runner = get_pre_check_runner()
    results = runner.run_checks(checks)
    all_passed = all(r.passed for r in results)
    return all_passed, results


def check_ffmpeg() -> Tuple[bool, str, Optional[str]]:
    """
    Check if ffmpeg is available.

    Returns:
        Tuple of (available, version_string, error_message)
    """
    result = get_pre_check_runner().run_check("ffmpeg_available")
    if result.passed:
        version = result.details.get("version", "unknown") if result.details else "unknown"
        return True, version, None
    return False, "", result.message


class Severity(Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class ProgressEvent(Enum):
    """Types of progress events."""
    STARTED = "started"
    PROGRESS = "progress"
    SUBSTEP = "substep"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ProgressUpdate:
    """A progress update from a skill."""
    event: ProgressEvent
    current: int
    total: int
    message: str
    percentage: float
    elapsed_ms: float
    estimated_remaining_ms: Optional[float] = None
    substep: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal event (completed or error)."""
        return self.event in (ProgressEvent.COMPLETED, ProgressEvent.ERROR)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event"] = self.event.value
        return d


class ProgressCallback(Protocol):
    """Protocol for progress callbacks."""
    def __call__(self, update: ProgressUpdate) -> None:
        """Handle a progress update."""
        ...


class ProgressReporter:
    """
    Helper for skills to report progress.

    Usage:
        reporter = ProgressReporter(total=100, callback=callback)
        reporter.start("Processing files...")
        for i, file in enumerate(files):
            reporter.update(i + 1, f"Processing {file}")
        reporter.complete("Done!")
    """

    def __init__(
        self,
        total: int,
        callback: Optional[ProgressCallback] = None,
        label: str = "progress"
    ):
        self.total = total
        self.callback = callback
        self.label = label
        self.current = 0
        self.start_time = time.time()
        self._history: List[ProgressUpdate] = []

    def _emit(self, update: ProgressUpdate) -> None:
        """Emit a progress update."""
        self._history.append(update)
        if self.callback:
            try:
                self.callback(update)
            except Exception:
                pass  # Don't let callback errors break the skill

    def _elapsed_ms(self) -> float:
        return (time.time() - self.start_time) * 1000

    def _estimate_remaining(self) -> Optional[float]:
        """Estimate remaining time based on progress rate."""
        if self.current <= 0 or self.total <= 0:
            return None
        elapsed = self._elapsed_ms()
        rate = self.current / elapsed  # items per ms
        remaining_items = self.total - self.current
        if rate > 0:
            return remaining_items / rate
        return None

    def start(self, message: str = "Starting...") -> None:
        """Emit a start event."""
        self.start_time = time.time()
        self._emit(ProgressUpdate(
            event=ProgressEvent.STARTED,
            current=0,
            total=self.total,
            message=message,
            percentage=0.0,
            elapsed_ms=0.0
        ))

    def update(
        self,
        current: int,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update progress."""
        self.current = current
        percentage = (current / self.total * 100) if self.total > 0 else 0.0
        self._emit(ProgressUpdate(
            event=ProgressEvent.PROGRESS,
            current=current,
            total=self.total,
            message=message,
            percentage=percentage,
            elapsed_ms=self._elapsed_ms(),
            estimated_remaining_ms=self._estimate_remaining(),
            metadata=metadata or {}
        ))

    def substep(self, substep_name: str, message: str = "") -> None:
        """Report a substep within the current progress."""
        self._emit(ProgressUpdate(
            event=ProgressEvent.SUBSTEP,
            current=self.current,
            total=self.total,
            message=message,
            percentage=(self.current / self.total * 100) if self.total > 0 else 0.0,
            elapsed_ms=self._elapsed_ms(),
            substep=substep_name
        ))

    def complete(self, message: str = "Completed") -> None:
        """Emit completion event."""
        self.current = self.total
        self._emit(ProgressUpdate(
            event=ProgressEvent.COMPLETED,
            current=self.total,
            total=self.total,
            message=message,
            percentage=100.0,
            elapsed_ms=self._elapsed_ms()
        ))

    def error(self, message: str) -> None:
        """Emit error event."""
        self._emit(ProgressUpdate(
            event=ProgressEvent.ERROR,
            current=self.current,
            total=self.total,
            message=message,
            percentage=(self.current / self.total * 100) if self.total > 0 else 0.0,
            elapsed_ms=self._elapsed_ms()
        ))

    @property
    def history(self) -> List[ProgressUpdate]:
        """Get progress history."""
        return self._history.copy()


class AggregateProgressReporter:
    """
    Aggregates progress from multiple sub-reporters.

    Usage:
        agg = AggregateProgressReporter(callback)
        agg.add_stage("download", weight=1)
        agg.add_stage("process", weight=3)
        agg.add_stage("upload", weight=1)

        download_reporter = agg.get_reporter("download")
        # ... use download_reporter
    """

    def __init__(self, callback: Optional[ProgressCallback] = None):
        self.callback = callback
        self.stages: Dict[str, Dict[str, Any]] = {}
        self.start_time = time.time()

    def add_stage(self, name: str, total: int = 100, weight: float = 1.0) -> None:
        """Add a stage with optional weighting."""
        self.stages[name] = {
            "total": total,
            "current": 0,
            "weight": weight,
            "complete": False
        }

    def get_reporter(self, stage_name: str) -> ProgressReporter:
        """Get a reporter for a specific stage."""
        if stage_name not in self.stages:
            raise ValueError(f"Unknown stage: {stage_name}")

        def stage_callback(update: ProgressUpdate) -> None:
            self._handle_stage_update(stage_name, update)

        return ProgressReporter(
            total=self.stages[stage_name]["total"],
            callback=stage_callback,
            label=stage_name
        )

    def _handle_stage_update(self, stage: str, update: ProgressUpdate) -> None:
        """Handle progress update from a stage."""
        self.stages[stage]["current"] = update.current
        if update.event == ProgressEvent.COMPLETED:
            self.stages[stage]["complete"] = True

        # Calculate aggregate progress
        total_weight = sum(s["weight"] for s in self.stages.values())
        weighted_progress = sum(
            (s["current"] / s["total"]) * s["weight"]
            for s in self.stages.values()
            if s["total"] > 0
        )
        aggregate_pct = (weighted_progress / total_weight * 100) if total_weight > 0 else 0

        # Emit aggregate update
        if self.callback:
            self.callback(ProgressUpdate(
                event=update.event,
                current=int(aggregate_pct),
                total=100,
                message=f"[{stage}] {update.message}",
                percentage=aggregate_pct,
                elapsed_ms=(time.time() - self.start_time) * 1000,
                substep=stage,
                metadata={"stage": stage, "stage_progress": update.percentage}
            ))


def report_progress(
    tools: Dict[str, Any],
    current: int,
    total: int,
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Convenience function for skills to report progress.

    Args:
        tools: The tools dict passed to the skill
        current: Current progress (0 to total)
        total: Total items
        message: Optional status message
        metadata: Optional metadata dict
    """
    reporter = tools.get("_progress_reporter")
    if reporter:
        reporter.update(current, message, metadata)


def create_progress_reporter(
    tools: Dict[str, Any],
    total: int,
    label: str = "progress"
) -> ProgressReporter:
    """
    Create a ProgressReporter from the tools dict.

    Args:
        tools: The tools dict passed to the skill
        total: Total number of items to process
        label: Label for this progress reporter

    Returns:
        A ProgressReporter (may have no-op callback if none provided)
    """
    callback = tools.get("_progress_callback")
    return ProgressReporter(total=total, callback=callback, label=label)


@dataclass
class Finding:
    """A single finding from a verification skill."""
    id: str  # Unique ID for suppression (e.g., "design_drift_001")
    type: str  # Finding type (e.g., "design_drift", "quality_violation")
    severity: Severity
    confidence: float  # 0-1
    file: str
    line: Optional[int] = None
    snippet: Optional[str] = None  # Redacted/truncated
    message: str = ""
    suggested_fix: Optional[str] = None
    rule_id: Optional[str] = None  # For suppressions

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class CheckResult:
    """Result of a single check/rule."""
    name: str
    success: bool
    duration_ms: float
    findings: List[Finding] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class SkillResult:
    """Standardized result from any skill execution."""
    success: bool
    summary: str
    run_id: str
    timestamp: str
    repo: Optional[str] = None

    # Detailed results
    checks: List[CheckResult] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)  # Created file paths

    # Diagnostics
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timings: Dict[str, float] = field(default_factory=dict)

    # Suppressed findings (tracked but not counted as failures)
    suppressed: List[Finding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        d = asdict(self)
        d["checks"] = [asdict(c) for c in self.checks]
        d["findings"] = [f.to_dict() for f in self.findings]
        d["suppressed"] = [f.to_dict() for f in self.suppressed]
        return d

    def to_devkit_json(self) -> str:
        """Output in devkit-compatible format."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class RuleSpec:
    """Specification for a verification rule."""
    id: str
    name: str
    pattern: str  # Regex pattern
    message: str
    severity: Severity = Severity.WARN
    confidence: float = 0.8

    # Guardrails
    scope: List[str] = field(default_factory=lambda: ["**/*"])  # File globs
    max_file_kb: int = MAX_FILE_SIZE_KB
    timeout_ms: int = RULE_TIMEOUT_MS

    # Optional
    suggested_fix: Optional[str] = None
    suppress_id: Optional[str] = None  # Custom suppression ID format


class SuppressionManager:
    """
    Manages rule suppressions from:
    - .duroignore files (path patterns)
    - Inline comments (// duro-ignore: rule_id)
    """

    INLINE_PATTERN = re.compile(r'//\s*duro-ignore:\s*(\S+)')

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.path_suppressions: List[str] = []
        self.rule_suppressions: Dict[str, List[str]] = {}  # rule_id -> [file patterns]
        self._load_duroignore()

    def _load_duroignore(self):
        """Load suppressions from .duroignore file."""
        ignore_file = self.project_root / ".duroignore"
        if not ignore_file.exists():
            return

        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Format: path_pattern or rule_id:path_pattern
            if ":" in line and not line.startswith("/"):
                rule_id, pattern = line.split(":", 1)
                if rule_id not in self.rule_suppressions:
                    self.rule_suppressions[rule_id] = []
                self.rule_suppressions[rule_id].append(pattern.strip())
            else:
                self.path_suppressions.append(line)

    def is_path_suppressed(self, file_path: str) -> bool:
        """Check if a file path is globally suppressed."""
        rel_path = str(Path(file_path).relative_to(self.project_root))
        for pattern in self.path_suppressions:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        return False

    def is_rule_suppressed(self, rule_id: str, file_path: str, line_content: str = "") -> bool:
        """Check if a rule is suppressed for a specific file/line."""
        # Check file-level suppression
        if rule_id in self.rule_suppressions:
            rel_path = str(Path(file_path).relative_to(self.project_root))
            for pattern in self.rule_suppressions[rule_id]:
                if fnmatch.fnmatch(rel_path, pattern):
                    return True

        # Check inline suppression
        if line_content:
            match = self.INLINE_PATTERN.search(line_content)
            if match and match.group(1) == rule_id:
                return True

        return False


class PathValidator:
    """
    Validates file paths for security.
    Prevents path traversal and access outside allowed roots.
    """

    def __init__(self, allowed_roots: Optional[List[Path]] = None):
        self.allowed_roots = allowed_roots or ALLOWED_ROOTS

    def is_safe(self, path: Union[str, Path]) -> bool:
        """Check if path is safe to access."""
        try:
            resolved = Path(path).resolve()

            # Check for path traversal attempts
            path_str = str(path)
            if ".." in path_str:
                return False

            # Check if under allowed root
            for root in self.allowed_roots:
                try:
                    resolved.relative_to(root.resolve())
                    return True
                except ValueError:
                    continue

            return False
        except Exception:
            return False

    def validate(self, path: Union[str, Path]) -> Path:
        """Validate and return resolved path, or raise."""
        if not self.is_safe(path):
            raise ValueError(f"Path not allowed: {path}")
        return Path(path).resolve()


class TimeoutError(Exception):
    """Raised when a skill or rule exceeds its timeout."""
    pass


def run_with_timeout(func: Callable, timeout_ms: int, *args, **kwargs) -> Any:
    """
    Run a function with a timeout.

    Note: This is a simple implementation. For production,
    consider using multiprocessing for true interruption.
    """
    result = [None]
    error = [None]

    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout_ms / 1000)

    if thread.is_alive():
        # Thread still running - timeout
        raise TimeoutError(f"Operation timed out after {timeout_ms}ms")

    if error[0]:
        raise error[0]

    return result[0]


def validate_args(args: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """
    Simple schema validation for skill arguments.

    Schema format:
    {
        "required": ["file_path", "rules"],
        "types": {
            "file_path": "str",
            "rules": "list",
            "max_findings": "int"
        },
        "defaults": {
            "max_findings": 100
        }
    }

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Check required fields
    for field in schema.get("required", []):
        if field not in args:
            errors.append(f"Missing required argument: {field}")

    # Check types
    type_map = {"str": str, "int": int, "float": float, "list": list, "dict": dict, "bool": bool}
    for field, expected_type in schema.get("types", {}).items():
        if field in args:
            if expected_type in type_map:
                if not isinstance(args[field], type_map[expected_type]):
                    errors.append(f"Invalid type for {field}: expected {expected_type}")

    # Apply defaults
    for field, default in schema.get("defaults", {}).items():
        if field not in args:
            args[field] = default

    return errors


def generate_run_id() -> str:
    """Generate a unique run ID."""
    import uuid
    return f"run_{uuid.uuid4().hex[:8]}"


def get_timestamp() -> str:
    """Get ISO timestamp."""
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


class SkillRunner:
    """
    The main skill execution engine.

    Usage:
        runner = SkillRunner(project_root="/path/to/project")
        result = runner.run(skill_func, args={"file_path": "src/app.tsx"})
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        allowed_roots: Optional[List[Path]] = None,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        max_file_kb: int = MAX_FILE_SIZE_KB
    ):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.path_validator = PathValidator(allowed_roots)
        self.suppressions = SuppressionManager(self.project_root)
        self.timeout_ms = timeout_ms
        self.max_file_kb = max_file_kb

    def run(
        self,
        skill_func: Callable[..., SkillResult],
        args: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallback] = None
    ) -> SkillResult:
        """
        Execute a skill with all guardrails.

        Args:
            skill_func: The skill function to execute
            args: Arguments to pass to the skill
            schema: Optional argument schema for validation
            progress_callback: Optional callback for progress updates

        Returns:
            SkillResult with standardized output
        """
        run_id = generate_run_id()
        timestamp = get_timestamp()
        start_time = time.time()

        # Emit start progress if callback provided
        if progress_callback:
            progress_callback(ProgressUpdate(
                event=ProgressEvent.STARTED,
                current=0,
                total=100,
                message=f"Starting skill execution",
                percentage=0.0,
                elapsed_ms=0.0,
                metadata={"run_id": run_id}
            ))

        # Validate arguments
        if schema:
            validation_errors = validate_args(args, schema)
            if validation_errors:
                if progress_callback:
                    progress_callback(ProgressUpdate(
                        event=ProgressEvent.ERROR,
                        current=0,
                        total=100,
                        message=f"Validation failed",
                        percentage=0.0,
                        elapsed_ms=(time.time() - start_time) * 1000
                    ))
                return SkillResult(
                    success=False,
                    summary=f"Validation failed: {', '.join(validation_errors)}",
                    run_id=run_id,
                    timestamp=timestamp,
                    errors=validation_errors
                )

        # Validate paths in args
        path_fields = ["file_path", "project_path", "target_path", "source_path"]
        for field in path_fields:
            if field in args:
                try:
                    args[field] = str(self.path_validator.validate(args[field]))
                except ValueError as e:
                    if progress_callback:
                        progress_callback(ProgressUpdate(
                            event=ProgressEvent.ERROR,
                            current=0,
                            total=100,
                            message=f"Path validation failed: {e}",
                            percentage=0.0,
                            elapsed_ms=(time.time() - start_time) * 1000
                        ))
                    return SkillResult(
                        success=False,
                        summary=f"Path validation failed: {e}",
                        run_id=run_id,
                        timestamp=timestamp,
                        errors=[str(e)]
                    )

        # Inject runner context
        args["_runner"] = self
        args["_run_id"] = run_id
        args["_suppressions"] = self.suppressions
        args["_progress_callback"] = progress_callback

        # Execute with timeout
        try:
            result = run_with_timeout(skill_func, self.timeout_ms, **args)

            # Ensure result is SkillResult
            if not isinstance(result, SkillResult):
                result = SkillResult(
                    success=True,
                    summary="Skill completed",
                    run_id=run_id,
                    timestamp=timestamp
                )
            else:
                result.run_id = run_id
                result.timestamp = timestamp

            # Add timing
            result.timings["total_ms"] = (time.time() - start_time) * 1000

            # Apply suppressions to findings
            active_findings = []
            suppressed_findings = []

            for finding in result.findings:
                if self.suppressions.is_path_suppressed(finding.file):
                    suppressed_findings.append(finding)
                elif finding.rule_id and self.suppressions.is_rule_suppressed(
                    finding.rule_id, finding.file
                ):
                    suppressed_findings.append(finding)
                else:
                    active_findings.append(finding)

            result.findings = active_findings
            result.suppressed = suppressed_findings

            # Emit completion progress
            if progress_callback:
                progress_callback(ProgressUpdate(
                    event=ProgressEvent.COMPLETED,
                    current=100,
                    total=100,
                    message=result.summary,
                    percentage=100.0,
                    elapsed_ms=result.timings.get("total_ms", 0),
                    metadata={"findings_count": len(result.findings)}
                ))

            return result

        except TimeoutError as e:
            elapsed = self.timeout_ms
            if progress_callback:
                progress_callback(ProgressUpdate(
                    event=ProgressEvent.ERROR,
                    current=0,
                    total=100,
                    message=f"Skill timed out after {self.timeout_ms}ms",
                    percentage=0.0,
                    elapsed_ms=elapsed
                ))
            return SkillResult(
                success=False,
                summary=f"Skill timed out after {self.timeout_ms}ms",
                run_id=run_id,
                timestamp=timestamp,
                errors=[str(e)],
                timings={"total_ms": self.timeout_ms}
            )
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            if progress_callback:
                progress_callback(ProgressUpdate(
                    event=ProgressEvent.ERROR,
                    current=0,
                    total=100,
                    message=f"Skill failed: {e}",
                    percentage=0.0,
                    elapsed_ms=elapsed
                ))
            return SkillResult(
                success=False,
                summary=f"Skill failed: {e}",
                run_id=run_id,
                timestamp=timestamp,
                errors=[str(e)],
                timings={"total_ms": elapsed}
            )

    def check_file_size(self, file_path: Path) -> bool:
        """Check if file is within size limits."""
        try:
            size_kb = file_path.stat().st_size / 1024
            return size_kb <= self.max_file_kb
        except Exception:
            return False

    def safe_read_file(self, file_path: Union[str, Path]) -> Optional[str]:
        """Safely read a file with all checks."""
        path = self.path_validator.validate(file_path)

        if not self.check_file_size(path):
            return None

        return path.read_text(encoding='utf-8')

    def run_with_pre_checks(
        self,
        skill_func: Callable[..., SkillResult],
        args: Dict[str, Any],
        pre_checks: List[str],
        schema: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        fail_fast: bool = True
    ) -> SkillResult:
        """
        Execute a skill with pre-checks.

        Args:
            skill_func: The skill function to execute
            args: Arguments to pass to the skill
            pre_checks: List of pre-checks to run before execution
            schema: Optional argument schema for validation
            progress_callback: Optional callback for progress updates
            fail_fast: If True, fail immediately on first pre-check failure

        Returns:
            SkillResult with standardized output
        """
        run_id = generate_run_id()
        timestamp = get_timestamp()
        start_time = time.time()

        # Run pre-checks
        if pre_checks:
            checker = get_pre_check_runner()
            failed_checks = []
            check_results = []

            for check in pre_checks:
                result = checker.run_check(check)
                check_results.append(result)

                if not result.passed:
                    failed_checks.append(result)
                    if fail_fast:
                        break

            if failed_checks:
                # Build error message
                error_messages = [f"{r.check_name}: {r.message}" for r in failed_checks]

                if progress_callback:
                    progress_callback(ProgressUpdate(
                        event=ProgressEvent.ERROR,
                        current=0,
                        total=100,
                        message=f"Pre-check failed: {failed_checks[0].message}",
                        percentage=0.0,
                        elapsed_ms=(time.time() - start_time) * 1000
                    ))

                return SkillResult(
                    success=False,
                    summary=f"Pre-checks failed: {'; '.join(error_messages)}",
                    run_id=run_id,
                    timestamp=timestamp,
                    errors=error_messages,
                    timings={"pre_checks_ms": (time.time() - start_time) * 1000}
                )

        # All pre-checks passed, run the skill
        return self.run(skill_func, args, schema, progress_callback)


# === Rule Engine ===

class RuleEngine:
    """
    Execute verification rules against code.

    Rules are data-only (RuleSpec), not executable code.
    This prevents arbitrary code execution in verifiers.
    """

    def __init__(self, runner: SkillRunner):
        self.runner = runner
        self._compiled_patterns: Dict[str, re.Pattern] = {}

    def _get_pattern(self, rule: RuleSpec) -> re.Pattern:
        """Get compiled regex pattern, with caching."""
        if rule.id not in self._compiled_patterns:
            self._compiled_patterns[rule.id] = re.compile(rule.pattern)
        return self._compiled_patterns[rule.id]

    def run_rule(
        self,
        rule: RuleSpec,
        file_path: Path,
        content: str
    ) -> CheckResult:
        """Execute a single rule against file content."""
        start = time.time()
        findings = []

        try:
            # Run with per-rule timeout
            def check():
                pattern = self._get_pattern(rule)
                lines = content.splitlines()

                for i, line in enumerate(lines, 1):
                    if pattern.search(line):
                        # Check inline suppression
                        if not self.runner.suppressions.is_rule_suppressed(
                            rule.id, str(file_path), line
                        ):
                            findings.append(Finding(
                                id=f"{rule.id}_{i}",
                                type="quality_violation",
                                severity=rule.severity,
                                confidence=rule.confidence,
                                file=str(file_path),
                                line=i,
                                snippet=line[:100] if len(line) > 100 else line,
                                message=rule.message,
                                suggested_fix=rule.suggested_fix,
                                rule_id=rule.id
                            ))

            run_with_timeout(check, rule.timeout_ms)

            return CheckResult(
                name=rule.name,
                success=len(findings) == 0,
                duration_ms=(time.time() - start) * 1000,
                findings=findings
            )

        except TimeoutError:
            return CheckResult(
                name=rule.name,
                success=False,
                duration_ms=rule.timeout_ms,
                error=f"Rule timed out after {rule.timeout_ms}ms"
            )
        except re.error as e:
            return CheckResult(
                name=rule.name,
                success=False,
                duration_ms=(time.time() - start) * 1000,
                error=f"Invalid regex pattern: {e}"
            )

    def run_rules(
        self,
        rules: List[RuleSpec],
        files: List[Path]
    ) -> List[CheckResult]:
        """Run multiple rules against multiple files."""
        results = []

        for rule in rules:
            rule_findings = []
            rule_start = time.time()

            for file_path in files:
                # Check scope
                rel_path = str(file_path)
                in_scope = any(
                    fnmatch.fnmatch(rel_path, pattern)
                    for pattern in rule.scope
                )
                if not in_scope:
                    continue

                # Check file size
                if not self.runner.check_file_size(file_path):
                    continue

                # Read and check
                content = self.runner.safe_read_file(file_path)
                if content:
                    result = self.run_rule(rule, file_path, content)
                    rule_findings.extend(result.findings)

            results.append(CheckResult(
                name=rule.name,
                success=len(rule_findings) == 0,
                duration_ms=(time.time() - rule_start) * 1000,
                findings=rule_findings
            ))

        return results


# CLI for testing
if __name__ == "__main__":
    print("Skill Runner - Ready")
    print(f"Allowed roots: {[str(r) for r in ALLOWED_ROOTS]}")

    # Test path validation
    print("\n=== Path Validation ===")
    validator = PathValidator()
    test_paths = [
        "C:/Users/sibag/Desktop/BUILD/msj/src/app.tsx",
        "C:/Users/sibag/../../../etc/passwd",
        "/etc/passwd",
    ]

    for p in test_paths:
        print(f"  {p}: {'SAFE' if validator.is_safe(p) else 'BLOCKED'}")

    # Test pre-checks
    print("\n=== Pre-Checks ===")
    checker = PreCheckRunner()

    # Test ffmpeg check
    ffmpeg_result = checker.run_check("ffmpeg_available")
    print(f"  ffmpeg: {'PASS' if ffmpeg_result.passed else 'FAIL'} - {ffmpeg_result.message}")

    # Test network check
    network_result = checker.run_check("network_available")
    print(f"  network: {'PASS' if network_result.passed else 'FAIL'} - {network_result.message}")

    # Test git repo check
    git_result = checker.run_check("git_repo")
    print(f"  git_repo: {'PASS' if git_result.passed else 'FAIL'} - {git_result.message}")

    # Test dependency check
    dep_result = checker.run_check("dependency_installed:pytest")
    print(f"  pytest: {'PASS' if dep_result.passed else 'FAIL'} - {dep_result.message}")

    # Test convenience function
    print("\n=== Batch Pre-Checks ===")
    all_passed, results = run_pre_checks(["ffmpeg_available", "network_available"])
    print(f"  All passed: {all_passed}")
    for r in results:
        print(f"    {r.check_name}: {'PASS' if r.passed else 'FAIL'}")
