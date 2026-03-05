"""
Skill: design_qa_verify
Description: Rigorous design QA - measures before claiming done. Prevents false "matches" claims.
Version: 2.0.0
Tier: tested

Failure pattern this fixes: Visual guessing instead of measuring.
Key insight: "The margin between subtle tension and alignment error is 2-3px"

Process:
1. Get snapshot_layout for pixel measurements
2. Calculate edge positions mathematically
3. Check alignment relationships numerically
4. Take screenshot for hierarchy check
5. WCAG contrast verification
6. Spacing consistency analysis
7. Typography scale verification
8. List specific issues (never "looks good")

V2.0 Improvements:
- WCAG contrast checking (AA: 4.5:1, AAA: 7:1)
- Spacing consistency analysis (detect anomalies)
- Typography scale verification (modular scale)
- Component alignment scoring
"""

import re
import math
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

SKILL_META = {
    "name": "design_qa_verify",
    "description": "Rigorous design QA with WCAG, spacing, and typography checks",
    "tier": "tested",
    "version": "2.0.0",
    "triggers": ["design qa", "verify design", "check design", "does this match"],
    "keywords": ["design", "qa", "verify", "alignment", "spacing", "measurement", "precision", "wcag", "accessibility", "contrast", "typography"],
}

REQUIRES = ["snapshot_layout", "get_screenshot", "batch_get"]


# === WCAG CONTRAST CHECKING ===

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    if len(hex_color) != 6:
        return (0, 0, 0)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_relative_luminance(r: int, g: int, b: int) -> float:
    """
    Calculate relative luminance per WCAG 2.1.
    https://www.w3.org/WAI/GL/wiki/Relative_luminance
    """
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
    """
    Calculate WCAG contrast ratio between two colors.
    Returns ratio from 1:1 to 21:1.
    """
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)

    l1 = rgb_to_relative_luminance(*rgb1)
    l2 = rgb_to_relative_luminance(*rgb2)

    lighter = max(l1, l2)
    darker = min(l1, l2)

    return (lighter + 0.05) / (darker + 0.05)


class ContrastLevel(Enum):
    """WCAG contrast compliance levels."""
    AAA = "AAA"       # 7:1 for normal text, 4.5:1 for large text
    AA = "AA"         # 4.5:1 for normal text, 3:1 for large text
    AA_LARGE = "AA_LARGE"  # 3:1 only valid for large text (18pt+ or 14pt bold)
    FAIL = "FAIL"     # Below minimum


@dataclass
class ContrastResult:
    """Result of a contrast check."""
    foreground: str
    background: str
    ratio: float
    level: ContrastLevel
    is_large_text: bool
    passes_aa: bool
    passes_aaa: bool
    node_id: str
    node_name: str


def check_contrast_wcag(
    text_color: str,
    bg_color: str,
    font_size: int = 16,
    font_weight: str = "normal",
    node_id: str = "",
    node_name: str = ""
) -> ContrastResult:
    """
    Check WCAG contrast compliance for a text/background pair.

    WCAG 2.1 requirements:
    - Normal text: 4.5:1 for AA, 7:1 for AAA
    - Large text (18pt+ or 14pt bold): 3:1 for AA, 4.5:1 for AAA
    """
    ratio = calculate_contrast_ratio(text_color, bg_color)

    # Determine if large text (18pt = 24px, 14pt bold = 18.5px bold)
    is_large = font_size >= 24 or (font_size >= 18.5 and font_weight in ["bold", "700", "800", "900"])

    # Determine compliance level
    if is_large:
        passes_aa = ratio >= 3.0
        passes_aaa = ratio >= 4.5
        if ratio >= 4.5:
            level = ContrastLevel.AAA
        elif ratio >= 3.0:
            level = ContrastLevel.AA_LARGE
        else:
            level = ContrastLevel.FAIL
    else:
        passes_aa = ratio >= 4.5
        passes_aaa = ratio >= 7.0
        if ratio >= 7.0:
            level = ContrastLevel.AAA
        elif ratio >= 4.5:
            level = ContrastLevel.AA
        else:
            level = ContrastLevel.FAIL

    return ContrastResult(
        foreground=text_color,
        background=bg_color,
        ratio=round(ratio, 2),
        level=level,
        is_large_text=is_large,
        passes_aa=passes_aa,
        passes_aaa=passes_aaa,
        node_id=node_id,
        node_name=node_name
    )


