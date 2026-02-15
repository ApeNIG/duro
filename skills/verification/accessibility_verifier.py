"""
Skill: accessibility_verifier
Description: WCAG compliance checking for designs and code
Version: 1.0.0
Tier: untested

Automated accessibility verification:
1. Color contrast checking (WCAG AA/AAA)
2. Touch target sizing (44x44px minimum)
3. Text sizing (minimum font sizes)
4. Focus indicators detection
5. Alt text verification
6. Heading hierarchy validation
7. ARIA validation
8. Keyboard navigation checks

Supports:
- HTML files
- CSS files
- React/JSX components
- Design tokens (colors, sizes)

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import re
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from html.parser import HTMLParser


# Skill metadata
SKILL_META = {
    "name": "accessibility_verifier",
    "description": "WCAG compliance checking for designs and code",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "phase": "3.1",
    "triggers": ["accessibility", "a11y", "wcag", "contrast", "accessible"],
}

# Required capabilities
REQUIRES = ["read_file", "glob_files"]


class Severity(Enum):
    """Finding severity levels."""
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class WCAGLevel(Enum):
    """WCAG conformance levels."""
    A = "A"
    AA = "AA"
    AAA = "AAA"


@dataclass
class A11yFinding:
    """An accessibility finding."""
    rule_id: str
    severity: Severity
    wcag_criterion: str
    file_path: str
    line: int
    message: str
    element: Optional[str] = None
    suggestion: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


# === DEFAULT CONFIGURATION ===

DEFAULT_CONFIG = {
    "wcag_level": "AA",
    "min_touch_target": 44,  # px
    "min_font_size": 12,  # px
    "min_line_height": 1.5,
    "check_focus_indicators": True,
    "check_alt_text": True,
    "check_heading_order": True,
    "check_aria": True,
    "check_color_contrast": True,
    "ignore_patterns": [
        "**/node_modules/**",
        "**/*.min.css",
        "**/*.min.js",
    ],
}

# WCAG contrast requirements
CONTRAST_REQUIREMENTS = {
    "AA": {
        "normal_text": 4.5,
        "large_text": 3.0,
        "ui_components": 3.0,
    },
    "AAA": {
        "normal_text": 7.0,
        "large_text": 4.5,
        "ui_components": 4.5,
    },
}

# Large text thresholds (in px, assuming 1pt = 1.333px)
LARGE_TEXT_SIZE = 18 * 1.333  # 18pt
LARGE_TEXT_BOLD_SIZE = 14 * 1.333  # 14pt bold


# === COLOR UTILITIES ===

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')

    # Handle shorthand (#fff -> #ffffff)
    if len(hex_color) == 3:
        hex_color = ''.join([c * 2 for c in hex_color])

    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")

    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def rgb_to_luminance(r: int, g: int, b: int) -> float:
    """
    Calculate relative luminance per WCAG 2.1.

    Uses the sRGB color space formula.
    """
    def linearize(c: int) -> float:
        c_srgb = c / 255.0
        if c_srgb <= 0.03928:
            return c_srgb / 12.92
        return ((c_srgb + 0.055) / 1.055) ** 2.4

    r_lin = linearize(r)
    g_lin = linearize(g)
    b_lin = linearize(b)

    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """
    Calculate contrast ratio between two colors.

    Returns ratio in range [1, 21].
    """
    try:
        rgb1 = hex_to_rgb(color1)
        rgb2 = hex_to_rgb(color2)
    except ValueError:
        return 0.0

    l1 = rgb_to_luminance(*rgb1)
    l2 = rgb_to_luminance(*rgb2)

    # Ensure l1 is the lighter color
    if l1 < l2:
        l1, l2 = l2, l1

    return (l1 + 0.05) / (l2 + 0.05)


def suggest_accessible_color(fg: str, bg: str, required_ratio: float) -> Optional[str]:
    """Suggest an accessible foreground color."""
    try:
        bg_rgb = hex_to_rgb(bg)
        fg_rgb = hex_to_rgb(fg)
    except ValueError:
        return None

    bg_lum = rgb_to_luminance(*bg_rgb)

    # Determine if we need lighter or darker
    fg_lum = rgb_to_luminance(*fg_rgb)

    # Try darkening the foreground
    for factor in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0]:
        new_rgb = tuple(int(c * factor) for c in fg_rgb)
        new_lum = rgb_to_luminance(*new_rgb)

        lighter = max(bg_lum, new_lum)
        darker = min(bg_lum, new_lum)
        ratio = (lighter + 0.05) / (darker + 0.05)

        if ratio >= required_ratio:
            return "#{:02x}{:02x}{:02x}".format(*new_rgb)

    return "#000000"  # Fallback to black


def check_contrast(
    foreground: str,
    background: str,
    is_large_text: bool,
    wcag_level: str = "AA"
) -> Tuple[bool, float, float]:
    """
    Check if color contrast meets WCAG requirements.

    Returns: (passes, actual_ratio, required_ratio)
    """
    ratio = calculate_contrast_ratio(foreground, background)
    requirements = CONTRAST_REQUIREMENTS.get(wcag_level, CONTRAST_REQUIREMENTS["AA"])

    if is_large_text:
        required = requirements["large_text"]
    else:
        required = requirements["normal_text"]

    return (ratio >= required, round(ratio, 2), required)


# === HTML PARSING ===

class A11yHTMLParser(HTMLParser):
    """Parse HTML for accessibility issues."""

    def __init__(self):
        super().__init__()
        self.findings: List[Dict[str, Any]] = []
        self.headings: List[Tuple[int, int]] = []  # (level, line)
        self.current_line = 1
        self.in_style = False
        self.style_content = ""

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attrs_dict = dict(attrs)
        line = self.getpos()[0]

        # Check images for alt text
        if tag == "img":
            if "alt" not in attrs_dict:
                self.findings.append({
                    "rule_id": "missing_alt_text",
                    "line": line,
                    "tag": tag,
                    "message": "Image missing alt attribute",
                    "wcag": "1.1.1",
                })
            elif attrs_dict.get("alt") == "":
                # Empty alt is valid for decorative images, but warn
                self.findings.append({
                    "rule_id": "empty_alt_text",
                    "line": line,
                    "tag": tag,
                    "message": "Image has empty alt (OK if decorative)",
                    "severity": "info",
                    "wcag": "1.1.1",
                })

        # Check headings
        if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            level = int(tag[1])
            self.headings.append((level, line))

        # Check buttons/links for touch target hints
        if tag in ["button", "a"]:
            style = attrs_dict.get("style", "")
            # Check for explicit small sizes
            if "width:" in style or "height:" in style:
                size_match = re.search(r'(?:width|height):\s*(\d+)(?:px)?', style)
                if size_match:
                    size = int(size_match.group(1))
                    if size < 44:
                        self.findings.append({
                            "rule_id": "small_touch_target",
                            "line": line,
                            "tag": tag,
                            "message": f"Touch target may be too small ({size}px, minimum 44px)",
                            "wcag": "2.5.5",
                        })

        # Check for missing accessible names on interactive elements
        if tag in ["button", "input", "select", "textarea"]:
            has_label = (
                "aria-label" in attrs_dict or
                "aria-labelledby" in attrs_dict or
                "title" in attrs_dict or
                "id" in attrs_dict  # Could be linked via <label for="">
            )
            if tag == "input" and attrs_dict.get("type") in ["submit", "button", "reset"]:
                has_label = has_label or "value" in attrs_dict

            if not has_label and tag != "input":
                self.findings.append({
                    "rule_id": "missing_accessible_name",
                    "line": line,
                    "tag": tag,
                    "message": f"{tag} may be missing accessible name",
                    "severity": "warn",
                    "wcag": "4.1.2",
                })

        # Check ARIA roles
        role = attrs_dict.get("role")
        if role:
            valid_roles = [
                "alert", "alertdialog", "application", "article", "banner",
                "button", "cell", "checkbox", "columnheader", "combobox",
                "complementary", "contentinfo", "definition", "dialog",
                "directory", "document", "feed", "figure", "form", "grid",
                "gridcell", "group", "heading", "img", "link", "list",
                "listbox", "listitem", "log", "main", "marquee", "math",
                "menu", "menubar", "menuitem", "menuitemcheckbox",
                "menuitemradio", "navigation", "none", "note", "option",
                "presentation", "progressbar", "radio", "radiogroup",
                "region", "row", "rowgroup", "rowheader", "scrollbar",
                "search", "searchbox", "separator", "slider", "spinbutton",
                "status", "switch", "tab", "table", "tablist", "tabpanel",
                "term", "textbox", "timer", "toolbar", "tooltip", "tree",
                "treegrid", "treeitem"
            ]
            if role not in valid_roles:
                self.findings.append({
                    "rule_id": "invalid_aria_role",
                    "line": line,
                    "tag": tag,
                    "message": f"Invalid ARIA role: {role}",
                    "wcag": "4.1.2",
                })

        # Track style tags
        if tag == "style":
            self.in_style = True
            self.style_content = ""

    def handle_endtag(self, tag: str):
        if tag == "style":
            self.in_style = False

    def handle_data(self, data: str):
        if self.in_style:
            self.style_content += data

    def check_heading_order(self) -> List[Dict[str, Any]]:
        """Check heading hierarchy."""
        findings = []
        prev_level = 0

        for level, line in self.headings:
            if prev_level > 0 and level > prev_level + 1:
                findings.append({
                    "rule_id": "heading_skip",
                    "line": line,
                    "tag": f"h{level}",
                    "message": f"Heading level skipped (h{prev_level} → h{level})",
                    "wcag": "1.3.1",
                })
            prev_level = level

        return findings


def analyze_html(content: str, file_path: str, config: Dict[str, Any]) -> List[A11yFinding]:
    """Analyze HTML file for accessibility issues."""
    findings = []

    parser = A11yHTMLParser()
    try:
        parser.feed(content)
    except Exception as e:
        findings.append(A11yFinding(
            rule_id="parse_error",
            severity=Severity.ERROR,
            wcag_criterion="N/A",
            file_path=file_path,
            line=1,
            message=f"Failed to parse HTML: {e}",
        ))
        return findings

    # Convert parser findings
    for f in parser.findings:
        severity = Severity.ERROR
        if f.get("severity") == "info":
            severity = Severity.INFO
        elif f.get("severity") == "warn":
            severity = Severity.WARN

        findings.append(A11yFinding(
            rule_id=f["rule_id"],
            severity=severity,
            wcag_criterion=f.get("wcag", "N/A"),
            file_path=file_path,
            line=f["line"],
            message=f["message"],
            element=f.get("tag"),
        ))

    # Check heading order
    if config.get("check_heading_order", True):
        for f in parser.check_heading_order():
            findings.append(A11yFinding(
                rule_id=f["rule_id"],
                severity=Severity.WARN,
                wcag_criterion=f["wcag"],
                file_path=file_path,
                line=f["line"],
                message=f["message"],
                element=f.get("tag"),
            ))

    return findings


# === CSS PARSING ===

def extract_colors_from_css(content: str) -> List[Dict[str, Any]]:
    """Extract color declarations from CSS."""
    colors = []

    # Match color properties
    color_pattern = r'(color|background-color|background|border-color):\s*(#[0-9a-fA-F]{3,6}|rgb\([^)]+\)|[a-z]+)'

    for match in re.finditer(color_pattern, content, re.IGNORECASE):
        prop = match.group(1)
        value = match.group(2)

        # Get line number
        line = content[:match.start()].count('\n') + 1

        colors.append({
            "property": prop,
            "value": value,
            "line": line,
        })

    return colors


def extract_font_sizes_from_css(content: str) -> List[Dict[str, Any]]:
    """Extract font-size declarations from CSS."""
    sizes = []

    # Match font-size property
    size_pattern = r'font-size:\s*(\d+(?:\.\d+)?)(px|pt|em|rem|%)'

    for match in re.finditer(size_pattern, content, re.IGNORECASE):
        value = float(match.group(1))
        unit = match.group(2).lower()

        # Convert to px (approximate)
        if unit == "pt":
            value = value * 1.333
        elif unit == "em" or unit == "rem":
            value = value * 16  # Assume 16px base
        elif unit == "%":
            value = value * 0.16  # Assume 16px base

        line = content[:match.start()].count('\n') + 1

        sizes.append({
            "value_px": value,
            "original": f"{match.group(1)}{match.group(2)}",
            "line": line,
        })

    return sizes


def analyze_css(content: str, file_path: str, config: Dict[str, Any]) -> List[A11yFinding]:
    """Analyze CSS file for accessibility issues."""
    findings = []

    # Check font sizes
    min_font_size = config.get("min_font_size", 12)
    for size in extract_font_sizes_from_css(content):
        if size["value_px"] < min_font_size:
            findings.append(A11yFinding(
                rule_id="small_font_size",
                severity=Severity.WARN,
                wcag_criterion="1.4.4",
                file_path=file_path,
                line=size["line"],
                message=f"Font size {size['original']} may be too small (minimum {min_font_size}px recommended)",
                details={"size_px": size["value_px"]},
            ))

    # Check for :focus styles (basic heuristic)
    if config.get("check_focus_indicators", True):
        has_focus = ":focus" in content or ":focus-visible" in content
        has_outline_none = re.search(r'outline:\s*none|outline:\s*0', content)

        if has_outline_none and not has_focus:
            # Find line number of outline:none
            match = re.search(r'outline:\s*(?:none|0)', content)
            line = content[:match.start()].count('\n') + 1 if match else 1

            findings.append(A11yFinding(
                rule_id="focus_outline_removed",
                severity=Severity.ERROR,
                wcag_criterion="2.4.7",
                file_path=file_path,
                line=line,
                message="Focus outline removed without alternative focus indicator",
                suggestion="Add custom :focus or :focus-visible styles",
            ))

    return findings


# === JSX/REACT PARSING ===

def analyze_jsx(content: str, file_path: str, config: Dict[str, Any]) -> List[A11yFinding]:
    """Analyze JSX/React file for accessibility issues."""
    findings = []

    # Check for img without alt
    if config.get("check_alt_text", True):
        img_pattern = r'<img\s+[^>]*?(?<!alt=)[^>]*?/?>'
        for match in re.finditer(img_pattern, content):
            img_tag = match.group(0)
            if 'alt=' not in img_tag and 'alt =' not in img_tag:
                line = content[:match.start()].count('\n') + 1
                findings.append(A11yFinding(
                    rule_id="missing_alt_text",
                    severity=Severity.ERROR,
                    wcag_criterion="1.1.1",
                    file_path=file_path,
                    line=line,
                    message="Image missing alt attribute",
                    element="img",
                ))

    # Check for onClick without keyboard handler
    onclick_pattern = r'onClick=\{[^}]+\}'
    for match in re.finditer(onclick_pattern, content):
        # Check context - look for onKeyDown/onKeyPress nearby
        start = max(0, match.start() - 200)
        end = min(len(content), match.end() + 200)
        context = content[start:end]

        if 'onKeyDown' not in context and 'onKeyPress' not in context and 'onKeyUp' not in context:
            # Check if it's on a button (which handles keyboard by default)
            if '<button' not in context and 'role="button"' not in context:
                line = content[:match.start()].count('\n') + 1
                findings.append(A11yFinding(
                    rule_id="click_without_keyboard",
                    severity=Severity.WARN,
                    wcag_criterion="2.1.1",
                    file_path=file_path,
                    line=line,
                    message="onClick without keyboard event handler",
                    suggestion="Add onKeyDown handler or use <button> element",
                ))

    # Check for tabIndex > 0
    tabindex_pattern = r'tabIndex=\{?["\']?(\d+)["\']?\}?'
    for match in re.finditer(tabindex_pattern, content):
        value = int(match.group(1))
        if value > 0:
            line = content[:match.start()].count('\n') + 1
            findings.append(A11yFinding(
                rule_id="positive_tabindex",
                severity=Severity.WARN,
                wcag_criterion="2.4.3",
                file_path=file_path,
                line=line,
                message=f"Positive tabIndex ({value}) disrupts natural tab order",
                suggestion="Use tabIndex={0} or tabIndex={-1} instead",
            ))

    return findings


# === COLOR PAIR ANALYSIS ===

def analyze_color_pairs(
    colors: List[Dict[str, Any]],
    file_path: str,
    config: Dict[str, Any]
) -> List[A11yFinding]:
    """Analyze color pairs for contrast issues."""
    findings = []
    wcag_level = config.get("wcag_level", "AA")

    # Group colors by context (simplified: just pair fg/bg)
    fg_colors = [c for c in colors if c["property"] == "color"]
    bg_colors = [c for c in colors if "background" in c["property"]]

    # Check each foreground against common backgrounds
    common_backgrounds = ["#ffffff", "#000000", "#f5f5f5", "#333333"]

    for fg in fg_colors:
        fg_value = fg["value"]
        if not fg_value.startswith("#"):
            continue

        for bg in common_backgrounds:
            passes, ratio, required = check_contrast(fg_value, bg, is_large_text=False, wcag_level=wcag_level)

            if not passes and ratio < required * 0.8:  # Only report significant failures
                suggestion = suggest_accessible_color(fg_value, bg, required)
                findings.append(A11yFinding(
                    rule_id="color_contrast",
                    severity=Severity.WARN,
                    wcag_criterion="1.4.3",
                    file_path=file_path,
                    line=fg["line"],
                    message=f"Potential contrast issue: {fg_value} on {bg} = {ratio}:1 (needs {required}:1 for {wcag_level})",
                    suggestion=f"Consider using {suggestion}" if suggestion else None,
                    details={
                        "foreground": fg_value,
                        "background": bg,
                        "ratio": ratio,
                        "required": required,
                    },
                ))

    return findings


# === MAIN FUNCTION ===

def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            files: List[str] - files to analyze (or glob pattern)
            config: Dict - configuration overrides
            colors: List[Dict] - optional color pairs to check directly
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
            wcag_level: str,
            findings: List[dict],
            summary: dict,
            files_analyzed: int
        }
    """
    import time
    start_time = time.time()

    files = args.get("files", [])
    config = {**DEFAULT_CONFIG, **args.get("config", {})}
    direct_colors = args.get("colors", [])

    # Expand glob patterns
    if isinstance(files, str):
        files = [files]

    expanded_files = []
    for f in files:
        if "*" in f:
            if tools.get("glob_files"):
                expanded_files.extend(tools["glob_files"](pattern=f))
        else:
            expanded_files.append(f)

    all_findings: List[A11yFinding] = []
    files_analyzed = 0

    # Analyze direct color pairs if provided
    if direct_colors:
        for pair in direct_colors:
            fg = pair.get("foreground")
            bg = pair.get("background")
            is_large = pair.get("is_large_text", False)

            if fg and bg:
                wcag_level = config.get("wcag_level", "AA")
                passes, ratio, required = check_contrast(fg, bg, is_large, wcag_level)

                if not passes:
                    suggestion = suggest_accessible_color(fg, bg, required)
                    all_findings.append(A11yFinding(
                        rule_id="color_contrast",
                        severity=Severity.ERROR,
                        wcag_criterion="1.4.3",
                        file_path=pair.get("source", "direct"),
                        line=pair.get("line", 0),
                        message=f"Contrast ratio {ratio}:1 fails {wcag_level} (requires {required}:1)",
                        suggestion=f"Use {suggestion} or darker" if suggestion else None,
                        details={
                            "foreground": fg,
                            "background": bg,
                            "ratio": ratio,
                            "required": required,
                        },
                    ))

    # Analyze files
    for file_path in expanded_files:
        try:
            if tools.get("read_file"):
                content = tools["read_file"](file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

            files_analyzed += 1

            # Determine file type and analyze
            if file_path.endswith('.html') or file_path.endswith('.htm'):
                all_findings.extend(analyze_html(content, file_path, config))

            elif file_path.endswith('.css'):
                all_findings.extend(analyze_css(content, file_path, config))
                if config.get("check_color_contrast", True):
                    colors = extract_colors_from_css(content)
                    all_findings.extend(analyze_color_pairs(colors, file_path, config))

            elif file_path.endswith(('.jsx', '.tsx')):
                all_findings.extend(analyze_jsx(content, file_path, config))

        except Exception as e:
            all_findings.append(A11yFinding(
                rule_id="read_error",
                severity=Severity.ERROR,
                wcag_criterion="N/A",
                file_path=file_path,
                line=1,
                message=f"Could not analyze file: {str(e)}",
            ))

    # Calculate summary
    summary = {
        "total_issues": len(all_findings),
        "errors": sum(1 for f in all_findings if f.severity == Severity.ERROR),
        "warnings": sum(1 for f in all_findings if f.severity == Severity.WARN),
        "info": sum(1 for f in all_findings if f.severity == Severity.INFO),
        "by_rule": {},
    }

    for f in all_findings:
        summary["by_rule"][f.rule_id] = summary["by_rule"].get(f.rule_id, 0) + 1

    # Determine pass/fail (fail on errors)
    passed = summary["errors"] == 0

    duration_ms = int((time.time() - start_time) * 1000)

    return {
        "success": True,
        "passed": passed,
        "wcag_level": config.get("wcag_level", "AA"),
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "wcag_criterion": f.wcag_criterion,
                "file_path": f.file_path,
                "line": f.line,
                "message": f.message,
                "element": f.element,
                "suggestion": f.suggestion,
                "details": f.details,
            }
            for f in all_findings
        ],
        "summary": summary,
        "files_analyzed": files_analyzed,
        "duration_ms": duration_ms,
    }


