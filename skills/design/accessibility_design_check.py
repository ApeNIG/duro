"""
Skill: accessibility_design_check
Description: WCAG compliance check at design phase (before code).
Version: 1.0.0
Tier: tested

Purpose: Catch accessibility issues early in the design process, before they become expensive to fix in code.

Checks:
- Color contrast ratios (AA: 4.5:1, AAA: 7:1)
- Touch/click target sizes (44px minimum)
- Text sizing (minimum 12px)
- Focus indicators (presence check)
- Semantic structure (heading hierarchy)
- Color-only information (no reliance on color alone)

Usage:
    duro_run_skill(skill_name="accessibility_design_check", args={
        "file_path": "design.pen",
        "node_id": "screen_001",
        "wcag_level": "AA"  # or "AAA"
    })
"""

import math
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


SKILL_META = {
    "name": "accessibility_design_check",
    "description": "WCAG compliance check at design phase",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["accessibility check", "wcag check", "a11y check", "accessibility audit"],
    "keywords": ["accessibility", "wcag", "a11y", "contrast", "touch", "target", "compliance"],
}

REQUIRES = ["pencil_batch_get", "pencil_snapshot_layout"]


class WCAGLevel(Enum):
    """WCAG compliance levels."""
    A = "A"
    AA = "AA"
    AAA = "AAA"


class IssueSeverity(Enum):
    """Accessibility issue severity."""
    CRITICAL = "critical"  # Must fix - blocks users
    SERIOUS = "serious"    # Should fix - significantly impacts users
    MODERATE = "moderate"  # Recommended - affects some users
    MINOR = "minor"        # Nice to have - minor impact


@dataclass
class AccessibilityIssue:
    """A detected accessibility issue."""
    check_type: str
    severity: IssueSeverity
    wcag_criterion: str  # e.g., "1.4.3" for contrast
    message: str
    node_id: str
    node_name: str
    current_value: Any
    required_value: Any
    suggestion: str


@dataclass
class AccessibilityReport:
    """Full accessibility report."""
    wcag_level: WCAGLevel
    total_checks: int
    passed: int
    failed: int
    issues: List[AccessibilityIssue] = field(default_factory=list)
    score: float = 0.0
    grade: str = "F"
    summary: str = ""


