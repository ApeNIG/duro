"""
Skill: code_pipeline
Description: Orchestrate code quality pipeline - review, coverage, test generation, auto-fix
Version: 1.1.0
Tier: tested

Pipeline orchestrator that runs code quality stages in sequence:
1. code_review: AST-based code review for issues and anti-patterns
2. test_coverage: Parse coverage reports and identify gaps
3. test_generate: Generate test stubs for uncovered/untested code
4. fix (optional): Auto-apply safe refactoring operations

Features:
- Single command to run full pipeline or individual stages
- --fix mode to auto-apply safe refactors (unused imports, sort imports)
- Unified report combining all stage results
- Priority-based file targeting (focus on worst files first)
- Project health score calculation
- CI-friendly JSON output

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function

Usage:
    result = run({
        "project_path": "/path/to/project",
        "stages": ["review", "coverage", "test_generate"],  # or "all"
        "fix": True,  # Auto-apply safe refactors
        "config": {
            "review": {"fail_on": "error"},
            "coverage": {"threshold": 80},
            "test_generate": {"max_files": 10},
            "fix": {"operations": ["remove_unused_imports", "sort_imports"]}
        }
    }, tools, context)
"""

import os
import sys
import json
import time
from pathlib import Path

# Add agent skills to path for imports
_agent_dir = Path(__file__).parent.parent.parent
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime


# Skill metadata
SKILL_META = {
    "name": "code_pipeline",
    "description": "Orchestrate code quality pipeline - review, coverage, test generation, auto-fix",
    "tier": "tested",
    "version": "1.1.2",
    "author": "duro",
    "phase": "4.4",
    "triggers": ["run pipeline", "code pipeline", "project health", "quality check", "fix code"],
}

# WARNING: Fix operations have known bugs with multi-line imports!
# They can corrupt files that use parenthesized imports like:
#   from typing import (
#       List,
#       Dict,
#   )
# These operations are DISABLED until the bugs are fixed.
# See: remove_unused_imports, sort_imports in code_refactor.py

SAFE_FIX_OPERATIONS = []  # DISABLED - was: ["remove_unused_imports", "sort_imports"]

# Operations that require confirmation (not auto-applied by default)
UNSAFE_FIX_OPERATIONS = [
    "remove_unused_imports",  # BUG: corrupts multi-line imports
    "sort_imports",           # BUG: corrupts multi-line imports
    "convert_to_fstring",
    "remove_dead_code",
]

# Required capabilities
REQUIRES = ["read_file", "glob_files", "write_file"]


class StageStatus(Enum):
    """Pipeline stage status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class StageResult:
    """Result from a pipeline stage."""
    stage: str
    status: StageStatus
    duration_ms: int
    summary: Dict[str, Any]
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Complete pipeline result."""
    project_path: str
    stages_run: List[str]
    stage_results: List[StageResult]
    health_score: float  # 0-100
    passed: bool
    total_duration_ms: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    recommendations: List[str] = field(default_factory=list)


# === Stage Runners ===

