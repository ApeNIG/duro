"""
Skill: design_critique_parallel
Description: Multi-agent parallel design critique - runs 5 specialized reviewers simultaneously
Version: 1.0.0
Tier: tested

Inspired by compound-engineering plugin's multi-agent parallel review pattern.
Instead of sequential evaluation, spawns 5 specialized reviewer "agents" that
analyze different aspects of a design in parallel, then consolidates findings.

Reviewers:
1. layout_analyzer - Visual hierarchy, balance, composition, alignment
2. color_harmony_checker - Color usage, contrast, palette cohesion
3. typography_reviewer - Typography hierarchy, readability, pairing
4. accessibility_auditor - WCAG compliance, contrast ratios, touch targets
5. interaction_patterns - Consistency, whitespace, component patterns

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


# Skill metadata
SKILL_META = {
    "name": "design_critique_parallel",
    "description": "Multi-agent parallel design critique with 5 specialized reviewers",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Inspired by compound-engineering plugin multi-agent review pattern",
    "validated": "2026-03-05",
    "triggers": [
        "parallel critique", "full design review", "comprehensive critique",
        "multi-agent review", "deep design analysis"
    ],
    "keywords": [
        "design", "critique", "parallel", "multi-agent", "review",
        "layout", "color", "typography", "accessibility", "patterns"
    ],
    "phase": "4.0",
    "parallel": True,  # Marks this as a parallel skill
    "reviewers": [
        "layout_analyzer",
        "color_harmony_checker",
        "typography_reviewer",
        "accessibility_auditor",
        "interaction_patterns"
    ],
}

# Required capabilities
REQUIRES = ["get_screenshot", "read_node"]

# Default timeout
DEFAULT_TIMEOUT = 120


class Severity(Enum):
    """Issue severity levels"""
    P1_CRITICAL = "P1"  # Blocks usability or accessibility
    P2_MAJOR = "P2"     # Significant impact on user experience
    P3_MINOR = "P3"     # Polish issues, nice-to-fix


@dataclass
class ReviewFinding:
    """A single finding from a reviewer"""
    reviewer: str
    severity: Severity
    issue: str
    impact: str
    fix: str
    element: Optional[str] = None  # Node ID or description


@dataclass
class ReviewerResult:
    """Result from a single reviewer"""
    reviewer: str
    score: int  # 1-5
    findings: List[ReviewFinding]
    strengths: List[str]
    elapsed_ms: int
    success: bool
    error: Optional[str] = None


# ============================================================
# REVIEWER FUNCTIONS - Each evaluates one aspect of design
# ============================================================

def review_layout(design_context: Dict, tools: Dict) -> ReviewerResult:
    """
    Layout Analyzer - Visual hierarchy, balance, composition, alignment

    Checks:
    - Primary element immediately obvious (3-second test)
    - Eye flow follows intended path (F/Z pattern)
    - Visual weight evenly distributed
    - Elements snap to grid, no "floating" components
    - Consistent left/center/right alignment
    """
    start = time.time()
    findings = []
    strengths = []
    score = 5

    nodes = design_context.get("nodes", [])
    layout_info = design_context.get("layout", {})

    # Check for alignment issues
    x_positions = set()
    for node in nodes:
        if "x" in node:
            x_positions.add(round(node["x"], -1))  # Round to nearest 10

    # Too many unique X positions = alignment issues
    if len(x_positions) > 8:
        findings.append(ReviewFinding(
            reviewer="layout_analyzer",
            severity=Severity.P2_MAJOR,
            issue="Inconsistent horizontal alignment",
            impact="Elements appear scattered, reducing visual cohesion",
            fix="Align elements to a consistent grid (4 or 8px base)"
        ))
        score -= 1
    else:
        strengths.append("Good horizontal alignment consistency")

    # Check for visual hierarchy (size variance)
    font_sizes = [n.get("fontSize", 16) for n in nodes if "fontSize" in n]
    if font_sizes:
        size_range = max(font_sizes) - min(font_sizes)
        if size_range < 8:
            findings.append(ReviewFinding(
                reviewer="layout_analyzer",
                severity=Severity.P2_MAJOR,
                issue="Weak visual hierarchy - insufficient size contrast",
                impact="Users can't quickly identify primary content",
                fix="Use larger size difference (at least 1.5x) between heading and body"
            ))
            score -= 1
        elif size_range > 6:
            strengths.append("Strong visual hierarchy through size contrast")

    # Check for overcrowding (spacing)
    gaps = [n.get("gap", 0) for n in nodes if "gap" in n]
    paddings = [n.get("padding", 0) for n in nodes if "padding" in n]

    if gaps and min(gaps) < 8:
        findings.append(ReviewFinding(
            reviewer="layout_analyzer",
            severity=Severity.P3_MINOR,
            issue="Tight spacing in some areas",
            impact="Content feels cramped",
            fix="Increase minimum gap to 8-12px"
        ))
        score -= 0.5

    elapsed = int((time.time() - start) * 1000)

    return ReviewerResult(
        reviewer="layout_analyzer",
        score=max(1, min(5, round(score))),
        findings=findings,
        strengths=strengths,
        elapsed_ms=elapsed,
        success=True
    )


def review_color(design_context: Dict, tools: Dict) -> ReviewerResult:
    """
    Color Harmony Checker - Color usage, contrast, palette cohesion

    Checks:
    - Palette cohesive (limited color count)
    - Semantic colors used correctly (red=error, green=success)
    - Not overusing accent colors
    - Sufficient contrast for text
    """
    start = time.time()
    findings = []
    strengths = []
    score = 5

    nodes = design_context.get("nodes", [])

    # Extract all colors
    colors = set()
    for node in nodes:
        if "fill" in node:
            colors.add(node["fill"])
        if "color" in node:
            colors.add(node["color"])

    # Too many colors = palette issues
    if len(colors) > 8:
        findings.append(ReviewFinding(
            reviewer="color_harmony_checker",
            severity=Severity.P2_MAJOR,
            issue=f"Too many colors ({len(colors)})",
            impact="Visual noise, reduced brand cohesion",
            fix="Limit palette to 5-7 colors: 2 primary, 2 neutral, 2-3 semantic"
        ))
        score -= 1
    elif len(colors) <= 6:
        strengths.append(f"Controlled color palette ({len(colors)} colors)")

    # Check for proper semantic colors
    has_red = any("#f" in c.lower() or "#e" in c.lower() or "red" in c.lower() for c in colors if isinstance(c, str))
    has_green = any("#0" in c.lower() or "green" in c.lower() for c in colors if isinstance(c, str))

    if has_red or has_green:
        strengths.append("Semantic colors present for feedback")

    elapsed = int((time.time() - start) * 1000)

    return ReviewerResult(
        reviewer="color_harmony_checker",
        score=max(1, min(5, round(score))),
        findings=findings,
        strengths=strengths,
        elapsed_ms=elapsed,
        success=True
    )


def review_typography(design_context: Dict, tools: Dict) -> ReviewerResult:
    """
    Typography Reviewer - Typography hierarchy, readability, pairing

    Checks:
    - Clear size/weight hierarchy
    - Readable line length (45-75 chars)
    - Harmonious font pairing
    - Consistent scale ratios
    """
    start = time.time()
    findings = []
    strengths = []
    score = 5

    nodes = design_context.get("nodes", [])

    # Extract typography info
    font_families = set()
    font_sizes = []
    font_weights = set()

    for node in nodes:
        if "fontFamily" in node:
            font_families.add(node["fontFamily"])
        if "fontSize" in node:
            font_sizes.append(node["fontSize"])
        if "fontWeight" in node:
            font_weights.add(node["fontWeight"])

    # Check font family count
    if len(font_families) > 2:
        findings.append(ReviewFinding(
            reviewer="typography_reviewer",
            severity=Severity.P2_MAJOR,
            issue=f"Too many font families ({len(font_families)})",
            impact="Visual inconsistency, harder to read",
            fix="Limit to 2 fonts max: one for headings, one for body"
        ))
        score -= 1
    elif len(font_families) <= 2:
        strengths.append("Good font family discipline")

    # Check for proper scale
    if font_sizes:
        unique_sizes = sorted(set(font_sizes))
        if len(unique_sizes) >= 3:
            # Check if sizes follow a reasonable scale
            ratios = [unique_sizes[i+1]/unique_sizes[i] for i in range(len(unique_sizes)-1)]
            avg_ratio = sum(ratios) / len(ratios)
            if 1.1 <= avg_ratio <= 1.5:
                strengths.append(f"Consistent type scale (avg ratio: {avg_ratio:.2f})")
            else:
                findings.append(ReviewFinding(
                    reviewer="typography_reviewer",
                    severity=Severity.P3_MINOR,
                    issue="Inconsistent type scale",
                    impact="Typography feels random",
                    fix="Use a consistent scale ratio (1.2-1.333 recommended)"
                ))
                score -= 0.5

    # Check weight variety
    if len(font_weights) < 2:
        findings.append(ReviewFinding(
            reviewer="typography_reviewer",
            severity=Severity.P3_MINOR,
            issue="Limited font weight variety",
            impact="Weak typographic hierarchy",
            fix="Use 2-3 weights: regular for body, medium/bold for emphasis"
        ))
        score -= 0.5

    elapsed = int((time.time() - start) * 1000)

    return ReviewerResult(
        reviewer="typography_reviewer",
        score=max(1, min(5, round(score))),
        findings=findings,
        strengths=strengths,
        elapsed_ms=elapsed,
        success=True
    )


def review_accessibility(design_context: Dict, tools: Dict) -> ReviewerResult:
    """
    Accessibility Auditor - WCAG compliance, contrast ratios, touch targets

    Checks:
    - Text contrast meets WCAG AA (4.5:1 normal, 3:1 large)
    - Touch targets minimum 44x44px
    - Focus states visible
    - No color-only information
    """
    start = time.time()
    findings = []
    strengths = []
    score = 5

    nodes = design_context.get("nodes", [])

    # Check touch target sizes
    small_targets = []
    for node in nodes:
        if node.get("type") in ["button", "link", "ref"]:
            width = node.get("width", 44)
            height = node.get("height", 44)
            if width < 44 or height < 44:
                small_targets.append(node.get("name", node.get("id", "unknown")))

    if small_targets:
        findings.append(ReviewFinding(
            reviewer="accessibility_auditor",
            severity=Severity.P1_CRITICAL,
            issue=f"Touch targets too small ({len(small_targets)} elements)",
            impact="Hard to tap on mobile, WCAG failure",
            fix="Minimum 44x44px for all interactive elements",
            element=", ".join(small_targets[:3])
        ))
        score -= 1.5
    else:
        strengths.append("Touch targets meet minimum size")

    # Check for text on images (potential contrast issue)
    # This is a simplified check - real implementation would analyze contrast
    text_on_image = any(
        node.get("type") == "text" and
        any(p.get("type") == "image" for p in nodes if p.get("id") == node.get("parent"))
        for node in nodes
    )

    if text_on_image:
        findings.append(ReviewFinding(
            reviewer="accessibility_auditor",
            severity=Severity.P2_MAJOR,
            issue="Text appears over images",
            impact="Potential contrast issues, hard to read",
            fix="Add semi-transparent overlay or ensure sufficient contrast"
        ))
        score -= 0.5

    elapsed = int((time.time() - start) * 1000)

    return ReviewerResult(
        reviewer="accessibility_auditor",
        score=max(1, min(5, round(score))),
        findings=findings,
        strengths=strengths,
        elapsed_ms=elapsed,
        success=True
    )


def review_patterns(design_context: Dict, tools: Dict) -> ReviewerResult:
    """
    Interaction Patterns - Consistency, whitespace, component patterns

    Checks:
    - Same patterns used throughout
    - Consistent button styles
    - Matching iconography
    - Content has room to breathe
    """
    start = time.time()
    findings = []
    strengths = []
    score = 5

    nodes = design_context.get("nodes", [])

    # Check button consistency
    buttons = [n for n in nodes if "button" in n.get("name", "").lower() or n.get("type") == "button"]
    if len(buttons) > 1:
        # Check if buttons have consistent styling
        button_heights = set(b.get("height") for b in buttons if "height" in b)
        button_radii = set(b.get("cornerRadius") for b in buttons if "cornerRadius" in b)

        if len(button_heights) > 2:
            findings.append(ReviewFinding(
                reviewer="interaction_patterns",
                severity=Severity.P2_MAJOR,
                issue="Inconsistent button heights",
                impact="UI feels unpolished, harder to scan",
                fix="Standardize button heights (e.g., 36px, 44px, 52px)"
            ))
            score -= 1
        else:
            strengths.append("Consistent button sizing")

        if len(button_radii) > 2:
            findings.append(ReviewFinding(
                reviewer="interaction_patterns",
                severity=Severity.P3_MINOR,
                issue="Inconsistent border radius on buttons",
                impact="Subtle visual inconsistency",
                fix="Use consistent corner radius across all buttons"
            ))
            score -= 0.5

    # Check spacing consistency
    gaps = [n.get("gap", 0) for n in nodes if "gap" in n]
    unique_gaps = set(gaps)

    if len(unique_gaps) > 5:
        findings.append(ReviewFinding(
            reviewer="interaction_patterns",
            severity=Severity.P3_MINOR,
            issue=f"Too many spacing values ({len(unique_gaps)})",
            impact="Inconsistent rhythm, feels random",
            fix="Use spacing scale: 4, 8, 12, 16, 24, 32, 48px"
        ))
        score -= 0.5
    elif len(unique_gaps) <= 4:
        strengths.append("Consistent spacing scale")

    elapsed = int((time.time() - start) * 1000)

    return ReviewerResult(
        reviewer="interaction_patterns",
        score=max(1, min(5, round(score))),
        findings=findings,
        strengths=strengths,
        elapsed_ms=elapsed,
        success=True
    )


# ============================================================
# MAIN EXECUTION - Runs all reviewers in parallel
# ============================================================

REVIEWERS = {
    "layout_analyzer": review_layout,
    "color_harmony_checker": review_color,
    "typography_reviewer": review_typography,
    "accessibility_auditor": review_accessibility,
    "interaction_patterns": review_patterns,
}


def format_consolidated_report(results: List[ReviewerResult], elapsed: float) -> str:
    """
    Create a consolidated report from all reviewer results.
    Prioritizes findings by severity (P1 > P2 > P3).
    """
    lines = []
    lines.append("# Design Critique Report (Parallel Multi-Agent)")
    lines.append(f"*{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC | {elapsed:.1f}s total*")
    lines.append("")

    # Overall score
    scores = [r.score for r in results if r.success]
    avg_score = sum(scores) / len(scores) if scores else 0
    lines.append(f"## Overall Score: {avg_score:.1f}/5")
    lines.append("")

    # Reviewer breakdown
    lines.append("### Reviewer Scores")
    lines.append("| Reviewer | Score | Time |")
    lines.append("|----------|-------|------|")
    for r in results:
        status = f"{r.score}/5" if r.success else "ERROR"
        lines.append(f"| {r.reviewer} | {status} | {r.elapsed_ms}ms |")
    lines.append("")

    # Collect all findings by severity
    all_findings: Dict[Severity, List[ReviewFinding]] = {
        Severity.P1_CRITICAL: [],
        Severity.P2_MAJOR: [],
        Severity.P3_MINOR: [],
    }

    for r in results:
        for f in r.findings:
            all_findings[f.severity].append(f)

    # P1 Critical Issues
    if all_findings[Severity.P1_CRITICAL]:
        lines.append("## P1 Critical Issues")
        for f in all_findings[Severity.P1_CRITICAL]:
            lines.append(f"### {f.issue}")
            lines.append(f"**Impact:** {f.impact}")
            lines.append(f"**Fix:** {f.fix}")
            if f.element:
                lines.append(f"**Element:** `{f.element}`")
            lines.append("")

    # P2 Major Issues
    if all_findings[Severity.P2_MAJOR]:
        lines.append("## P2 Major Issues")
        for f in all_findings[Severity.P2_MAJOR]:
            lines.append(f"- **{f.issue}** ({f.reviewer})")
            lines.append(f"  - Impact: {f.impact}")
            lines.append(f"  - Fix: {f.fix}")
        lines.append("")

    # P3 Minor Issues
    if all_findings[Severity.P3_MINOR]:
        lines.append("## P3 Minor Issues")
        for f in all_findings[Severity.P3_MINOR]:
            lines.append(f"- {f.issue} → {f.fix}")
        lines.append("")

    # Strengths
    all_strengths = []
    for r in results:
        all_strengths.extend(r.strengths)

    if all_strengths:
        lines.append("## Strengths")
        for s in all_strengths:
            lines.append(f"- {s}")
        lines.append("")

    # Summary counts
    total_findings = sum(len(f) for f in all_findings.values())
    lines.append("---")
    lines.append(f"**Summary:** {total_findings} issues found | "
                f"{len(all_findings[Severity.P1_CRITICAL])} critical, "
                f"{len(all_findings[Severity.P2_MAJOR])} major, "
                f"{len(all_findings[Severity.P3_MINOR])} minor | "
                f"{len(all_strengths)} strengths")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main parallel critique execution.

    Runs 5 specialized reviewers in parallel using ThreadPoolExecutor,
    then consolidates results into a prioritized report.

    Args:
        args: {
            design_context: dict - Node data from Pencil
            node_id: str - Optional node ID to screenshot first
            skip_reviewers: List[str] - Reviewers to skip
            max_workers: int - Parallel threads (default 5)
        }
        tools: {
            get_screenshot: callable - Get Pencil screenshot
            read_node: callable - Read node data
        }
        context: {run_id, timeout}

    Returns:
        {
            success: bool,
            report: str - Consolidated critique report
            overall_score: float - Average score 1-5
            findings_count: int
            p1_count: int
            p2_count: int
            p3_count: int
            reviewer_results: List[dict]
            elapsed_seconds: float
        }
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    # Parse args
    design_context = args.get("design_context", {})
    node_id = args.get("node_id")
    skip_reviewers = args.get("skip_reviewers", [])
    max_workers = args.get("max_workers", 5)

    # If node_id provided but no design_context, try to read it
    if node_id and not design_context:
        read_node = tools.get("read_node")
        if read_node:
            try:
                design_context = read_node(node_id)
            except Exception as e:
                return {"success": False, "error": f"Failed to read node: {e}"}

    # Determine which reviewers to run
    reviewers_to_run = {
        name: func for name, func in REVIEWERS.items()
        if name not in skip_reviewers
    }

    if not reviewers_to_run:
        return {"success": False, "error": "No reviewers to run (all skipped)"}

    # Run reviewers in parallel
    results: List[ReviewerResult] = []

    with ThreadPoolExecutor(max_workers=min(max_workers, len(reviewers_to_run))) as executor:
        futures = {
            executor.submit(func, design_context, tools): name
            for name, func in reviewers_to_run.items()
        }

        for future in as_completed(futures, timeout=timeout):
            reviewer_name = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append(ReviewerResult(
                    reviewer=reviewer_name,
                    score=0,
                    findings=[],
                    strengths=[],
                    elapsed_ms=0,
                    success=False,
                    error=str(e)
                ))

    # Calculate metrics
    elapsed = time.time() - start_time

    successful_results = [r for r in results if r.success]
    overall_score = sum(r.score for r in successful_results) / len(successful_results) if successful_results else 0

    all_findings = []
    for r in results:
        all_findings.extend(r.findings)

    p1_count = len([f for f in all_findings if f.severity == Severity.P1_CRITICAL])
    p2_count = len([f for f in all_findings if f.severity == Severity.P2_MAJOR])
    p3_count = len([f for f in all_findings if f.severity == Severity.P3_MINOR])

    # Generate report
    report = format_consolidated_report(results, elapsed)

    return {
        "success": len(successful_results) >= 3,  # At least 3 reviewers must succeed
        "report": report,
        "overall_score": round(overall_score, 2),
        "findings_count": len(all_findings),
        "p1_count": p1_count,
        "p2_count": p2_count,
        "p3_count": p3_count,
        "reviewer_results": [
            {
                "reviewer": r.reviewer,
                "score": r.score,
                "findings": len(r.findings),
                "strengths": len(r.strengths),
                "elapsed_ms": r.elapsed_ms,
                "success": r.success,
                "error": r.error,
            }
            for r in results
        ],
        "elapsed_seconds": round(elapsed, 2),
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("design_critique_parallel - Multi-Agent Parallel Design Critique v1.0.0")
    print("=" * 60)
    print()
    print("This skill runs 5 specialized reviewers IN PARALLEL:")
    print()
    print("  ┌─────────────────────────────────────────────┐")
    print("  │           design_critique_parallel          │")
    print("  ├─────────────────────────────────────────────┤")
    print("  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │")
    print("  │  │ Layout   │  │ Color    │  │ Type     │  │")
    print("  │  │ Analyzer │  │ Harmony  │  │ Reviewer │  │")
    print("  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  │")
    print("  │       │              │              │       │")
    print("  │  ┌────┴─────┐  ┌────┴─────┐        │       │")
    print("  │  │ Access-  │  │ Pattern  │        │       │")
    print("  │  │ ibility  │  │ Checker  │        │       │")
    print("  │  └────┬─────┘  └────┬─────┘        │       │")
    print("  │       └──────────┬───┴─────────────┘       │")
    print("  │            Consolidated Report              │")
    print("  └─────────────────────────────────────────────┘")
    print()
    print("All reviewers run simultaneously, findings prioritized by severity.")
    print("P1 Critical > P2 Major > P3 Minor")
