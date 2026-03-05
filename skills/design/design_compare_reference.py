"""
Skill: design_compare_reference
Description: Compare current design against stored reference.
Version: 1.0.0
Tier: tested

Purpose: Compare a current design against a stored reference from the taste
library to identify deviations and suggest adjustments.

Process:
1. Load reference design (from design_reference artifact)
2. Get current design snapshot
3. Compare: spacing patterns, color usage, typography hierarchy
4. Generate deviation report
5. Suggest adjustments to match reference intent

Usage:
    duro_run_skill(skill_name="design_compare_reference", args={
        "file_path": "design.pen",
        "node_id": "screen_001",
        "reference_id": "ref_linear_dashboard",
        # OR
        "reference_pattern": "dashboard",
        "reference_product": "Linear"
    })
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


SKILL_META = {
    "name": "design_compare_reference",
    "description": "Compare current design against stored reference",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["compare to reference", "match reference", "check against reference", "reference comparison"],
    "keywords": ["design", "compare", "reference", "deviation", "match", "taste"],
}

REQUIRES = ["duro_get_artifact", "duro_query_memory", "pencil_batch_get", "pencil_design_tokens"]


@dataclass
class DesignMetrics:
    """Extracted design metrics for comparison."""
    colors: List[str] = field(default_factory=list)
    primary_colors: List[str] = field(default_factory=list)
    spacing_values: List[int] = field(default_factory=list)
    font_sizes: List[int] = field(default_factory=list)
    font_families: List[str] = field(default_factory=list)
    layout_type: str = ""
    has_sidebar: bool = False
    has_cards: bool = False
    dominant_color: str = ""


@dataclass
class Deviation:
    """A detected deviation from reference."""
    category: str  # "color", "spacing", "typography", "layout", "pattern"
    aspect: str  # What specific thing deviated
    reference_value: Any
    current_value: Any
    severity: str  # "high", "medium", "low"
    suggestion: str


@dataclass
class ComparisonResult:
    """Result of design comparison."""
    match_score: float  # 0-100
    deviations: List[Deviation]
    stealable_rules_applied: List[str]
    stealable_rules_missed: List[str]
    overall_assessment: str


def extract_metrics_from_nodes(nodes: List[Dict]) -> DesignMetrics:
    """Extract design metrics from Pencil nodes."""
    metrics = DesignMetrics()

    colors_found = []
    spacing_found = []
    font_sizes_found = []
    font_families_found = set()

    def walk(node):
        if not isinstance(node, dict):
            return

        # Colors
        if "fill" in node:
            fill = node["fill"]
            if isinstance(fill, str) and fill.startswith("#"):
                colors_found.append(fill.lower())

        # Spacing
        if "padding" in node:
            p = node["padding"]
            if isinstance(p, (int, float)):
                spacing_found.append(int(p))
            elif isinstance(p, list):
                spacing_found.extend([int(x) for x in p if isinstance(x, (int, float))])

        if "gap" in node:
            g = node["gap"]
            if isinstance(g, (int, float)):
                spacing_found.append(int(g))

        # Typography
        if "fontSize" in node:
            font_sizes_found.append(int(node["fontSize"]))

        if "fontFamily" in node:
            font_families_found.add(node["fontFamily"])

        # Layout detection
        name = node.get("name", "").lower()
        if "sidebar" in name or "sidenav" in name:
            metrics.has_sidebar = True
        if "card" in name:
            metrics.has_cards = True

        # Recurse
        for child in node.get("children", []):
            walk(child)

    for node in nodes:
        walk(node)

    metrics.colors = list(set(colors_found))
    metrics.spacing_values = sorted(set(spacing_found))
    metrics.font_sizes = sorted(set(font_sizes_found))
    metrics.font_families = list(font_families_found)

    # Determine primary colors (most frequent)
    if colors_found:
        from collections import Counter
        color_counts = Counter(colors_found)
        metrics.primary_colors = [c for c, _ in color_counts.most_common(3)]
        metrics.dominant_color = metrics.primary_colors[0] if metrics.primary_colors else ""

    # Determine layout type
    if metrics.has_sidebar:
        metrics.layout_type = "sidebar_layout"
    elif metrics.has_cards:
        metrics.layout_type = "card_grid"
    else:
        metrics.layout_type = "standard"

    return metrics


def analyze_stealable_rules(
    metrics: DesignMetrics,
    rules: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Check which stealable rules from reference are applied in current design.

    Returns: (applied_rules, missed_rules)
    """
    applied = []
    missed = []

    for rule in rules:
        rule_lower = rule.lower()

        # Check color-related rules
        if "color" in rule_lower or "palette" in rule_lower:
            # Check if limited palette
            if "limited" in rule_lower or "few" in rule_lower:
                if len(metrics.colors) <= 5:
                    applied.append(rule)
                else:
                    missed.append(rule)
            else:
                applied.append(rule)  # Generic color rule, assume applied

        # Check spacing-related rules
        elif "spacing" in rule_lower or "gap" in rule_lower or "padding" in rule_lower:
            # Check for consistent spacing
            if metrics.spacing_values:
                # Check if spacing follows a scale
                if all(s % 4 == 0 for s in metrics.spacing_values if s > 0):
                    applied.append(rule)
                else:
                    missed.append(rule)
            else:
                missed.append(rule)

        # Check typography-related rules
        elif "font" in rule_lower or "typography" in rule_lower:
            if "single" in rule_lower or "one font" in rule_lower:
                if len(metrics.font_families) <= 1:
                    applied.append(rule)
                else:
                    missed.append(rule)
            else:
                applied.append(rule)

        # Check layout-related rules
        elif "sidebar" in rule_lower:
            if metrics.has_sidebar:
                applied.append(rule)
            else:
                missed.append(rule)

        elif "card" in rule_lower:
            if metrics.has_cards:
                applied.append(rule)
            else:
                missed.append(rule)

        else:
            # Can't determine automatically
            applied.append(rule)  # Give benefit of doubt

    return applied, missed


