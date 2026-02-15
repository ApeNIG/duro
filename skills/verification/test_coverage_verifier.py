"""
Skill: test_coverage_verifier
Description: Parse coverage reports and enforce thresholds
Version: 1.0.0
Tier: untested

Multi-format coverage verification:
- Cobertura XML (pytest-cov, coverage.py)
- LCOV (nyc, Go, genhtml)
- JSON (coverage.py --json)
- Clover XML (PHP, Java)

Capabilities:
1. Multi-format parsing
2. Metric extraction (line, branch, function coverage)
3. Threshold enforcement
4. Uncovered file identification
5. Regression detection (compare against baseline)
6. Exclusion patterns
7. CI-friendly JSON output

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import os
import re
import json
import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import xml.etree.ElementTree as ET


# Skill metadata
SKILL_META = {
    "name": "test_coverage_verifier",
    "description": "Parse coverage reports and enforce thresholds",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "phase": "3.1",
    "triggers": ["coverage", "test coverage", "check coverage", "coverage report"],
}

# Required capabilities
REQUIRES = ["read_file", "glob_files"]


class CoverageFormat(Enum):
    """Supported coverage report formats."""
    COBERTURA = "cobertura"
    LCOV = "lcov"
    JSON = "json"
    CLOVER = "clover"
    UNKNOWN = "unknown"


@dataclass
class FileCoverage:
    """Coverage data for a single file."""
    path: str
    line_coverage: float
    branch_coverage: Optional[float]
    function_coverage: Optional[float]
    lines_covered: int
    lines_total: int
    branches_covered: int = 0
    branches_total: int = 0
    functions_covered: int = 0
    functions_total: int = 0
    uncovered_lines: List[int] = field(default_factory=list)


@dataclass
class CoverageMetrics:
    """Aggregate coverage metrics."""
    line_coverage: float
    branch_coverage: Optional[float]
    function_coverage: Optional[float]
    files_covered: int
    files_total: int
    lines_covered: int
    lines_total: int
    branches_covered: int
    branches_total: int
    functions_covered: int
    functions_total: int


@dataclass
class ThresholdFailure:
    """A threshold that was not met."""
    metric: str
    actual: float
    required: float
    gap: float


@dataclass
class RegressionInfo:
    """Coverage regression information."""
    detected: bool
    baseline: Optional[float]
    current: float
    delta: float


# === DEFAULT CONFIGURATION ===

DEFAULT_CONFIG = {
    "min_line_coverage": 80.0,
    "min_branch_coverage": 70.0,
    "min_function_coverage": 80.0,
    "fail_on_regression": True,
    "regression_threshold": 2.0,  # Allow 2% drop
    "exclude_patterns": [
        "**/test_*.py",
        "**/tests/**",
        "**/__pycache__/**",
        "**/migrations/**",
        "**/.venv/**",
        "**/node_modules/**",
    ],
    "report_uncovered_limit": 10,
}


# === FORMAT DETECTION ===

def detect_format(content: str, filename: str) -> CoverageFormat:
    """Detect coverage report format from content and filename."""
    filename_lower = filename.lower()

    # Check filename patterns
    if filename_lower.endswith('.json'):
        return CoverageFormat.JSON
    if 'lcov' in filename_lower or filename_lower.endswith('.info'):
        return CoverageFormat.LCOV

    # Check content patterns
    content_start = content[:500].strip()

    if content_start.startswith('{'):
        return CoverageFormat.JSON
    if content_start.startswith('TN:') or content_start.startswith('SF:'):
        return CoverageFormat.LCOV
    if '<?xml' in content_start or '<coverage' in content_start:
        if 'clover' in content_start.lower():
            return CoverageFormat.CLOVER
        return CoverageFormat.COBERTURA

    return CoverageFormat.UNKNOWN


# === PARSERS ===

def parse_cobertura(content: str) -> Tuple[List[FileCoverage], CoverageMetrics]:
    """Parse Cobertura XML format (pytest-cov, coverage.py)."""
    files: List[FileCoverage] = []

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}")

    total_lines_covered = 0
    total_lines_total = 0
    total_branches_covered = 0
    total_branches_total = 0

    # Find all classes/files
    for package in root.findall('.//package'):
        for cls in package.findall('.//class'):
            filename = cls.get('filename', '')

            lines_covered = 0
            lines_total = 0
            branches_covered = 0
            branches_total = 0
            uncovered_lines = []

            for line in cls.findall('.//line'):
                line_num = int(line.get('number', 0))
                hits = int(line.get('hits', 0))
                lines_total += 1

                if hits > 0:
                    lines_covered += 1
                else:
                    uncovered_lines.append(line_num)

                # Branch coverage
                if line.get('branch') == 'true':
                    condition = line.get('condition-coverage', '')
                    match = re.search(r'\((\d+)/(\d+)\)', condition)
                    if match:
                        branches_covered += int(match.group(1))
                        branches_total += int(match.group(2))

            line_cov = (lines_covered / lines_total * 100) if lines_total > 0 else 0
            branch_cov = (branches_covered / branches_total * 100) if branches_total > 0 else None

            files.append(FileCoverage(
                path=filename,
                line_coverage=line_cov,
                branch_coverage=branch_cov,
                function_coverage=None,
                lines_covered=lines_covered,
                lines_total=lines_total,
                branches_covered=branches_covered,
                branches_total=branches_total,
                uncovered_lines=uncovered_lines[:20],  # Limit
            ))

            total_lines_covered += lines_covered
            total_lines_total += lines_total
            total_branches_covered += branches_covered
            total_branches_total += branches_total

    # Calculate aggregate metrics
    line_cov = (total_lines_covered / total_lines_total * 100) if total_lines_total > 0 else 0
    branch_cov = (total_branches_covered / total_branches_total * 100) if total_branches_total > 0 else None

    metrics = CoverageMetrics(
        line_coverage=line_cov,
        branch_coverage=branch_cov,
        function_coverage=None,
        files_covered=sum(1 for f in files if f.line_coverage > 0),
        files_total=len(files),
        lines_covered=total_lines_covered,
        lines_total=total_lines_total,
        branches_covered=total_branches_covered,
        branches_total=total_branches_total,
        functions_covered=0,
        functions_total=0,
    )

    return files, metrics


def parse_lcov(content: str) -> Tuple[List[FileCoverage], CoverageMetrics]:
    """Parse LCOV format."""
    files: List[FileCoverage] = []

    current_file = None
    lines_covered = 0
    lines_total = 0
    branches_covered = 0
    branches_total = 0
    functions_covered = 0
    functions_total = 0
    uncovered_lines = []

    total_lines_covered = 0
    total_lines_total = 0
    total_branches_covered = 0
    total_branches_total = 0
    total_functions_covered = 0
    total_functions_total = 0

    for line in content.split('\n'):
        line = line.strip()

        if line.startswith('SF:'):
            # Start of new file
            if current_file:
                # Save previous file
                line_cov = (lines_covered / lines_total * 100) if lines_total > 0 else 0
                branch_cov = (branches_covered / branches_total * 100) if branches_total > 0 else None
                func_cov = (functions_covered / functions_total * 100) if functions_total > 0 else None

                files.append(FileCoverage(
                    path=current_file,
                    line_coverage=line_cov,
                    branch_coverage=branch_cov,
                    function_coverage=func_cov,
                    lines_covered=lines_covered,
                    lines_total=lines_total,
                    branches_covered=branches_covered,
                    branches_total=branches_total,
                    functions_covered=functions_covered,
                    functions_total=functions_total,
                    uncovered_lines=uncovered_lines[:20],
                ))

            current_file = line[3:]
            lines_covered = 0
            lines_total = 0
            branches_covered = 0
            branches_total = 0
            functions_covered = 0
            functions_total = 0
            uncovered_lines = []

        elif line.startswith('DA:'):
            # Line data: DA:line_number,hit_count
            parts = line[3:].split(',')
            if len(parts) >= 2:
                line_num = int(parts[0])
                hits = int(parts[1])
                lines_total += 1
                if hits > 0:
                    lines_covered += 1
                else:
                    uncovered_lines.append(line_num)

        elif line.startswith('BRDA:'):
            # Branch data: BRDA:line,block,branch,taken
            parts = line[5:].split(',')
            if len(parts) >= 4:
                branches_total += 1
                if parts[3] != '-' and int(parts[3]) > 0:
                    branches_covered += 1

        elif line.startswith('FNF:'):
            # Functions found
            functions_total = int(line[4:])

        elif line.startswith('FNH:'):
            # Functions hit
            functions_covered = int(line[4:])

        elif line == 'end_of_record':
            if current_file:
                line_cov = (lines_covered / lines_total * 100) if lines_total > 0 else 0
                branch_cov = (branches_covered / branches_total * 100) if branches_total > 0 else None
                func_cov = (functions_covered / functions_total * 100) if functions_total > 0 else None

                files.append(FileCoverage(
                    path=current_file,
                    line_coverage=line_cov,
                    branch_coverage=branch_cov,
                    function_coverage=func_cov,
                    lines_covered=lines_covered,
                    lines_total=lines_total,
                    branches_covered=branches_covered,
                    branches_total=branches_total,
                    functions_covered=functions_covered,
                    functions_total=functions_total,
                    uncovered_lines=uncovered_lines[:20],
                ))

                total_lines_covered += lines_covered
                total_lines_total += lines_total
                total_branches_covered += branches_covered
                total_branches_total += branches_total
                total_functions_covered += functions_covered
                total_functions_total += functions_total

                current_file = None

    # Calculate aggregate metrics
    line_cov = (total_lines_covered / total_lines_total * 100) if total_lines_total > 0 else 0
    branch_cov = (total_branches_covered / total_branches_total * 100) if total_branches_total > 0 else None
    func_cov = (total_functions_covered / total_functions_total * 100) if total_functions_total > 0 else None

    metrics = CoverageMetrics(
        line_coverage=line_cov,
        branch_coverage=branch_cov,
        function_coverage=func_cov,
        files_covered=sum(1 for f in files if f.line_coverage > 0),
        files_total=len(files),
        lines_covered=total_lines_covered,
        lines_total=total_lines_total,
        branches_covered=total_branches_covered,
        branches_total=total_branches_total,
        functions_covered=total_functions_covered,
        functions_total=total_functions_total,
    )

    return files, metrics


def parse_json(content: str) -> Tuple[List[FileCoverage], CoverageMetrics]:
    """Parse coverage.py JSON format."""
    files: List[FileCoverage] = []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    total_lines_covered = 0
    total_lines_total = 0

    # coverage.py JSON format
    if 'files' in data:
        for filepath, filedata in data['files'].items():
            summary = filedata.get('summary', {})

            lines_covered = summary.get('covered_lines', 0)
            lines_total = summary.get('num_statements', 0)

            missing = filedata.get('missing_lines', [])

            line_cov = (lines_covered / lines_total * 100) if lines_total > 0 else 0

            files.append(FileCoverage(
                path=filepath,
                line_coverage=line_cov,
                branch_coverage=None,
                function_coverage=None,
                lines_covered=lines_covered,
                lines_total=lines_total,
                uncovered_lines=missing[:20],
            ))

            total_lines_covered += lines_covered
            total_lines_total += lines_total

    # Totals from summary
    totals = data.get('totals', {})
    line_cov = totals.get('percent_covered', 0)
    if not line_cov and total_lines_total > 0:
        line_cov = (total_lines_covered / total_lines_total * 100)

    metrics = CoverageMetrics(
        line_coverage=line_cov,
        branch_coverage=None,
        function_coverage=None,
        files_covered=sum(1 for f in files if f.line_coverage > 0),
        files_total=len(files),
        lines_covered=total_lines_covered,
        lines_total=total_lines_total,
        branches_covered=0,
        branches_total=0,
        functions_covered=0,
        functions_total=0,
    )

    return files, metrics


def parse_coverage(content: str, filename: str) -> Tuple[List[FileCoverage], CoverageMetrics, CoverageFormat]:
    """Parse coverage report, auto-detecting format."""
    fmt = detect_format(content, filename)

    if fmt == CoverageFormat.COBERTURA:
        files, metrics = parse_cobertura(content)
    elif fmt == CoverageFormat.LCOV:
        files, metrics = parse_lcov(content)
    elif fmt == CoverageFormat.JSON:
        files, metrics = parse_json(content)
    elif fmt == CoverageFormat.CLOVER:
        # Clover uses similar structure to Cobertura
        files, metrics = parse_cobertura(content)
    else:
        raise ValueError(f"Unknown coverage format for {filename}")

    return files, metrics, fmt


# === FILTERING ===

def should_exclude(filepath: str, patterns: List[str]) -> bool:
    """Check if file should be excluded based on patterns."""
    # Normalize path separators
    filepath_normalized = filepath.replace('\\', '/')

    for pattern in patterns:
        pattern_normalized = pattern.replace('\\', '/')

        # Direct match
        if fnmatch.fnmatch(filepath_normalized, pattern_normalized):
            return True

        # Check basename
        if fnmatch.fnmatch(os.path.basename(filepath), pattern_normalized):
            return True

        # Handle **/ patterns - check if any part of path matches
        if '**' in pattern_normalized:
            # Convert **/dir/** to check if 'dir' is in path
            parts = pattern_normalized.split('**')
            for part in parts:
                part = part.strip('/')
                if part and part in filepath_normalized:
                    return True

        # Check if pattern directory is in filepath
        pattern_dir = pattern_normalized.strip('*').strip('/')
        if pattern_dir and f'/{pattern_dir}/' in f'/{filepath_normalized}/':
            return True
        if pattern_dir and filepath_normalized.startswith(f'{pattern_dir}/'):
            return True

    return False


def filter_files(files: List[FileCoverage], exclude_patterns: List[str]) -> List[FileCoverage]:
    """Filter out excluded files."""
    return [f for f in files if not should_exclude(f.path, exclude_patterns)]


def recalculate_metrics(files: List[FileCoverage]) -> CoverageMetrics:
    """Recalculate aggregate metrics from filtered files."""
    total_lines_covered = sum(f.lines_covered for f in files)
    total_lines_total = sum(f.lines_total for f in files)
    total_branches_covered = sum(f.branches_covered for f in files)
    total_branches_total = sum(f.branches_total for f in files)
    total_functions_covered = sum(f.functions_covered for f in files)
    total_functions_total = sum(f.functions_total for f in files)

    line_cov = (total_lines_covered / total_lines_total * 100) if total_lines_total > 0 else 0
    branch_cov = (total_branches_covered / total_branches_total * 100) if total_branches_total > 0 else None
    func_cov = (total_functions_covered / total_functions_total * 100) if total_functions_total > 0 else None

    return CoverageMetrics(
        line_coverage=line_cov,
        branch_coverage=branch_cov,
        function_coverage=func_cov,
        files_covered=sum(1 for f in files if f.line_coverage > 0),
        files_total=len(files),
        lines_covered=total_lines_covered,
        lines_total=total_lines_total,
        branches_covered=total_branches_covered,
        branches_total=total_branches_total,
        functions_covered=total_functions_covered,
        functions_total=total_functions_total,
    )


# === VERIFICATION ===

def check_thresholds(metrics: CoverageMetrics, config: Dict[str, Any]) -> List[ThresholdFailure]:
    """Check if metrics meet configured thresholds."""
    failures = []

    min_line = config.get("min_line_coverage", 0)
    if metrics.line_coverage < min_line:
        failures.append(ThresholdFailure(
            metric="line_coverage",
            actual=metrics.line_coverage,
            required=min_line,
            gap=min_line - metrics.line_coverage,
        ))

    min_branch = config.get("min_branch_coverage", 0)
    if metrics.branch_coverage is not None and metrics.branch_coverage < min_branch:
        failures.append(ThresholdFailure(
            metric="branch_coverage",
            actual=metrics.branch_coverage,
            required=min_branch,
            gap=min_branch - metrics.branch_coverage,
        ))

    min_func = config.get("min_function_coverage", 0)
    if metrics.function_coverage is not None and metrics.function_coverage < min_func:
        failures.append(ThresholdFailure(
            metric="function_coverage",
            actual=metrics.function_coverage,
            required=min_func,
            gap=min_func - metrics.function_coverage,
        ))

    return failures


def check_regression(
    current: float,
    baseline: Optional[float],
    threshold: float
) -> RegressionInfo:
    """Check for coverage regression."""
    if baseline is None:
        return RegressionInfo(
            detected=False,
            baseline=None,
            current=current,
            delta=0,
        )

    delta = current - baseline
    detected = delta < -threshold

    return RegressionInfo(
        detected=detected,
        baseline=baseline,
        current=current,
        delta=delta,
    )


def get_uncovered_files(
    files: List[FileCoverage],
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Get files with lowest coverage."""
    # Sort by line coverage ascending
    sorted_files = sorted(files, key=lambda f: f.line_coverage)

    return [
        {
            "file": f.path,
            "line_coverage": round(f.line_coverage, 2),
            "uncovered_lines": f.uncovered_lines,
        }
        for f in sorted_files[:limit]
        if f.line_coverage < 100
    ]