def run_code_review_stage(
    project_path: str,
    config: Dict[str, Any],
    tools: Dict[str, Any]
) -> StageResult:
    """Run code review stage."""
    start = time.time()

    try:
        # Import the skill
        from skills.verification.code_review_verifier import (
            run as run_review,
            Severity,
        )

        # Find Python files
        glob_files = tools.get("glob_files")
        if glob_files:
            files = glob_files(os.path.join(project_path, "**/*.py"))
        else:
            # Fallback: walk directory
            files = []
            for root, _, filenames in os.walk(project_path):
                for f in filenames:
                    if f.endswith(".py"):
                        files.append(os.path.join(root, f))

        # Filter out test files and virtual envs
        files = [
            f for f in files
            if not any(skip in f for skip in [
                "test_", "_test.py", "tests/", "__pycache__",
                "venv/", ".venv/", "site-packages/", "node_modules/"
            ])
        ]

        if not files:
            return StageResult(
                stage="code_review",
                status=StageStatus.SKIPPED,
                duration_ms=int((time.time() - start) * 1000),
                summary={"message": "No Python files found"},
            )

        # Run review
        result = run_review(
            args={
                "files": files,
                "config": config.get("review", {}),
                "fail_on": config.get("fail_on", "error"),
            },
            tools=tools,
            context={}
        )

        duration_ms = int((time.time() - start) * 1000)

        # Extract summary
        findings = result.get("findings", [])
        summary = {
            "files_reviewed": result.get("files_reviewed", len(files)),
            "total_findings": len(findings),
            "errors": sum(1 for f in findings if f.get("severity") == "error"),
            "warnings": sum(1 for f in findings if f.get("severity") == "warn"),
            "info": sum(1 for f in findings if f.get("severity") == "info"),
        }

        passed = result.get("passed", summary["errors"] == 0)

        return StageResult(
            stage="code_review",
            status=StageStatus.PASSED if passed else StageStatus.FAILED,
            duration_ms=duration_ms,
            summary=summary,
            details={"findings": findings[:50]},  # Limit for report size
        )

    except ImportError as e:
        return StageResult(
            stage="code_review",
            status=StageStatus.ERROR,
            duration_ms=int((time.time() - start) * 1000),
            summary={},
            error=f"Failed to import code_review_verifier: {e}",
        )
    except Exception as e:
        return StageResult(
            stage="code_review",
            status=StageStatus.ERROR,
            duration_ms=int((time.time() - start) * 1000),
            summary={},
            error=str(e),
        )


def run_test_coverage_stage(
    project_path: str,
    config: Dict[str, Any],
    tools: Dict[str, Any]
) -> StageResult:
    """Run test coverage stage."""
    start = time.time()

    try:
        from skills.verification.test_coverage_verifier import (
            run as run_coverage,
        )

        # Look for coverage report
        coverage_paths = [
            os.path.join(project_path, "coverage.xml"),
            os.path.join(project_path, "htmlcov", "coverage.xml"),
            os.path.join(project_path, ".coverage"),
            os.path.join(project_path, "coverage.json"),
            os.path.join(project_path, "lcov.info"),
        ]

        coverage_report = None
        for path in coverage_paths:
            if os.path.exists(path):
                coverage_report = path
                break

        if not coverage_report:
            return StageResult(
                stage="test_coverage",
                status=StageStatus.SKIPPED,
                duration_ms=int((time.time() - start) * 1000),
                summary={"message": "No coverage report found. Run pytest --cov to generate."},
            )

        # Run coverage verification
        result = run_coverage(
            args={
                "report_path": coverage_report,
                "threshold": config.get("coverage", {}).get("threshold", 80),
                "fail_under": config.get("coverage", {}).get("fail_under", 0),
            },
            tools=tools,
            context={}
        )

        duration_ms = int((time.time() - start) * 1000)

        summary = {
            "line_coverage": result.get("line_coverage", 0),
            "branch_coverage": result.get("branch_coverage"),
            "files_covered": result.get("files_covered", 0),
            "files_total": result.get("files_total", 0),
            "threshold_met": result.get("passed", False),
        }

        # Get uncovered files for test generation
        uncovered = result.get("uncovered_files", [])

        return StageResult(
            stage="test_coverage",
            status=StageStatus.PASSED if result.get("passed") else StageStatus.FAILED,
            duration_ms=duration_ms,
            summary=summary,
            details={"uncovered_files": uncovered[:20]},
        )

    except ImportError as e:
        return StageResult(
            stage="test_coverage",
            status=StageStatus.ERROR,
            duration_ms=int((time.time() - start) * 1000),
            summary={},
            error=f"Failed to import test_coverage_verifier: {e}",
        )
    except Exception as e:
        return StageResult(
            stage="test_coverage",
            status=StageStatus.ERROR,
            duration_ms=int((time.time() - start) * 1000),
            summary={},
            error=str(e),
        )