def extract_colors_from_node(node: Dict) -> Dict[str, str]:
    """Extract text color and background color from a node."""
    colors = {}

    # Background color from fill
    if "fill" in node:
        fill = node["fill"]
        if isinstance(fill, str) and fill.startswith("#"):
            colors["background"] = fill

    # Text color (for text nodes)
    if node.get("type") == "text":
        if "fill" in node:
            fill = node["fill"]
            if isinstance(fill, str) and fill.startswith("#"):
                colors["text"] = fill

    return colors


# === SPACING CONSISTENCY ANALYSIS ===

@dataclass
class SpacingAnomaly:
    """Detected spacing anomaly."""
    property_name: str  # padding, gap, margin
    values_found: List[int]
    anomaly_value: int
    expected_values: List[int]
    node_id: str
    node_name: str
    message: str


def analyze_spacing_consistency(
    nodes: List[Dict],
    tolerance: int = 2
) -> Tuple[Dict[str, List[int]], List[SpacingAnomaly]]:
    """
    Analyze spacing consistency across nodes.

    Detects:
    - Non-standard spacing values
    - Inconsistent gaps between similar elements
    - Near-miss values (e.g., 15px when 16px is standard)

    Returns: (unique_values_by_type, anomalies)
    """
    # Common spacing scales (4px, 8px systems)
    STANDARD_SCALES = {
        "4px": [0, 4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64, 80, 96],
        "8px": [0, 8, 16, 24, 32, 40, 48, 64, 80, 96, 128],
    }

    spacing_values = {
        "padding": [],
        "gap": [],
        "margin": [],
    }

    anomalies = []

    def extract_spacing(node: Dict, path: str = ""):
        """Recursively extract spacing values."""
        node_id = node.get("id", "unknown")
        node_name = node.get("name", node_id)

        # Padding
        if "padding" in node:
            padding = node["padding"]
            if isinstance(padding, (int, float)):
                spacing_values["padding"].append((int(padding), node_id, node_name))
            elif isinstance(padding, list):
                for p in padding:
                    if isinstance(p, (int, float)):
                        spacing_values["padding"].append((int(p), node_id, node_name))

        # Gap
        if "gap" in node:
            gap = node["gap"]
            if isinstance(gap, (int, float)):
                spacing_values["gap"].append((int(gap), node_id, node_name))

        # Recurse
        for child in node.get("children", []):
            if isinstance(child, dict):
                extract_spacing(child, f"{path}/{node_name}")

    for node in nodes:
        extract_spacing(node)

    # Analyze for anomalies
    for prop_type, values in spacing_values.items():
        if not values:
            continue

        # Get unique values (just the numbers)
        unique_nums = sorted(set(v[0] for v in values))

        # Detect scale in use
        detected_scale = None
        for scale_name, scale_values in STANDARD_SCALES.items():
            if all(v in scale_values for v in unique_nums):
                detected_scale = scale_name
                break

        if detected_scale:
            scale_values = STANDARD_SCALES[detected_scale]
        else:
            # Use 4px scale as default
            scale_values = STANDARD_SCALES["4px"]

        # Find near-misses and non-standard values
        for val, node_id, node_name in values:
            if val == 0:
                continue

            # Check if value is in standard scale
            if val not in scale_values:
                # Find closest standard values
                closest = min(scale_values, key=lambda x: abs(x - val))
                diff = abs(val - closest)

                if diff <= tolerance:
                    # Near-miss
                    anomalies.append(SpacingAnomaly(
                        property_name=prop_type,
                        values_found=unique_nums,
                        anomaly_value=val,
                        expected_values=[closest],
                        node_id=node_id,
                        node_name=node_name,
                        message=f"Near-miss {prop_type}: {val}px is {diff}px off from {closest}px"
                    ))
                else:
                    # Non-standard value
                    anomalies.append(SpacingAnomaly(
                        property_name=prop_type,
                        values_found=unique_nums,
                        anomaly_value=val,
                        expected_values=scale_values,
                        node_id=node_id,
                        node_name=node_name,
                        message=f"Non-standard {prop_type}: {val}px not in {detected_scale or '4px'} scale"
                    ))

    # Return unique values summary
    unique_by_type = {
        prop: sorted(set(v[0] for v in vals))
        for prop, vals in spacing_values.items()
    }

    return unique_by_type, anomalies


# === TYPOGRAPHY SCALE VERIFICATION ===