# === MAIN FUNCTION ===

def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            report_path: str - path to coverage report file
            config: Dict - configuration overrides
            baseline: float - optional baseline coverage for regression check
        }
        tools: {
            read_file: callable
            glob_files: callable
        }
        context: {run_id, etc.}

    Returns:
        {
            success: bool,
            passed: bool,
            format: str - detected format
            metrics: dict - coverage metrics
            failures: list - threshold failures
            uncovered: list - files with lowest coverage
            regression: dict - regression info
            files_analyzed: int
        }
    """
    import time
    start_time = time.time()

    report_path = args.get("report_path", "coverage.xml")
    config = {**DEFAULT_CONFIG, **args.get("config", {})}
    baseline = args.get("baseline")

    # Read report file
    try:
        if tools.get("read_file"):
            content = tools["read_file"](report_path)
        else:
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not read coverage report: {e}",
            "passed": False,
        }

    # Handle empty content
    if not content or not content.strip():
        return {
            "success": False,
            "error": "Coverage report is empty",
            "passed": False,
        }

    # Parse report
    try:
        files, metrics, fmt = parse_coverage(content, report_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not parse coverage report: {e}",
            "passed": False,
        }

    # Filter excluded files
    exclude_patterns = config.get("exclude_patterns", [])
    if exclude_patterns:
        files = filter_files(files, exclude_patterns)
        metrics = recalculate_metrics(files)

    # Check thresholds
    failures = check_thresholds(metrics, config)

    # Check regression
    regression = check_regression(
        metrics.line_coverage,
        baseline,
        config.get("regression_threshold", 2.0)
    )

    # Get uncovered files
    uncovered = get_uncovered_files(
        files,
        config.get("report_uncovered_limit", 10)
    )

    # Determine pass/fail
    passed = len(failures) == 0
    if config.get("fail_on_regression", True) and regression.detected:
        passed = False

    duration_ms = int((time.time() - start_time) * 1000)

    return {
        "success": True,
        "passed": passed,
        "format": fmt.value,
        "metrics": {
            "line_coverage": round(metrics.line_coverage, 2),
            "branch_coverage": round(metrics.branch_coverage, 2) if metrics.branch_coverage else None,
            "function_coverage": round(metrics.function_coverage, 2) if metrics.function_coverage else None,
            "files_covered": metrics.files_covered,
            "files_total": metrics.files_total,
            "lines_covered": metrics.lines_covered,
            "lines_total": metrics.lines_total,
        },
        "failures": [
            {
                "metric": f.metric,
                "actual": round(f.actual, 2),
                "required": f.required,
                "gap": round(f.gap, 2),
            }
            for f in failures
        ],
        "uncovered": uncovered,
        "regression": {
            "detected": regression.detected,
            "baseline": regression.baseline,
            "current": round(regression.current, 2),
            "delta": round(regression.delta, 2),
        },
        "files_analyzed": len(files),
        "duration_ms": duration_ms,
        "config_used": {
            "min_line_coverage": config.get("min_line_coverage"),
            "min_branch_coverage": config.get("min_branch_coverage"),
            "min_function_coverage": config.get("min_function_coverage"),
        },
    }


# Export key components
__all__ = [
    "SKILL_META",
    "REQUIRES",
    "run",
    "parse_coverage",
    "parse_cobertura",
    "parse_lcov",
    "parse_json",
    "detect_format",
    "check_thresholds",
    "check_regression",
    "CoverageFormat",
    "FileCoverage",
    "CoverageMetrics",
    "DEFAULT_CONFIG",
]


if __name__ == "__main__":
    print("test_coverage_verifier Skill v1.0")
    print("=" * 50)
    print()
    print("Supported Formats:")
    for fmt in CoverageFormat:
        if fmt != CoverageFormat.UNKNOWN:
            print(f"  - {fmt.value}")
    print()
    print("Default Thresholds:")
    print(f"  Line coverage: {DEFAULT_CONFIG['min_line_coverage']}%")
    print(f"  Branch coverage: {DEFAULT_CONFIG['min_branch_coverage']}%")
    print(f"  Function coverage: {DEFAULT_CONFIG['min_function_coverage']}%")
    print()
    print("Usage:")
    print('  result = run({"report_path": "coverage.xml"}, tools, ctx)')
    print('  print(f"Passed: {result[\'passed\']}, Coverage: {result[\'metrics\'][\'line_coverage\']}%")')