def run_test_generate_stage(
    project_path: str,
    config: Dict[str, Any],
    tools: Dict[str, Any],
    target_files: Optional[List[str]] = None
) -> StageResult:
    """Run test generation stage."""
    start = time.time()

    try:
        from skills.code.test_generate import run as run_test_gen

        # If no target files specified, find Python files in project
        if not target_files:
            glob_files = tools.get("glob_files")
            if glob_files:
                all_files = glob_files(os.path.join(project_path, "**/*.py"))
            else:
                all_files = []
                for root, _, filenames in os.walk(project_path):
                    for f in filenames:
                        if f.endswith(".py"):
                            all_files.append(os.path.join(root, f))

            # Filter to source files only (exclude tests, venvs, etc.)
            target_files = [
                f for f in all_files
                if not any(skip in f for skip in [
                    "test_", "_test.py", "tests/", "conftest.py",
                    "__pycache__", "venv/", ".venv/", "site-packages/",
                    "node_modules/", "__init__.py"
                ])
            ]

            # Limit files
            max_files = config.get("test_generate", {}).get("max_files", 10)
            target_files = target_files[:max_files]

        if not target_files:
            return StageResult(
                stage="test_generate",
                status=StageStatus.SKIPPED,
                duration_ms=int((time.time() - start) * 1000),
                summary={"message": "No files to generate tests for"},
            )

        # Generate tests for each file
        generated = []
        failed = []

        for file_path in target_files:
            try:
                result = run_test_gen(
                    args={
                        "source_path": file_path,
                        "framework": config.get("test_generate", {}).get("framework", "pytest"),
                        "include_edge_cases": config.get("test_generate", {}).get("edge_cases", False),
                    },
                    tools=tools,
                    config={}
                )

                if result.get("success"):
                    tests_list = result.get("tests_generated", [])
                    test_count = len(tests_list) if isinstance(tests_list, list) else 0
                    test_content = result.get("test_file_content", "")
                    generated.append({
                        "source": file_path,
                        "tests_generated": test_count,
                        "test_code": test_content[:500] if test_content else "",  # Preview
                    })
                else:
                    failed.append({
                        "source": file_path,
                        "error": result.get("error", "Unknown error"),
                    })

            except Exception as e:
                failed.append({
                    "source": file_path,
                    "error": str(e),
                })

        duration_ms = int((time.time() - start) * 1000)

        total_tests = sum(g.get("tests_generated", 0) for g in generated)

        summary = {
            "files_processed": len(target_files),
            "files_generated": len(generated),
            "files_failed": len(failed),
            "total_tests_generated": total_tests,
        }

        # Consider it passed if at least some tests were generated
        passed = len(generated) > 0

        return StageResult(
            stage="test_generate",
            status=StageStatus.PASSED if passed else StageStatus.FAILED,
            duration_ms=duration_ms,
            summary=summary,
            details={
                "generated": generated[:10],
                "failed": failed[:10],
            },
        )

    except ImportError as e:
        return StageResult(
            stage="test_generate",
            status=StageStatus.ERROR,
            duration_ms=int((time.time() - start) * 1000),
            summary={},
            error=f"Failed to import test_generate: {e}",
        )
    except Exception as e:
        return StageResult(
            stage="test_generate",
            status=StageStatus.ERROR,
            duration_ms=int((time.time() - start) * 1000),
            summary={},
            error=str(e),
        )