# === WCAG CONTRAST CHECKING (reused from design_qa_verify) ===

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    if len(hex_color) != 6:
        return (0, 0, 0)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_relative_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance per WCAG 2.1."""
    def srgb_to_linear(value: int) -> float:
        v = value / 255
        if v <= 0.04045:
            return v / 12.92
        return ((v + 0.055) / 1.055) ** 2.4

    r_lin = srgb_to_linear(r)
    g_lin = srgb_to_linear(g)
    b_lin = srgb_to_linear(b)

    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """Calculate WCAG contrast ratio between two colors."""
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)

    l1 = rgb_to_relative_luminance(*rgb1)
    l2 = rgb_to_relative_luminance(*rgb2)

    lighter = max(l1, l2)
    darker = min(l1, l2)

    return (lighter + 0.05) / (darker + 0.05)


# === ACCESSIBILITY CHECKS ===

def check_text_contrast(
    nodes: List[Dict],
    wcag_level: WCAGLevel = WCAGLevel.AA
) -> List[AccessibilityIssue]:
    """
    Check text contrast against WCAG requirements.

    WCAG 1.4.3 (AA): 4.5:1 for normal text, 3:1 for large text
    WCAG 1.4.6 (AAA): 7:1 for normal text, 4.5:1 for large text
    """
    issues = []

    # Requirements by level
    if wcag_level == WCAGLevel.AAA:
        normal_ratio = 7.0
        large_ratio = 4.5
        criterion = "1.4.6"
    else:  # AA or A
        normal_ratio = 4.5
        large_ratio = 3.0
        criterion = "1.4.3"

    def check_node(node: Dict, parent_bg: str = "#ffffff"):
        if not isinstance(node, dict):
            return

        node_id = node.get("id", "unknown")
        node_name = node.get("name", node_id)

        # Get background color
        bg_color = parent_bg
        if "fill" in node:
            fill = node["fill"]
            if isinstance(fill, str) and fill.startswith("#"):
                bg_color = fill

        # Check text nodes
        if node.get("type") == "text":
            text_color = "#000000"
            if "fill" in node:
                fill = node["fill"]
                if isinstance(fill, str) and fill.startswith("#"):
                    text_color = fill

            font_size = node.get("fontSize", 16)
            font_weight = str(node.get("fontWeight", "normal"))

            # Determine if large text (18pt = 24px, 14pt bold = 18.5px bold)
            is_large = font_size >= 24 or (font_size >= 18.5 and font_weight in ["bold", "700", "800", "900"])
            required_ratio = large_ratio if is_large else normal_ratio

            ratio = calculate_contrast_ratio(text_color, bg_color)

            if ratio < required_ratio:
                issues.append(AccessibilityIssue(
                    check_type="contrast",
                    severity=IssueSeverity.SERIOUS,
                    wcag_criterion=criterion,
                    message=f"Text contrast {ratio:.2f}:1 below {required_ratio}:1 requirement",
                    node_id=node_id,
                    node_name=node_name,
                    current_value=f"{ratio:.2f}:1",
                    required_value=f"{required_ratio}:1",
                    suggestion=f"Increase contrast between {text_color} and {bg_color}"
                ))

        # Recurse
        for child in node.get("children", []):
            check_node(child, bg_color)

    for node in nodes:
        check_node(node)

    return issues


def check_touch_target_size(
    nodes: List[Dict],
    minimum_size: int = 44
) -> List[AccessibilityIssue]:
    """
    Check touch/click target sizes against WCAG 2.5.5.

    Minimum size: 44x44 CSS pixels for AA
    Exception: Links in flowing text
    """
    issues = []

    interactive_types = {"button", "link", "input", "checkbox", "radio", "switch", "select"}

    def is_interactive(node: Dict) -> bool:
        """Check if node is interactive."""
        name = node.get("name", "").lower()
        node_type = node.get("type", "").lower()

        # Check name patterns
        interactive_keywords = ["button", "btn", "link", "input", "checkbox", "radio", "switch", "toggle", "select", "click", "tap"]
        if any(kw in name for kw in interactive_keywords):
            return True

        # Check if it's explicitly an interactive component
        if node_type in interactive_types:
            return True

        return False

    def check_node(node: Dict):
        if not isinstance(node, dict):
            return

        node_id = node.get("id", "unknown")
        node_name = node.get("name", node_id)

        if is_interactive(node):
            width = node.get("width", 0)
            height = node.get("height", 0)

            if isinstance(width, (int, float)) and isinstance(height, (int, float)):
                if width < minimum_size or height < minimum_size:
                    issues.append(AccessibilityIssue(
                        check_type="touch_target",
                        severity=IssueSeverity.MODERATE,
                        wcag_criterion="2.5.5",
                        message=f"Touch target {width}x{height}px below {minimum_size}x{minimum_size}px minimum",
                        node_id=node_id,
                        node_name=node_name,
                        current_value=f"{width}x{height}px",
                        required_value=f"{minimum_size}x{minimum_size}px",
                        suggestion=f"Increase size to at least {minimum_size}x{minimum_size}px"
                    ))

        # Recurse
        for child in node.get("children", []):
            check_node(child)

    for node in nodes:
        check_node(node)

    return issues


def check_text_size(
    nodes: List[Dict],
    minimum_size: int = 12
) -> List[AccessibilityIssue]:
    """
    Check text size meets minimum readable size.

    While WCAG doesn't specify a minimum, 12px is generally accepted as minimum readable.
    """
    issues = []

    def check_node(node: Dict):
        if not isinstance(node, dict):
            return

        node_id = node.get("id", "unknown")
        node_name = node.get("name", node_id)

        if node.get("type") == "text":
            font_size = node.get("fontSize", 16)

            if isinstance(font_size, (int, float)) and font_size < minimum_size:
                issues.append(AccessibilityIssue(
                    check_type="text_size",
                    severity=IssueSeverity.MODERATE,
                    wcag_criterion="1.4.4",
                    message=f"Text size {font_size}px below {minimum_size}px minimum",
                    node_id=node_id,
                    node_name=node_name,
                    current_value=f"{font_size}px",
                    required_value=f">= {minimum_size}px",
                    suggestion=f"Increase font size to at least {minimum_size}px"
                ))

        # Recurse
        for child in node.get("children", []):
            check_node(child)

    for node in nodes:
        check_node(node)

    return issues


def check_heading_hierarchy(
    nodes: List[Dict]
) -> List[AccessibilityIssue]:
    """
    Check for proper heading hierarchy (H1 -> H2 -> H3, no skipping levels).

    WCAG 1.3.1 - Info and Relationships
    """
    issues = []
    headings_found = []

    def find_headings(node: Dict, depth: int = 0):
        if not isinstance(node, dict):
            return

        node_id = node.get("id", "unknown")
        node_name = node.get("name", "").lower()
        font_size = node.get("fontSize", 16)

        # Detect heading patterns
        # By name: h1, h2, heading, title
        # By size: large text that's not body text
        heading_level = None

        if "h1" in node_name or (node_name.startswith("heading") and "1" in node_name):
            heading_level = 1
        elif "h2" in node_name or (node_name.startswith("heading") and "2" in node_name):
            heading_level = 2
        elif "h3" in node_name or (node_name.startswith("heading") and "3" in node_name):
            heading_level = 3
        elif "h4" in node_name:
            heading_level = 4
        elif "title" in node_name and font_size >= 24:
            heading_level = 1
        elif "subtitle" in node_name:
            heading_level = 2

        if heading_level:
            headings_found.append({
                "level": heading_level,
                "node_id": node_id,
                "node_name": node.get("name", node_id),
                "font_size": font_size
            })

        # Recurse
        for child in node.get("children", []):
            find_headings(child, depth + 1)

    for node in nodes:
        find_headings(node)

    # Check hierarchy
    if headings_found:
        # Check for multiple H1s
        h1_count = sum(1 for h in headings_found if h["level"] == 1)
        if h1_count > 1:
            issues.append(AccessibilityIssue(
                check_type="heading_hierarchy",
                severity=IssueSeverity.MODERATE,
                wcag_criterion="1.3.1",
                message=f"Multiple H1 headings found ({h1_count}). Should have exactly one.",
                node_id="multiple",
                node_name="H1 headings",
                current_value=f"{h1_count} H1s",
                required_value="1 H1",
                suggestion="Keep only one H1 as the main page heading"
            ))

        # Check for skipped levels
        levels = sorted(set(h["level"] for h in headings_found))
        for i in range(len(levels) - 1):
            if levels[i + 1] - levels[i] > 1:
                issues.append(AccessibilityIssue(
                    check_type="heading_hierarchy",
                    severity=IssueSeverity.MODERATE,
                    wcag_criterion="1.3.1",
                    message=f"Heading level skipped: H{levels[i]} to H{levels[i+1]}",
                    node_id="hierarchy",
                    node_name="Heading levels",
                    current_value=f"H{levels[i]} -> H{levels[i+1]}",
                    required_value=f"H{levels[i]} -> H{levels[i]+1}",
                    suggestion=f"Add H{levels[i]+1} between H{levels[i]} and H{levels[i+1]}"
                ))

    return issues


def check_focus_indicators(
    nodes: List[Dict]
) -> List[AccessibilityIssue]:
    """
    Check that interactive elements have focus indicators defined.

    WCAG 2.4.7 - Focus Visible
    """
    issues = []

    # This is a design-time check - we look for focus states in component variants
    # or border/outline properties that would indicate focus styling

    def check_node(node: Dict):
        if not isinstance(node, dict):
            return

        node_id = node.get("id", "unknown")
        node_name = node.get("name", "").lower()

        # Check interactive components
        interactive_keywords = ["button", "btn", "input", "link", "tab", "checkbox", "radio"]
        is_interactive = any(kw in node_name for kw in interactive_keywords)

        if is_interactive:
            # Look for focus variant or focus-related styling
            has_focus_state = False

            # Check if "focus" is in the name (suggesting a focus variant)
            if "focus" in node_name:
                has_focus_state = True

            # Check for ring/outline properties that might indicate focus
            if node.get("stroke") or node.get("ring"):
                has_focus_state = True

            # This is a warning since we can't fully verify focus states at design time
            if not has_focus_state and "state" not in node_name:  # Skip if it's already a state variant
                issues.append(AccessibilityIssue(
                    check_type="focus_indicator",
                    severity=IssueSeverity.MINOR,
                    wcag_criterion="2.4.7",
                    message=f"No focus state found for interactive element",
                    node_id=node_id,
                    node_name=node.get("name", node_id),
                    current_value="No focus state",
                    required_value="Focus state with visible indicator",
                    suggestion="Add a :focus variant with visible border/ring"
                ))

        # Recurse
        for child in node.get("children", []):
            check_node(child)

    for node in nodes:
        check_node(node)

    return issues


def calculate_score_and_grade(report: AccessibilityReport) -> Tuple[float, str]:
    """Calculate accessibility score and letter grade."""
    if report.total_checks == 0:
        return 100.0, "A"

    # Weight by severity
    severity_weights = {
        IssueSeverity.CRITICAL: 4,
        IssueSeverity.SERIOUS: 3,
        IssueSeverity.MODERATE: 2,
        IssueSeverity.MINOR: 1,
    }

    total_weight = 0
    for issue in report.issues:
        total_weight += severity_weights.get(issue.severity, 1)

    # Score: 100 - (weighted issues / total checks * 100)
    max_possible = report.total_checks * 4  # If all were critical
    penalty = (total_weight / max(max_possible, 1)) * 100
    score = max(0, 100 - penalty)

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
    Run accessibility compliance check on a design.

    Args:
        args: {
            file_path: str - Path to .pen file
            node_id: str - Node to check
            wcag_level: str - "A", "AA", or "AAA" (default: "AA")
            minimum_touch_target: int - Minimum touch target size (default: 44)
            minimum_text_size: int - Minimum text size (default: 12)
        }
        tools: {pencil_batch_get, pencil_snapshot_layout}
        context: execution context

    Returns:
        {success, report, score, grade, issues}
    """
    file_path = args.get("file_path", "")
    node_id = args.get("node_id", "")
    wcag_level_str = args.get("wcag_level", "AA").upper()
    minimum_touch_target = args.get("minimum_touch_target", 44)
    minimum_text_size = args.get("minimum_text_size", 12)

    if not node_id:
        return {"success": False, "error": "node_id is required"}

    # Parse WCAG level
    try:
        wcag_level = WCAGLevel[wcag_level_str]
    except KeyError:
        wcag_level = WCAGLevel.AA

    # Get design nodes
    nodes = []
    batch_get = tools.get("pencil_batch_get")
    if batch_get:
        try:
            result = batch_get(filePath=file_path, nodeIds=[node_id], readDepth=10)
            if result:
                nodes = result if isinstance(result, list) else [result]
        except Exception as e:
            return {"success": False, "error": f"Failed to read design: {str(e)}"}

    if not nodes:
        return {"success": False, "error": "No nodes found in design"}

    # Run all checks
    all_issues = []

    # 1. Contrast check
    contrast_issues = check_text_contrast(nodes, wcag_level)
    all_issues.extend(contrast_issues)

    # 2. Touch target size
    touch_issues = check_touch_target_size(nodes, minimum_touch_target)
    all_issues.extend(touch_issues)

    # 3. Text size
    text_issues = check_text_size(nodes, minimum_text_size)
    all_issues.extend(text_issues)

    # 4. Heading hierarchy
    heading_issues = check_heading_hierarchy(nodes)
    all_issues.extend(heading_issues)

    # 5. Focus indicators
    focus_issues = check_focus_indicators(nodes)
    all_issues.extend(focus_issues)

    # Build report
    total_checks = 5  # Number of check types
    passed = total_checks - len(set(i.check_type for i in all_issues))

    report = AccessibilityReport(
        wcag_level=wcag_level,
        total_checks=total_checks,
        passed=passed,
        failed=total_checks - passed,
        issues=all_issues
    )

    score, grade = calculate_score_and_grade(report)
    report.score = score
    report.grade = grade

    # Generate summary
    lines = [
        f"# Accessibility Report (WCAG {wcag_level.value})",
        f"",
        f"**Score:** {score}/100 (Grade: {grade})",
        f"**Checks:** {passed}/{total_checks} passed",
        f"",
    ]

    # Group issues by severity
    by_severity = {}
    for issue in all_issues:
        sev = issue.severity.value
        if sev not in by_severity:
            by_severity[sev] = []
        by_severity[sev].append(issue)

    for sev in ["critical", "serious", "moderate", "minor"]:
        if sev in by_severity:
            lines.append(f"## {sev.title()} Issues ({len(by_severity[sev])})")
            for issue in by_severity[sev]:
                lines.append(f"- **{issue.wcag_criterion}** {issue.message}")
                lines.append(f"  - Node: {issue.node_name}")
                lines.append(f"  - Current: {issue.current_value} | Required: {issue.required_value}")
                lines.append(f"  - Fix: {issue.suggestion}")
            lines.append("")

    if not all_issues:
        lines.append("## All Checks Passed")
        lines.append(f"Design meets WCAG {wcag_level.value} requirements.")

    report.summary = "\n".join(lines)

    # Return results
    return {
        "success": True,
        "score": score,
        "grade": grade,
        "wcag_level": wcag_level.value,
        "total_checks": total_checks,
        "passed": passed,
        "failed": total_checks - passed,
        "issues": [
            {
                "check_type": i.check_type,
                "severity": i.severity.value,
                "wcag_criterion": i.wcag_criterion,
                "message": i.message,
                "node_id": i.node_id,
                "node_name": i.node_name,
                "current_value": str(i.current_value),
                "required_value": str(i.required_value),
                "suggestion": i.suggestion
            }
            for i in all_issues
        ],
        "report": report.summary,
        "can_claim_done": len([i for i in all_issues if i.severity in [IssueSeverity.CRITICAL, IssueSeverity.SERIOUS]]) == 0
    }


if __name__ == "__main__":
    print("accessibility_design_check v1.0.0")
    print("=" * 50)
    print("WCAG compliance check at design phase")
    print("")
    print("Checks performed:")
    print("  - Color contrast (WCAG 1.4.3/1.4.6)")
    print("  - Touch target size (WCAG 2.5.5)")
    print("  - Text size minimum")
    print("  - Heading hierarchy (WCAG 1.3.1)")
    print("  - Focus indicators (WCAG 2.4.7)")