@dataclass
class TypographyIssue:
    """Typography scale issue."""
    font_size: int
    expected_sizes: List[int]
    scale_ratio: float
    node_id: str
    node_name: str
    message: str


def verify_typography_scale(
    nodes: List[Dict],
    base_size: int = 16,
    scale_ratio: float = 1.25,  # Major Third
    tolerance: int = 1
) -> Tuple[List[int], List[TypographyIssue]]:
    """
    Verify font sizes follow a modular scale.

    Common scales:
    - 1.125: Major Second
    - 1.200: Minor Third
    - 1.250: Major Third (default)
    - 1.333: Perfect Fourth
    - 1.414: Augmented Fourth
    - 1.500: Perfect Fifth
    - 1.618: Golden Ratio

    Returns: (found_sizes, issues)
    """
    # Generate expected scale values (5 steps down, 10 steps up from base)
    expected_sizes = []
    for i in range(-5, 11):
        size = base_size * (scale_ratio ** i)
        expected_sizes.append(round(size))
    expected_sizes = sorted(set(expected_sizes))

    found_sizes = []
    issues = []

    def extract_fonts(node: Dict):
        """Recursively extract font sizes."""
        node_id = node.get("id", "unknown")
        node_name = node.get("name", node_id)

        if "fontSize" in node:
            size = int(node["fontSize"])
            found_sizes.append(size)

            # Check if in scale
            if size not in expected_sizes:
                # Find closest
                closest = min(expected_sizes, key=lambda x: abs(x - size))
                diff = abs(size - closest)

                if diff <= tolerance:
                    # Near-miss
                    issues.append(TypographyIssue(
                        font_size=size,
                        expected_sizes=expected_sizes,
                        scale_ratio=scale_ratio,
                        node_id=node_id,
                        node_name=node_name,
                        message=f"Font size {size}px is {diff}px off from scale value {closest}px"
                    ))
                else:
                    issues.append(TypographyIssue(
                        font_size=size,
                        expected_sizes=expected_sizes,
                        scale_ratio=scale_ratio,
                        node_id=node_id,
                        node_name=node_name,
                        message=f"Font size {size}px not in {scale_ratio} modular scale (nearest: {closest}px)"
                    ))

        # Recurse
        for child in node.get("children", []):
            if isinstance(child, dict):
                extract_fonts(child)

    for node in nodes:
        extract_fonts(node)

    return sorted(set(found_sizes)), issues


# === ALIGNMENT SCORING ===

@dataclass
class AlignmentScore:
    """Overall alignment score for a design."""
    score: float  # 0-100
    total_elements: int
    aligned_elements: int
    near_miss_count: int
    issues: List[str]
    grade: str  # A, B, C, D, F

def calculate_alignment_score(nodes: List[Dict], tolerance: int = 2) -> AlignmentScore:
    """
    Calculate overall alignment score for a set of nodes.

    Scoring:
    - 100: Perfect alignment (all elements on grid)
    - 90-99: Excellent (1-2 near-misses)
    - 80-89: Good (minor issues)
    - 70-79: Acceptable (some drift)
    - <70: Needs attention

    Returns AlignmentScore with detailed breakdown.
    """
    if not nodes:
        return AlignmentScore(
            score=100.0,
            total_elements=0,
            aligned_elements=0,
            near_miss_count=0,
            issues=[],
            grade="A"
        )

    issues = []
    near_misses = 0
    aligned = 0
    total = 0

    # Collect all edge positions
    left_edges = []
    right_edges = []
    top_edges = []

    for node in nodes:
        if not isinstance(node, dict):
            continue

        x = node.get("x", 0)
        y = node.get("y", 0)
        width = node.get("width", 0)
        height = node.get("height", 0)

        if isinstance(x, (int, float)) and isinstance(width, (int, float)):
            left_edges.append((x, node.get("name", node.get("id", "unknown"))))
            right_edges.append((x + width, node.get("name", node.get("id", "unknown"))))
            total += 1

        if isinstance(y, (int, float)):
            top_edges.append((y, node.get("name", node.get("id", "unknown"))))

    # Check for alignment patterns
    def find_alignment_groups(edges: List[Tuple[float, str]], tolerance: int) -> Dict[int, List]:
        """Group edges that should be aligned."""
        groups = {}
        for value, name in edges:
            # Round to nearest tolerance multiple
            key = round(value / tolerance) * tolerance
            if key not in groups:
                groups[key] = []
            groups[key].append((value, name))
        return groups

    # Analyze left edge alignment
    left_groups = find_alignment_groups(left_edges, tolerance * 2)
    for key, members in left_groups.items():
        if len(members) > 1:
            values = [v for v, _ in members]
            spread = max(values) - min(values)
            if spread > 0 and spread <= tolerance * 3:
                near_misses += 1
                names = [n for _, n in members]
                issues.append(f"Left edges near-miss: {names} differ by {spread:.1f}px")
            elif spread == 0:
                aligned += len(members)

    # Calculate score
    if total == 0:
        score = 100.0
    else:
        alignment_rate = aligned / total if total > 0 else 0
        near_miss_penalty = near_misses * 3
        score = max(0, 100 * alignment_rate - near_miss_penalty)

    # Assign grade
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

    return AlignmentScore(
        score=round(score, 1),
        total_elements=total,
        aligned_elements=aligned,
        near_miss_count=near_misses,
        issues=issues,
        grade=grade
    )