def run_fix_stage(
    project_path: str,
    config: Dict[str, Any],
    tools: Dict[str, Any],
    target_files: Optional[List[str]] = None,
    review_findings: Optional[List[Dict]] = None
) -> StageResult:
    """
    Run auto-fix stage - apply safe refactoring operations.

    Args:
        project_path: Path to project
        config: Fix configuration
        tools: Available tools
        target_files: Specific files to fix (if None, uses files from review)
        review_findings: Findings from code review stage
    """
    start = time.time()

    try:
        from skills.code.code_refactor import run as run_refactor

        # Determine which operations to run
        fix_config = config.get("fix", {})
        operations = fix_config.get("operations", SAFE_FIX_OPERATIONS)

        # Validate operations are safe
        for op in operations:
            if op not in SAFE_FIX_OPERATIONS and op not in UNSAFE_FIX_OPERATIONS:
                return StageResult(
                    stage="fix",
                    status=StageStatus.ERROR,
                    duration_ms=int((time.time() - start) * 1000),
                    summary={},
                    error=f"Unknown fix operation: {op}",
                )

        # Get files to fix
        if not target_files:
            # Find Python files in project
            glob_files = tools.get("glob_files")
            if glob_files:
                all_files = glob_files(os.path.join(project_path, "**/*.py"))
            else:
                all_files = []
                for root, _, filenames in os.walk(project_path):
                    for f in filenames:
                        if f.endswith(".py"):
                            all_files.append(os.path.join(root, f))

            # Filter to source files
            target_files = [
                f for f in all_files
                if not any(skip in f for skip in [
                    "test_", "_test.py", "conftest.py",
                    "__pycache__", "venv/", ".venv/", "site-packages/",
                    "node_modules/"
                ])
            ]

        if not target_files:
            return StageResult(
                stage="fix",
                status=StageStatus.SKIPPED,
                duration_ms=int((time.time() - start) * 1000),
                summary={"message": "No files to fix"},
            )

        # Apply each operation to each file
        fixed_files = []
        total_changes = 0
        errors = []

        for file_path in target_files:
            file_changes = 0

            for op in operations:
                try:
                    result = run_refactor(
                        args={
                            "source_path": file_path,
                            "operation": op,
                            "target": "",
                            "dry_run": False,  # Actually apply changes
                            "verify": False,
                        },
                        tools=tools,
                        config={}
                    )

                    changes = result.get("changes", [])
                    if result.get("success") and len(changes) > 0:
                        file_changes += len(changes)

                except Exception as e:
                    errors.append({
                        "file": os.path.basename(file_path),
                        "operation": op,
                        "error": str(e)[:50],
                    })

            if file_changes > 0:
                fixed_files.append({
                    "file": file_path,
                    "changes": file_changes,
                })
                total_changes += file_changes

        duration_ms = int((time.time() - start) * 1000)

        summary = {
            "files_scanned": len(target_files),
            "files_fixed": len(fixed_files),
            "total_changes": total_changes,
            "operations_applied": operations,
            "errors": len(errors),
        }

        return StageResult(
            stage="fix",
            status=StageStatus.PASSED if total_changes > 0 or len(errors) == 0 else StageStatus.FAILED,
            duration_ms=duration_ms,
            summary=summary,
            details={
                "fixed_files": fixed_files[:20],
                "errors": errors[:10],
            },
        )

    except ImportError as e:
        return StageResult(
            stage="fix",
            status=StageStatus.ERROR,
            duration_ms=int((time.time() - start) * 1000),
            summary={},
            error=f"Failed to import code_refactor: {e}",
        )
    except Exception as e:
        return StageResult(
            stage="fix",
            status=StageStatus.ERROR,
            duration_ms=int((time.time() - start) * 1000),
            summary={},
            error=str(e),
        )


# === Health Score Calculation ===

def calculate_health_score(stage_results: List[StageResult]) -> Tuple[float, List[str]]:
    """
    Calculate project health score (0-100) based on stage results.

    Scoring:
    - Code review: 40 points max
      - 40 points if passed with no errors
      - Deduct 5 per error, 1 per warning (min 0)
    - Test coverage: 40 points max
      - Points = coverage percentage * 0.4
    - Test generation: 20 points max
      - 20 points if tests generated successfully
      - 0 if skipped or failed
    """
    score = 0.0
    recommendations = []

    for result in stage_results:
        if result.stage == "code_review":
            if result.status == StageStatus.PASSED:
                # Start with full points, deduct for findings
                stage_score = 40.0
                errors = result.summary.get("errors", 0)
                warnings = result.summary.get("warnings", 0)
                stage_score -= (errors * 5 + warnings * 1)
                stage_score = max(0, stage_score)
                score += stage_score

                if errors > 0:
                    recommendations.append(f"Fix {errors} code review errors")
                if warnings > 5:
                    recommendations.append(f"Address {warnings} code review warnings")

            elif result.status == StageStatus.FAILED:
                errors = result.summary.get("errors", 0)
                recommendations.append(f"Critical: {errors} code review errors need fixing")

            elif result.status == StageStatus.ERROR:
                recommendations.append("Fix code review stage error")

        elif result.stage == "test_coverage":
            if result.status in [StageStatus.PASSED, StageStatus.FAILED]:
                coverage = result.summary.get("line_coverage", 0)
                stage_score = coverage * 0.4
                score += stage_score

                if coverage < 50:
                    recommendations.append(f"Increase test coverage (currently {coverage:.0f}%)")
                elif coverage < 80:
                    recommendations.append(f"Good coverage at {coverage:.0f}%, aim for 80%+")

            elif result.status == StageStatus.SKIPPED:
                recommendations.append("Generate coverage report: pytest --cov")

        elif result.stage == "test_generate":
            if result.status == StageStatus.PASSED:
                tests_generated = result.summary.get("total_tests_generated", 0)
                if tests_generated > 0:
                    score += 20
                else:
                    score += 10
                    recommendations.append("Review generated test stubs")

            elif result.status == StageStatus.SKIPPED:
                score += 10  # Partial credit if nothing to generate

    return min(100, score), recommendations


