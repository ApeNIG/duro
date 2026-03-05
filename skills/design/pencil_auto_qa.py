"""
Skill: pencil_auto_qa
Description: Automatic QA when design is marked "done".
Version: 1.0.0
Tier: tested

Trigger: When user says "design done", "ready for review", "finished design", etc.

Purpose: Gate the "done" claim with automatic QA checks. If issues found, block
the "done" claim and list what needs to be fixed.

Process:
1. Get screenshot of current design
2. Run snapshot_layout for measurements
3. Execute design_qa_full compound skill
4. If issues found: block "done" claim, list issues
5. If passed: store decision, proceed to implementation

Usage:
    duro_run_skill(skill_name="pencil_auto_qa", args={
        "file_path": "design.pen",
        "node_id": "screen_001",
        "context": "Landing page hero section"
    })

Can also be triggered via intent detection:
    - "I'm done with this design"
    - "This design is ready"
    - "Let's move to implementation"
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


SKILL_META = {
    "name": "pencil_auto_qa",
    "description": "Automatic QA when design is marked done",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": [
        "design done",
        "finished design",
        "ready for review",
        "move to implementation",
        "design complete",
        "ready to code",
    ],
    "keywords": ["design", "qa", "done", "auto", "gate", "verification", "pencil"],
}

REQUIRES = ["design_qa_full", "pencil_get_screenshot", "duro_store_decision"]


# Phrases that indicate design completion intent
DONE_PHRASES = [
    "design done",
    "design is done",
    "finished design",
    "design finished",
    "ready for review",
    "ready to review",
    "design complete",
    "design is complete",
    "move to implementation",
    "ready to code",
    "start coding",
    "let's implement",
    "design ready",
    "looks good to me",
    "ship it",
]


def detect_done_intent(message: str) -> bool:
    """Check if message indicates design completion intent."""
    message_lower = message.lower().strip()

    for phrase in DONE_PHRASES:
        if phrase in message_lower:
            return True

    return False


@dataclass
class QAGateResult:
    """Result of the QA gate check."""
    passed: bool
    can_proceed: bool
    issues_blocking: List[str]
    issues_warning: List[str]
    score: float
    grade: str
    report: str
    decision_stored: bool
    decision_id: Optional[str]


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run automatic QA when design is marked "done".

    Args:
        args: {
            file_path: str - Path to .pen file
            node_id: str - Node to check
            design_context: str - Context about what was designed (optional)
            wcag_level: str - WCAG level (default: "AA")
            strict_mode: bool - Fail on any issues (default: False)
            store_decision: bool - Store decision on pass (default: True)
        }
        tools: {
            design_qa_full: func,
            pencil_get_screenshot: func,
            duro_store_decision: func
        }
        context: execution context

    Returns:
        {success, passed, can_proceed, issues, report, decision_id}
    """
    file_path = args.get("file_path", "")
    node_id = args.get("node_id", "")
    design_context = args.get("design_context", "Design")
    wcag_level = args.get("wcag_level", "AA")
    strict_mode = args.get("strict_mode", False)
    store_decision = args.get("store_decision", True)

    if not node_id:
        return {"success": False, "error": "node_id is required"}

    result = QAGateResult(
        passed=False,
        can_proceed=False,
        issues_blocking=[],
        issues_warning=[],
        score=0,
        grade="F",
        report="",
        decision_stored=False,
        decision_id=None
    )

    # === Step 1: Run Full QA ===
    design_qa_full = tools.get("design_qa_full")
    if not design_qa_full:
        return {"success": False, "error": "design_qa_full skill not available"}

    try:
        qa_result = design_qa_full(
            file_path=file_path,
            node_id=node_id,
            wcag_level=wcag_level,
            take_screenshot=True,
            fail_on_moderate=strict_mode
        )

        if isinstance(qa_result, dict):
            result.passed = qa_result.get("overall_passed", False)
            result.score = qa_result.get("overall_score", 0)
            result.grade = qa_result.get("grade", "F")

            # Categorize issues
            all_issues = qa_result.get("all_issues", [])
            blocking = qa_result.get("blocking_issues", 0)

            if blocking > 0:
                # First N issues are blocking
                result.issues_blocking = all_issues[:blocking]
                result.issues_warning = all_issues[blocking:]
            else:
                result.issues_warning = all_issues

            result.report = qa_result.get("report", "")

    except Exception as e:
        return {"success": False, "error": f"QA check failed: {str(e)}"}

    # === Step 2: Determine if can proceed ===
    if result.passed and len(result.issues_blocking) == 0:
        result.can_proceed = True
    else:
        result.can_proceed = False

    # === Step 3: Store decision if passed ===
    if result.can_proceed and store_decision:
        store_decision_func = tools.get("duro_store_decision")
        if store_decision_func:
            try:
                decision_result = store_decision_func(
                    decision=f"Design '{design_context}' approved for implementation",
                    rationale=f"Passed QA with score {result.score}/100 (Grade: {result.grade}). "
                              f"All accessibility and alignment checks passed.",
                    context=f"Auto-QA gate passed. Node: {node_id}",
                    tags=["design", "qa-passed", "auto-approved"],
                    reversible=True
                )

                if isinstance(decision_result, dict):
                    result.decision_stored = True
                    result.decision_id = decision_result.get("artifact_id")

            except Exception:
                pass  # Non-fatal

    # === Step 4: Generate response ===
    lines = []

    if result.can_proceed:
        lines.extend([
            "# Design QA Passed",
            "",
            f"**Score:** {result.score}/100 (Grade: {result.grade})",
            "",
            "Design has passed all automated QA checks and is ready for implementation.",
            "",
        ])

        if result.decision_stored:
            lines.append(f"**Decision stored:** {result.decision_id}")
            lines.append("")

        if result.issues_warning:
            lines.extend([
                "## Minor Warnings (non-blocking)",
                "",
            ])
            for issue in result.issues_warning[:5]:
                lines.append(f"- {issue}")
            lines.append("")
            lines.append("*These are suggestions for improvement but don't block implementation.*")

        lines.extend([
            "",
            "---",
            "",
            "**Next steps:**",
            "1. Proceed to implementation",
            "2. Use design_to_code_verifier to ensure code matches design",
            "3. Run QA again on the implemented component",
        ])

    else:
        lines.extend([
            "# Design QA Failed - Cannot Claim Done",
            "",
            f"**Score:** {result.score}/100 (Grade: {result.grade})",
            "",
            "Design has issues that must be resolved before proceeding.",
            "",
        ])

        if result.issues_blocking:
            lines.extend([
                "## Blocking Issues (must fix)",
                "",
            ])
            for issue in result.issues_blocking:
                lines.append(f"- {issue}")
            lines.append("")

        if result.issues_warning:
            lines.extend([
                "## Warnings (should fix)",
                "",
            ])
            for issue in result.issues_warning[:10]:
                lines.append(f"- {issue}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "**Required actions:**",
            "1. Fix all blocking issues listed above",
            "2. Re-run this QA check",
            "3. Only proceed when QA passes",
        ])

    response_report = "\n".join(lines)

    return {
        "success": True,
        "passed": result.passed,
        "can_proceed": result.can_proceed,
        "score": result.score,
        "grade": result.grade,
        "issues_blocking": result.issues_blocking,
        "issues_blocking_count": len(result.issues_blocking),
        "issues_warning": result.issues_warning,
        "issues_warning_count": len(result.issues_warning),
        "decision_stored": result.decision_stored,
        "decision_id": result.decision_id,
        "report": response_report,
        "full_qa_report": result.report
    }


# Helper function for intent detection
def should_trigger(message: str, current_context: Dict) -> bool:
    """
    Check if this skill should be triggered based on message and context.

    Used by orchestrator for automatic triggering.
    """
    # Check for done intent
    if not detect_done_intent(message):
        return False

    # Check if we're in a design context
    # (This would be determined by orchestrator based on recent activity)
    recent_tools = current_context.get("recent_tools_used", [])
    design_tools = ["pencil_batch_design", "pencil_batch_get", "get_screenshot"]

    has_design_context = any(t in recent_tools for t in design_tools)

    return has_design_context


if __name__ == "__main__":
    print("pencil_auto_qa v1.0.0")
    print("=" * 50)
    print("Automatic QA when design is marked 'done'")
    print("")
    print("Trigger phrases:")
    for phrase in DONE_PHRASES[:8]:
        print(f"  - '{phrase}'")
    print("  ...")
    print("")
    print("Process:")
    print("  1. Run design_qa_full compound skill")
    print("  2. If passed: store decision, allow proceed")
    print("  3. If failed: block, list issues to fix")
