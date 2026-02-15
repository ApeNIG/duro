"""
Skill Runner - The spine for all Duro skill execution.

Core responsibilities:
1. Validate skill arguments against schema
2. Enforce path allowlist (security)
3. Enforce file size limits and timeouts
4. Standardize all results

Every skill runs through this. It's the trust layer.
"""

import os
import re
import time
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union
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


class Severity(Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


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
        schema: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """
        Execute a skill with all guardrails.

        Args:
            skill_func: The skill function to execute
            args: Arguments to pass to the skill
            schema: Optional argument schema for validation

        Returns:
            SkillResult with standardized output
        """
        run_id = generate_run_id()
        timestamp = get_timestamp()
        start_time = time.time()

        # Validate arguments
        if schema:
            validation_errors = validate_args(args, schema)
            if validation_errors:
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

            return result

        except TimeoutError as e:
            return SkillResult(
                success=False,
                summary=f"Skill timed out after {self.timeout_ms}ms",
                run_id=run_id,
                timestamp=timestamp,
                errors=[str(e)],
                timings={"total_ms": self.timeout_ms}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                summary=f"Skill failed: {e}",
                run_id=run_id,
                timestamp=timestamp,
                errors=[str(e)],
                timings={"total_ms": (time.time() - start_time) * 1000}
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
    validator = PathValidator()
    test_paths = [
        "C:/Users/sibag/Desktop/BUILD/msj/src/app.tsx",
        "C:/Users/sibag/../../../etc/passwd",
        "/etc/passwd",
    ]

    for p in test_paths:
        print(f"  {p}: {'SAFE' if validator.is_safe(p) else 'BLOCKED'}")