# === Report Generation ===

def generate_report(result: PipelineResult, format: str = "text") -> str:
    """Generate pipeline report in specified format."""

    if format == "json":
        return json.dumps(asdict(result), indent=2, default=str)

    # Text format
    lines = [
        "=" * 60,
        "CODE PIPELINE REPORT",
        "=" * 60,
        f"Project: {result.project_path}",
        f"Timestamp: {result.timestamp}",
        f"Duration: {result.total_duration_ms}ms",
        "",
        f"HEALTH SCORE: {result.health_score:.0f}/100",
        f"Status: {'PASSED' if result.passed else 'NEEDS ATTENTION'}",
        "",
        "-" * 60,
        "STAGE RESULTS",
        "-" * 60,
    ]

    for stage_result in result.stage_results:
        status_icon = {
            StageStatus.PASSED: "[PASS]",
            StageStatus.FAILED: "[FAIL]",
            StageStatus.SKIPPED: "[SKIP]",
            StageStatus.ERROR: "[ERR!]",
        }.get(stage_result.status, "[????]")

        lines.append(f"\n{status_icon} {stage_result.stage.upper()} ({stage_result.duration_ms}ms)")

        for key, value in stage_result.summary.items():
            lines.append(f"  {key}: {value}")

        if stage_result.error:
            lines.append(f"  ERROR: {stage_result.error}")

    if result.recommendations:
        lines.extend([
            "",
            "-" * 60,
            "RECOMMENDATIONS",
            "-" * 60,
        ])
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"  {i}. {rec}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


# === Main Entry Point ===