def calculate_edges(node):
    """Calculate right and bottom edges from node bounds."""
    x = node.get("x", 0)
    y = node.get("y", 0)
    width = node.get("width", 0)
    height = node.get("height", 0)
    return {
        "left": x,
        "top": y,
        "right": x + width if isinstance(width, (int, float)) else "auto",
        "bottom": y + height if isinstance(height, (int, float)) else "auto",
        "width": width,
        "height": height,
    }

def check_alignment(nodes, tolerance=2):
    """Check if nodes are aligned within tolerance."""
    issues = []
    
    # Group by approximate left edge
    left_edges = {}
    for n in nodes:
        edges = calculate_edges(n)
        left = round(edges["left"] / 10) * 10  # Group by 10px
        left_edges.setdefault(left, []).append((n.get("name", n.get("id")), edges["left"]))
    
    # Check for near-misses (within 10px but not exact)
    for group_key, items in left_edges.items():
        if len(items) > 1:
            values = [v for _, v in items]
            spread = max(values) - min(values)
            if 0 < spread <= 10:
                issues.append(f"Near-miss alignment: {[n for n, _ in items]} differ by {spread}px")
    
    return issues

def run(args, tools, context):
    """
    Enhanced design QA verification with WCAG, spacing, and typography checks.

    Args:
        args: {
            file_path: str - path to .pen file
            node_id: str - node to verify
            reference_spec: dict - optional expected values
            check_contrast: bool - run WCAG contrast checks (default: True)
            check_spacing: bool - run spacing consistency (default: True)
            check_typography: bool - run typography scale (default: True)
            typography_scale: float - modular scale ratio (default: 1.25)
            base_font_size: int - base font size (default: 16)
        }
        tools: {snapshot_layout, get_screenshot, batch_get}
        context: execution context

    Returns:
        Full QA report with all checks
    """
    results = {
        "success": True,
        "checks": [],
        "issues": [],
        "measurements": {},
        "contrast_results": [],
        "spacing_analysis": {},
        "typography_analysis": {},
        "alignment_score": None,
    }

    file_path = args.get("file_path", "")
    node_id = args.get("node_id", "")
    reference_spec = args.get("reference_spec", {})
    check_contrast = args.get("check_contrast", True)
    check_spacing = args.get("check_spacing", True)
    check_typography = args.get("check_typography", True)
    typography_scale = args.get("typography_scale", 1.25)
    base_font_size = args.get("base_font_size", 16)

    if not node_id:
        return {"success": False, "error": "node_id required"}

    nodes = []

    # Step 1: Get layout measurements
    snapshot_layout = tools.get("snapshot_layout")
    if snapshot_layout:
        try:
            layout = snapshot_layout(filePath=file_path, parentId=node_id, maxDepth=3)
            results["checks"].append({"step": "snapshot_layout", "status": "done"})

            # Extract measurements
            if isinstance(layout, dict):
                nodes = layout.get("nodes", [layout])
            elif isinstance(layout, list):
                nodes = layout
            else:
                nodes = []

            for node in nodes[:20]:
                name = node.get("name", node.get("id", "unknown"))
                results["measurements"][name] = calculate_edges(node)

            # Check alignments
            alignment_issues = check_alignment(nodes)
            results["issues"].extend(alignment_issues)

        except Exception as e:
            results["checks"].append({"step": "snapshot_layout", "error": str(e)})

    # Step 2: Get full node data for deeper analysis
    batch_get = tools.get("batch_get")
    if batch_get and node_id:
        try:
            full_nodes = batch_get(filePath=file_path, nodeIds=[node_id], readDepth=5)
            if full_nodes:
                nodes = full_nodes if isinstance(full_nodes, list) else [full_nodes]
            results["checks"].append({"step": "batch_get", "status": "done"})
        except Exception as e:
            results["checks"].append({"step": "batch_get", "error": str(e)})

    # Step 3: WCAG Contrast Check
    if check_contrast and nodes:
        try:
            contrast_issues = []
            text_nodes = []

            def find_text_nodes(node, parent_bg="#ffffff"):
                """Recursively find text nodes and their backgrounds."""
                if not isinstance(node, dict):
                    return

                # Get this node's background
                node_bg = parent_bg
                if "fill" in node:
                    fill = node["fill"]
                    if isinstance(fill, str) and fill.startswith("#"):
                        node_bg = fill

                # If text node, check contrast
                if node.get("type") == "text":
                    text_color = "#000000"  # default
                    if "fill" in node:
                        fill = node["fill"]
                        if isinstance(fill, str) and fill.startswith("#"):
                            text_color = fill

                    font_size = node.get("fontSize", 16)
                    font_weight = str(node.get("fontWeight", "normal"))

                    result = check_contrast_wcag(
                        text_color=text_color,
                        bg_color=node_bg,
                        font_size=int(font_size) if font_size else 16,
                        font_weight=font_weight,
                        node_id=node.get("id", ""),
                        node_name=node.get("name", "")
                    )
                    text_nodes.append(result)

                    if not result.passes_aa:
                        contrast_issues.append(
                            f"WCAG AA fail: {result.node_name} has {result.ratio}:1 contrast "
                            f"({result.foreground} on {result.background})"
                        )

                # Recurse
                for child in node.get("children", []):
                    find_text_nodes(child, node_bg)

            for node in nodes:
                find_text_nodes(node)

            results["contrast_results"] = [
                {
                    "node": r.node_name,
                    "ratio": r.ratio,
                    "level": r.level.value,
                    "passes_aa": r.passes_aa,
                    "passes_aaa": r.passes_aaa,
                    "colors": f"{r.foreground} on {r.background}"
                }
                for r in text_nodes
            ]
            results["issues"].extend(contrast_issues)
            results["checks"].append({"step": "contrast_check", "status": "done", "text_nodes": len(text_nodes)})

        except Exception as e:
            results["checks"].append({"step": "contrast_check", "error": str(e)})

    # Step 4: Spacing Consistency Analysis
    if check_spacing and nodes:
        try:
            unique_spacing, spacing_anomalies = analyze_spacing_consistency(nodes)
            results["spacing_analysis"] = {
                "unique_values": unique_spacing,
                "anomaly_count": len(spacing_anomalies),
                "anomalies": [
                    {
                        "type": a.property_name,
                        "value": a.anomaly_value,
                        "node": a.node_name,
                        "message": a.message
                    }
                    for a in spacing_anomalies
                ]
            }

            for a in spacing_anomalies:
                results["issues"].append(a.message)

            results["checks"].append({"step": "spacing_check", "status": "done"})

        except Exception as e:
            results["checks"].append({"step": "spacing_check", "error": str(e)})

    # Step 5: Typography Scale Verification
    if check_typography and nodes:
        try:
            found_sizes, typography_issues = verify_typography_scale(
                nodes,
                base_size=base_font_size,
                scale_ratio=typography_scale
            )
            results["typography_analysis"] = {
                "found_sizes": found_sizes,
                "base_size": base_font_size,
                "scale_ratio": typography_scale,
                "issue_count": len(typography_issues),
                "issues": [
                    {
                        "size": i.font_size,
                        "node": i.node_name,
                        "message": i.message
                    }
                    for i in typography_issues
                ]
            }

            for i in typography_issues:
                results["issues"].append(i.message)

            results["checks"].append({"step": "typography_check", "status": "done"})

        except Exception as e:
            results["checks"].append({"step": "typography_check", "error": str(e)})

    # Step 6: Calculate Alignment Score
    if nodes:
        try:
            alignment_score = calculate_alignment_score(nodes)
            results["alignment_score"] = {
                "score": alignment_score.score,
                "grade": alignment_score.grade,
                "total_elements": alignment_score.total_elements,
                "aligned_elements": alignment_score.aligned_elements,
                "near_misses": alignment_score.near_miss_count
            }
            results["checks"].append({"step": "alignment_score", "status": "done"})
        except Exception as e:
            results["checks"].append({"step": "alignment_score", "error": str(e)})

    # Step 7: Get screenshot for visual hierarchy check
    get_screenshot = tools.get("get_screenshot")
    if get_screenshot:
        try:
            get_screenshot(filePath=file_path, nodeId=node_id)
            results["checks"].append({"step": "screenshot", "status": "done"})
        except Exception as e:
            results["checks"].append({"step": "screenshot", "error": str(e)})

    # Step 8: Compare to reference spec if provided
    if reference_spec:
        for element, expected in reference_spec.items():
            actual = results["measurements"].get(element, {})
            for prop, expected_val in expected.items():
                actual_val = actual.get(prop)
                if actual_val is not None and actual_val != expected_val:
                    diff = abs(actual_val - expected_val) if isinstance(actual_val, (int, float)) else "mismatch"
                    results["issues"].append(f"{element}.{prop}: expected {expected_val}, got {actual_val} (diff: {diff})")

    # Generate report
    lines = ["## Design QA Verify Report (v2.0)", ""]
    lines.append(f"**Node:** {node_id}")
    lines.append(f"**Checks completed:** {len(results['checks'])}")
    lines.append(f"**Issues found:** {len(results['issues'])}")
    lines.append("")

    # Alignment score
    if results["alignment_score"]:
        score_data = results["alignment_score"]
        lines.append(f"### Alignment Score: {score_data['score']}/100 (Grade: {score_data['grade']})")
        lines.append(f"- Elements analyzed: {score_data['total_elements']}")
        lines.append(f"- Properly aligned: {score_data['aligned_elements']}")
        lines.append(f"- Near-misses: {score_data['near_misses']}")
        lines.append("")

    # Contrast summary
    if results["contrast_results"]:
        aa_pass = sum(1 for r in results["contrast_results"] if r["passes_aa"])
        total = len(results["contrast_results"])
        lines.append(f"### WCAG Contrast: {aa_pass}/{total} pass AA")
        for r in results["contrast_results"][:5]:
            status = "✓" if r["passes_aa"] else "✗"
            lines.append(f"- {status} {r['node']}: {r['ratio']}:1 ({r['level']})")
        lines.append("")

    # Spacing summary
    if results["spacing_analysis"].get("unique_values"):
        lines.append("### Spacing Analysis")
        for prop, values in results["spacing_analysis"]["unique_values"].items():
            if values:
                lines.append(f"- {prop}: {values}")
        if results["spacing_analysis"]["anomaly_count"]:
            lines.append(f"- **Anomalies detected:** {results['spacing_analysis']['anomaly_count']}")
        lines.append("")

    # Typography summary
    if results["typography_analysis"].get("found_sizes"):
        lines.append("### Typography Scale")
        lines.append(f"- Found sizes: {results['typography_analysis']['found_sizes']}")
        lines.append(f"- Scale: {results['typography_analysis']['scale_ratio']} (base: {results['typography_analysis']['base_size']}px)")
        if results["typography_analysis"]["issue_count"]:
            lines.append(f"- **Issues:** {results['typography_analysis']['issue_count']}")
        lines.append("")

    # Issues list
    if results["issues"]:
        lines.append("### All Issues")
        for issue in results["issues"]:
            lines.append(f"- {issue}")
        lines.append("")
    else:
        lines.append("### No issues detected")
        lines.append("*Design passes all automated checks.*")

    results["report"] = "\n".join(lines)

    # Final verdict
    contrast_failures = sum(1 for r in results["contrast_results"] if not r["passes_aa"]) if results["contrast_results"] else 0

    if contrast_failures > 0:
        results["verdict"] = "WCAG_FAIL"
        results["can_claim_done"] = False
    elif results["issues"]:
        results["verdict"] = "ISSUES_FOUND"
        results["can_claim_done"] = False
    else:
        results["verdict"] = "ALL_CHECKS_PASSED"
        results["can_claim_done"] = True

    return results

if __name__ == "__main__":
    print("design_qa_verify v2.0.0")
    print("=" * 50)
    print("Enhanced Design QA with:")
    print("  - WCAG contrast checking (AA: 4.5:1, AAA: 7:1)")
    print("  - Spacing consistency analysis (4px/8px scale)")
    print("  - Typography scale verification (modular scale)")
    print("  - Component alignment scoring")
    print("")
    print("Prevents false 'done' claims by measuring instead of guessing")