def compare_metrics(
    current: DesignMetrics,
    reference_data: Dict
) -> List[Deviation]:
    """Compare current metrics against reference data."""
    deviations = []

    # Extract reference info
    ref_style_tags = reference_data.get("style_tags", [])
    ref_rules = reference_data.get("stealable_rules", [])
    ref_why_works = reference_data.get("why_it_works", [])

    # Check color palette size
    ref_is_minimal = "minimal" in ref_style_tags or any("limited" in r.lower() for r in ref_rules)
    if ref_is_minimal and len(current.colors) > 6:
        deviations.append(Deviation(
            category="color",
            aspect="palette_size",
            reference_value="5-6 colors (minimal)",
            current_value=f"{len(current.colors)} colors",
            severity="medium",
            suggestion="Reduce color palette to 5-6 colors for minimal aesthetic"
        ))

    # Check dark mode alignment
    ref_is_dark = "dark" in ref_style_tags
    if ref_is_dark:
        # Check if current design uses dark backgrounds
        dark_colors = [c for c in current.colors if c.startswith("#0") or c.startswith("#1") or c.startswith("#2")]
        if len(dark_colors) < 2:
            deviations.append(Deviation(
                category="color",
                aspect="dark_theme",
                reference_value="Dark theme",
                current_value="Light theme",
                severity="high",
                suggestion="Switch to dark background colors (#0x, #1x, #2x range)"
            ))

    # Check spacing consistency
    ref_has_consistent_spacing = any("spacing" in r.lower() and "consist" in r.lower() for r in ref_rules)
    if ref_has_consistent_spacing and current.spacing_values:
        # Check if using 4px or 8px base
        non_standard = [s for s in current.spacing_values if s > 0 and s % 4 != 0]
        if non_standard:
            deviations.append(Deviation(
                category="spacing",
                aspect="consistency",
                reference_value="4px/8px base",
                current_value=f"Non-standard values: {non_standard[:3]}",
                severity="medium",
                suggestion="Use spacing values divisible by 4 or 8"
            ))

    # Check typography simplicity
    ref_has_single_font = any("single font" in r.lower() or "one font" in r.lower() for r in ref_rules)
    if ref_has_single_font and len(current.font_families) > 1:
        deviations.append(Deviation(
            category="typography",
            aspect="font_count",
            reference_value="1 font family",
            current_value=f"{len(current.font_families)} fonts: {current.font_families}",
            severity="low",
            suggestion="Use single font family for cleaner aesthetic"
        ))

    # Check layout pattern
    ref_has_sidebar = any("sidebar" in r.lower() for r in ref_rules)
    if ref_has_sidebar and not current.has_sidebar:
        deviations.append(Deviation(
            category="layout",
            aspect="sidebar",
            reference_value="Has sidebar",
            current_value="No sidebar",
            severity="low",
            suggestion="Consider adding sidebar for navigation consistency"
        ))

    return deviations


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare current design against a stored reference.

    Args:
        args: {
            file_path: str - Path to .pen file
            node_id: str - Node to compare
            reference_id: str - Artifact ID of reference (optional)
            reference_pattern: str - Pattern to search for (optional)
            reference_product: str - Product name to search for (optional)
        }
        tools: {
            duro_get_artifact: func,
            duro_query_memory: func,
            pencil_batch_get: func
        }
        context: execution context

    Returns:
        {success, match_score, deviations, suggestions, report}
    """
    file_path = args.get("file_path", "")
    node_id = args.get("node_id", "")
    reference_id = args.get("reference_id")
    reference_pattern = args.get("reference_pattern")
    reference_product = args.get("reference_product")

    if not node_id:
        return {"success": False, "error": "node_id is required"}

    # === Step 1: Load reference ===
    reference_data = None

    if reference_id:
        get_artifact = tools.get("duro_get_artifact")
        if get_artifact:
            try:
                result = get_artifact(artifact_id=reference_id)
                if isinstance(result, dict):
                    reference_data = result.get("data", result)
            except Exception:
                pass

    if not reference_data and (reference_pattern or reference_product):
        query_memory = tools.get("duro_query_memory")
        if query_memory:
            try:
                search_tags = []
                if reference_pattern:
                    search_tags.append(reference_pattern)

                results = query_memory(
                    artifact_type="design_reference",
                    tags=search_tags if search_tags else None,
                    search_text=reference_product,
                    limit=5
                )

                if results and len(results) > 0:
                    # Find best match
                    for r in results:
                        data = r.get("data", r)
                        if reference_product and reference_product.lower() in data.get("product_name", "").lower():
                            reference_data = data
                            break
                        elif reference_pattern and reference_pattern.lower() == data.get("pattern", "").lower():
                            reference_data = data
                            break

                    if not reference_data:
                        reference_data = results[0].get("data", results[0])

            except Exception:
                pass

    if not reference_data:
        return {
            "success": False,
            "error": "Could not find matching reference. Provide reference_id or valid pattern/product."
        }

    # === Step 2: Get current design metrics ===
    batch_get = tools.get("pencil_batch_get")
    if not batch_get:
        return {"success": False, "error": "pencil_batch_get not available"}

    try:
        nodes = batch_get(filePath=file_path, nodeIds=[node_id], readDepth=10)
        if not nodes:
            return {"success": False, "error": "No nodes found"}

        nodes = nodes if isinstance(nodes, list) else [nodes]
        current_metrics = extract_metrics_from_nodes(nodes)

    except Exception as e:
        return {"success": False, "error": f"Failed to read design: {str(e)}"}

    # === Step 3: Compare against reference ===
    deviations = compare_metrics(current_metrics, reference_data)

    # === Step 4: Analyze stealable rules ===
    stealable_rules = reference_data.get("stealable_rules", [])
    applied_rules, missed_rules = analyze_stealable_rules(current_metrics, stealable_rules)

    # === Step 5: Calculate match score ===
    # Base score starts at 100
    score = 100.0

    # Deduct for deviations
    severity_deductions = {"high": 15, "medium": 10, "low": 5}
    for d in deviations:
        score -= severity_deductions.get(d.severity, 5)

    # Deduct for missed rules
    if stealable_rules:
        rule_score = len(applied_rules) / len(stealable_rules) * 20
        score = score * 0.8 + rule_score

    score = max(0, min(100, score))

    # === Step 6: Generate report ===
    ref_name = reference_data.get("product_name", "Reference")
    ref_pattern = reference_data.get("pattern", "")

    lines = [
        f"# Design Comparison Report",
        f"",
        f"**Reference:** {ref_name} ({ref_pattern})",
        f"**Current:** {node_id}",
        f"**Match Score:** {score:.1f}/100",
        f"",
    ]

    # Style alignment
    ref_style_tags = reference_data.get("style_tags", [])
    lines.append(f"## Style Tags from Reference")
    lines.append(", ".join(ref_style_tags) if ref_style_tags else "None specified")
    lines.append("")

    # Deviations
    if deviations:
        lines.append(f"## Deviations Found ({len(deviations)})")
        for d in deviations:
            lines.append(f"### {d.category.title()}: {d.aspect}")
            lines.append(f"- **Reference:** {d.reference_value}")
            lines.append(f"- **Current:** {d.current_value}")
            lines.append(f"- **Severity:** {d.severity}")
            lines.append(f"- **Suggestion:** {d.suggestion}")
            lines.append("")
    else:
        lines.append("## No Significant Deviations")
        lines.append("Design aligns well with reference.")
        lines.append("")

    # Rules analysis
    lines.append(f"## Stealable Rules Analysis")
    if applied_rules:
        lines.append(f"### Applied ({len(applied_rules)})")
        for rule in applied_rules:
            lines.append(f"- {rule}")
        lines.append("")

    if missed_rules:
        lines.append(f"### Missed ({len(missed_rules)})")
        for rule in missed_rules:
            lines.append(f"- {rule}")
        lines.append("")

    # Overall assessment
    if score >= 85:
        assessment = "Excellent alignment with reference. Minor refinements possible."
    elif score >= 70:
        assessment = "Good alignment. Address medium-severity deviations."
    elif score >= 50:
        assessment = "Moderate alignment. Review and apply more stealable rules."
    else:
        assessment = "Significant deviation from reference. Consider revisiting design direction."

    lines.append(f"## Assessment")
    lines.append(assessment)

    report = "\n".join(lines)

    return {
        "success": True,
        "reference_name": ref_name,
        "reference_pattern": ref_pattern,
        "match_score": round(score, 1),
        "deviations": [
            {
                "category": d.category,
                "aspect": d.aspect,
                "reference_value": str(d.reference_value),
                "current_value": str(d.current_value),
                "severity": d.severity,
                "suggestion": d.suggestion
            }
            for d in deviations
        ],
        "deviations_count": len(deviations),
        "rules_applied": applied_rules,
        "rules_missed": missed_rules,
        "current_metrics": {
            "colors": len(current_metrics.colors),
            "spacing_values": current_metrics.spacing_values[:5],
            "font_families": current_metrics.font_families,
            "layout_type": current_metrics.layout_type
        },
        "report": report
    }


if __name__ == "__main__":
    print("design_compare_reference v1.0.0")
    print("=" * 50)
    print("Compare current design against stored reference")
    print("")
    print("Compares:")
    print("  - Color palette and theme")
    print("  - Spacing consistency")
    print("  - Typography choices")
    print("  - Layout patterns")
    print("  - Stealable rules application")
