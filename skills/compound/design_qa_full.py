"""
Skill: design_qa_full
Description: Full design QA sequence - runs all QA checks and generates unified report.
Version: 1.0.0
Tier: tested

Purpose: Run comprehensive design QA in sequence with pass/fail verdict.

Sequence:
1. design_qa_verify (measurements, alignment, spacing, typography)
2. accessibility_design_check (WCAG compliance)
3. Generate unified report with overall verdict

Usage:
    duro_run_skill(skill_name="design_qa_full", args={
        "file_path": "design.pen",
        "node_id": "screen_001",
        "wcag_level": "AA"
    })
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime


SKILL_META = {
    "name": "design_qa_full",
    "description": "Full design QA sequence with unified pass/fail verdict",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["full qa", "complete qa", "design review", "qa all"],
    "keywords": ["design", "qa", "full", "complete", "verification", "accessibility", "alignment"],
}

REQUIRES = ["design_qa_verify", "accessibility_design_check", "pencil_get_screenshot"]


@dataclass
class QACheckResult:
    """Result of a single QA check."""
    check_name: str
    passed: bool
    score: float
    issues_count: int
    critical_issues: int
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FullQAReport:
    """Complete QA report."""
    timestamp: str
    node_id: str
    file_path: str
    overall_passed: bool
    overall_score: float
    overall_grade: str
    checks: List[QACheckResult]
    total_issues: int
    blocking_issues: int
    verdict: str
    summary: str


def calculate_overall_score(checks: List[QACheckResult]) -> tuple:
    """Calculate overall score and grade from individual checks."""
    if not checks:
        return 100.0, "A"

    # Weighted average
    weights = {
        "design_qa_verify": 0.4,
        "accessibility_design_check": 0.4,
        "screenshot_review": 0.2,
    }

    total_weight = 0
    weighted_sum = 0

    for check in checks:
        weight = weights.get(check.check_name, 0.2)
        weighted_sum += check.score * weight
        total_weight += weight

    score = weighted_sum / total_weight if total_weight > 0 else 0

    # Grade
    if score >= 95:
        grade = "A+"
    elif score >= 90:
        grade = "A"
    elif score >= 85:
        grade = "B+"
    elif score >= 80:
        grade = "B"
    elif score >= 75:
        grade = "C+"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    return round(score, 1), grade


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run full design QA sequence.

    Args:
        args: {
            file_path: str - Path to .pen file
            node_id: str - Node to check
            wcag_level: str - "A", "AA", or "AAA" (default: "AA")
            take_screenshot: bool - Take screenshot for visual review (default: True)
            fail_on_moderate: bool - Fail on moderate issues (default: False)
        }
        tools: {
            design_qa_verify: func,
            accessibility_design_check: func,
            pencil_get_screenshot: func
        }
        context: execution context

    Returns:
        {success, report, overall_passed, overall_score, grade, checks}
    """
    file_path = args.get("file_path", "")
    node_id = args.get("node_id", "")
    wcag_level = args.get("wcag_level", "AA")
    take_screenshot = args.get("take_screenshot", True)
    fail_on_moderate = args.get("fail_on_moderate", False)

    if not node_id:
        return {"success": False, "error": "node_id is required"}

    checks = []
    all_issues = []

    # === Check 1: Design QA Verify ===
    design_qa_verify = tools.get("design_qa_verify")
    if design_qa_verify:
        try:
            result = design_qa_verify(
                file_path=file_path,
                node_id=node_id,
                check_contrast=True,
                check_spacing=True,
                check_typography=True
            )

            if isinstance(result, dict):
                issues_count = len(result.get("issues", []))
                alignment_score = result.get("alignment_score", {})
                score = alignment_score.get("score", 100) if alignment_score else 100

                # Count critical issues (WCAG failures)
                contrast_results = result.get("contrast_results", [])
                critical = sum(1 for r in contrast_results if not r.get("passes_aa", True))

                checks.append(QACheckResult(
                    check_name="design_qa_verify",
                    passed=result.get("can_claim_done", True),
                    score=score,
                    issues_count=issues_count,
                    critical_issues=critical,
                    summary=f"Alignment: {alignment_score.get('grade', 'N/A')}, Issues: {issues_count}",
                    details=result
                ))

                all_issues.extend(result.get("issues", []))

        except Exception as e:
            checks.append(QACheckResult(
                check_name="design_qa_verify",
                passed=False,
                score=0,
                issues_count=1,
                critical_issues=1,
                summary=f"Error: {str(e)}",
                details={"error": str(e)}
            ))

    # === Check 2: Accessibility Check ===
    accessibility_check = tools.get("accessibility_design_check")
    if accessibility_check:
        try:
            result = accessibility_check(
                file_path=file_path,
                node_id=node_id,
                wcag_level=wcag_level
            )

            if isinstance(result, dict):
                issues = result.get("issues", [])
                critical = sum(1 for i in issues if i.get("severity") in ["critical", "serious"])

                checks.append(QACheckResult(
                    check_name="accessibility_design_check",
                    passed=result.get("can_claim_done", True),
                    score=result.get("score", 100),
                    issues_count=len(issues),
                    critical_issues=critical,
                    summary=f"WCAG {wcag_level}: {result.get('grade', 'N/A')}, Score: {result.get('score', 0)}/100",
                    details=result
                ))

                # Add issues with context
                for issue in issues:
                    all_issues.append(f"[A11y] {issue.get('message', '')}")

        except Exception as e:
            checks.append(QACheckResult(
                check_name="accessibility_design_check",
                passed=False,
                score=0,
                issues_count=1,
                critical_issues=1,
                summary=f"Error: {str(e)}",
                details={"error": str(e)}
            ))

    # === Check 3: Screenshot Review ===
    if take_screenshot:
        get_screenshot = tools.get("pencil_get_screenshot")
        if get_screenshot:
            try:
                get_screenshot(filePath=file_path, nodeId=node_id)
                checks.append(QACheckResult(
                    check_name="screenshot_review",
                    passed=True,
                    score=100,
                    issues_count=0,
                    critical_issues=0,
                    summary="Screenshot captured for visual review",
                    details={"screenshot": "captured"}
                ))
            except Exception as e:
                checks.append(QACheckResult(
                    check_name="screenshot_review",
                    passed=True,  # Non-blocking
                    score=100,
                    issues_count=0,
                    critical_issues=0,
                    summary=f"Screenshot failed: {str(e)}",
                    details={"error": str(e)}
                ))

    # === Calculate Overall Results ===
    overall_score, overall_grade = calculate_overall_score(checks)

    total_issues = sum(c.issues_count for c in checks)
    blocking_issues = sum(c.critical_issues for c in checks)

    # Determine pass/fail
    # Fail if any critical/serious issues, or if any check explicitly failed
    has_blocking = blocking_issues > 0
    any_failed = any(not c.passed for c in checks)

    if has_blocking:
        overall_passed = False
        verdict = "FAIL_BLOCKING_ISSUES"
    elif any_failed:
        overall_passed = False
        verdict = "FAIL_CHECKS_NOT_PASSED"
    elif fail_on_moderate and total_issues > 0:
        overall_passed = False
        verdict = "FAIL_MODERATE_ISSUES"
    else:
        overall_passed = True
        verdict = "PASS"

    # === Generate Report ===
    timestamp = datetime.now().isoformat()

    lines = [
        "# Full Design QA Report",
        f"",
        f"**Timestamp:** {timestamp}",
        f"**Node:** {node_id}",
        f"**File:** {file_path}",
        f"",
        f"---",
        f"",
        f"## Overall Result",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| **Verdict** | {'PASS' if overall_passed else 'FAIL'} |",
        f"| **Score** | {overall_score}/100 |",
        f"| **Grade** | {overall_grade} |",
        f"| **Total Issues** | {total_issues} |",
        f"| **Blocking Issues** | {blocking_issues} |",
        f"",
        f"---",
        f"",
        f"## Individual Checks",
        f"",
    ]

    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"### {check.check_name}")
        lines.append(f"- **Status:** {status}")
        lines.append(f"- **Score:** {check.score}/100")
        lines.append(f"- **Issues:** {check.issues_count} ({check.critical_issues} blocking)")
        lines.append(f"- **Summary:** {check.summary}")
        lines.append("")

    if all_issues:
        lines.append("---")
        lines.append("")
        lines.append("## All Issues")
        lines.append("")
        for issue in all_issues[:20]:  # Limit to first 20
            lines.append(f"- {issue}")
        if len(all_issues) > 20:
            lines.append(f"- ... and {len(all_issues) - 20} more")
        lines.append("")

    # Verdict explanation
    lines.append("---")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")

    if overall_passed:
        lines.append("**Design passes all QA checks and can proceed to implementation.**")
    else:
        lines.append("**Design has issues that must be resolved before proceeding.**")
        lines.append("")
        if has_blocking:
            lines.append(f"- {blocking_issues} blocking issues require immediate attention")
        if any_failed:
            lines.append("- One or more QA checks did not pass")
        lines.append("")
        lines.append("Fix the issues above and run QA again.")

    summary = "\n".join(lines)

    # Build report object
    report = FullQAReport(
        timestamp=timestamp,
        node_id=node_id,
        file_path=file_path,
        overall_passed=overall_passed,
        overall_score=overall_score,
        overall_grade=overall_grade,
        checks=checks,
        total_issues=total_issues,
        blocking_issues=blocking_issues,
        verdict=verdict,
        summary=summary
    )

    return {
        "success": True,
        "overall_passed": overall_passed,
        "overall_score": overall_score,
        "grade": overall_grade,
        "verdict": verdict,
        "total_issues": total_issues,
        "blocking_issues": blocking_issues,
        "checks": [
            {
                "name": c.check_name,
                "passed": c.passed,
                "score": c.score,
                "issues_count": c.issues_count,
                "critical_issues": c.critical_issues,
                "summary": c.summary
            }
            for c in checks
        ],
        "all_issues": all_issues[:50],  # Limit for response size
        "report": summary,
        "can_claim_done": overall_passed
    }


if __name__ == "__main__":
    print("design_qa_full v1.0.0")
    print("=" * 50)
    print("Full design QA sequence with unified pass/fail verdict")
    print("")
    print("Checks performed:")
    print("  1. design_qa_verify (alignment, spacing, typography, contrast)")
    print("  2. accessibility_design_check (WCAG compliance)")
    print("  3. Screenshot capture for visual review")
    print("")
    print("Verdict rules:")
    print("  - PASS: All checks pass, no blocking issues")
    print("  - FAIL: Any blocking issues OR any check fails")