def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            project_path: str - path to project root
            stages: List[str] or "all" - stages to run
            fix: bool - whether to run auto-fix stage
            config: Dict - stage-specific configuration
            output_format: str - "text" or "json"
            write_report: bool - whether to write report file
        }
        tools: {
            read_file: callable
            glob_files: callable
            write_file: callable
        }
        context: {run_id, etc.}

    Returns:
        {
            success: bool,
            passed: bool - whether pipeline passed
            health_score: float - 0-100 score
            report: str - formatted report
            stage_results: List[dict] - individual stage results
        }
    """
    start_time = time.time()

    project_path = args.get("project_path", ".")
    stages = args.get("stages", "all")
    fix_mode = args.get("fix", False)
    config = args.get("config", {})
    output_format = args.get("output_format", "text")
    write_report = args.get("write_report", False)

    # Normalize project path
    project_path = os.path.abspath(project_path)

    if not os.path.isdir(project_path):
        return {
            "success": False,
            "error": f"Project path does not exist: {project_path}",
        }

    # Determine which stages to run
    all_stages = ["code_review", "test_coverage", "test_generate", "fix"]

    if stages == "all":
        # "all" doesn't include fix by default - must be explicitly requested
        stages_to_run = ["code_review", "test_coverage", "test_generate"]
    elif isinstance(stages, str):
        stages_to_run = [stages]
    else:
        stages_to_run = stages

    # Add fix stage if --fix mode enabled and not already in stages
    if fix_mode and "fix" not in stages_to_run:
        stages_to_run.append("fix")

    # Validate stages
    for stage in stages_to_run:
        if stage not in all_stages:
            return {
                "success": False,
                "error": f"Unknown stage: {stage}. Valid: {all_stages}",
            }

    # Run stages
    stage_results = []
    uncovered_files = []
    review_findings = []

    for stage in stages_to_run:
        if stage == "code_review":
            result = run_code_review_stage(project_path, config, tools)
            # Capture findings for fix stage
            if result.details:
                review_findings = result.details.get("findings", [])

        elif stage == "test_coverage":
            result = run_test_coverage_stage(project_path, config, tools)
            # Capture uncovered files for test generation
            if result.details:
                uncovered_files = result.details.get("uncovered_files", [])

        elif stage == "test_generate":
            # Use uncovered files from coverage stage if available
            target_files = uncovered_files if uncovered_files else None
            result = run_test_generate_stage(project_path, config, tools, target_files)

        elif stage == "fix":
            # Run auto-fix on project files
            result = run_fix_stage(project_path, config, tools, None, review_findings)

        stage_results.append(result)

    # Calculate health score
    health_score, recommendations = calculate_health_score(stage_results)

    # Determine overall pass/fail
    passed = all(
        r.status in [StageStatus.PASSED, StageStatus.SKIPPED]
        for r in stage_results
    )

    total_duration = int((time.time() - start_time) * 1000)

    # Build result
    pipeline_result = PipelineResult(
        project_path=project_path,
        stages_run=stages_to_run,
        stage_results=stage_results,
        health_score=health_score,
        passed=passed,
        total_duration_ms=total_duration,
        recommendations=recommendations,
    )

    # Generate report
    report = generate_report(pipeline_result, output_format)

    # Optionally write report file
    if write_report:
        write_file = tools.get("write_file")
        if write_file:
            report_path = os.path.join(project_path, "pipeline_report.txt")
            write_file(report_path, report)

    return {
        "success": True,
        "passed": passed,
        "health_score": health_score,
        "report": report,
        "stage_results": [
            {
                "stage": r.stage,
                "status": r.status.value,
                "duration_ms": r.duration_ms,
                "summary": r.summary,
                "error": r.error,
            }
            for r in stage_results
        ],
        "recommendations": recommendations,
    }


# === CLI Interface ===

def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run code quality pipeline on a project"
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Path to project root"
    )
    parser.add_argument(
        "--stages",
        nargs="+",
        default=["all"],
        choices=["all", "code_review", "test_coverage", "test_generate", "fix"],
        help="Stages to run"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-apply safe refactoring (remove unused imports, sort imports)"
    )
    parser.add_argument(
        "--fix-operations",
        nargs="+",
        default=["remove_unused_imports", "sort_imports"],
        choices=["remove_unused_imports", "sort_imports", "convert_to_fstring", "remove_dead_code"],
        help="Fix operations to apply (default: safe operations only)"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--fail-on",
        choices=["error", "warn", "info"],
        default="error",
        help="Severity level that causes failure"
    )
    parser.add_argument(
        "--coverage-threshold",
        type=int,
        default=80,
        help="Minimum coverage percentage"
    )
    parser.add_argument(
        "--max-test-files",
        type=int,
        default=10,
        help="Maximum files to generate tests for"
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write report to pipeline_report.txt"
    )

    args = parser.parse_args()

    # Build config
    config = {
        "fail_on": args.fail_on,
        "coverage": {"threshold": args.coverage_threshold},
        "test_generate": {"max_files": args.max_test_files},
        "fix": {"operations": args.fix_operations},
    }

    stages = args.stages[0] if args.stages == ["all"] else args.stages

    # Simple tools for CLI mode
    def read_file(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def glob_files(pattern):
        from glob import glob
        return glob(pattern, recursive=True)

    def write_file(path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    tools = {
        "read_file": read_file,
        "glob_files": glob_files,
        "write_file": write_file,
    }

    result = run(
        args={
            "project_path": args.project_path,
            "stages": stages,
            "fix": args.fix,
            "config": config,
            "output_format": args.format,
            "write_report": args.write_report,
        },
        tools=tools,
        context={}
    )

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(result.get("report", ""))

    sys.exit(0 if result.get("passed") else 1)


if __name__ == "__main__":
    main()