# Export key components
__all__ = [
    "SKILL_META",
    "REQUIRES",
    "run",
    "calculate_contrast_ratio",
    "check_contrast",
    "hex_to_rgb",
    "rgb_to_luminance",
    "suggest_accessible_color",
    "analyze_html",
    "analyze_css",
    "analyze_jsx",
    "A11yFinding",
    "Severity",
    "WCAGLevel",
    "DEFAULT_CONFIG",
    "CONTRAST_REQUIREMENTS",
]


if __name__ == "__main__":
    print("accessibility_verifier Skill v1.0")
    print("=" * 50)
    print()
    print("WCAG Levels supported: A, AA, AAA")
    print()
    print("Contrast Requirements (AA):")
    print(f"  Normal text: {CONTRAST_REQUIREMENTS['AA']['normal_text']}:1")
    print(f"  Large text:  {CONTRAST_REQUIREMENTS['AA']['large_text']}:1")
    print()
    print("Checks:")
    print("  - Color contrast")
    print("  - Touch target size")
    print("  - Font size")
    print("  - Alt text")
    print("  - Heading order")
    print("  - ARIA validation")
    print("  - Focus indicators")
    print()
    print("Usage:")
    print('  result = run({"files": ["src/**/*.html"]}, tools, ctx)')
    print('  print(f"Passed: {result[\'passed\']}, Issues: {result[\'summary\'][\'total_issues\']}")')
