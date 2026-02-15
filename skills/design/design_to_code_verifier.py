"""
Skill: design_to_code_verifier
Description: Compare Pencil designs to implemented code and detect drift
Version: 1.0.0
Tier: core

This skill closes the design-to-code feedback loop by:
1. Extracting design tokens from .pen files (colors, spacing, typography, border-radius)
2. Scanning React/TSX components for CSS values
3. Detecting drift between design and implementation
4. Generating fix suggestions

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function

Usage via orchestrator:
    duro_run_skill(skill_name="design_to_code_verifier", args={
        "pen_file": "path/to/design.pen",
        "code_dir": "path/to/src/components",
        "node_id": "optional_specific_node"
    })
"""

import re
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


# Skill metadata
SKILL_META = {
    "name": "design_to_code_verifier",
    "description": "Compare Pencil designs to code and detect drift",
    "tier": "core",
    "version": "1.0.0",
    "author": "duro",
    "triggers": ["verify design", "check implementation", "design drift", "code matches design"],
}

# Required capabilities
REQUIRES = ["pencil_batch_get", "read_file", "glob_files"]


class DriftSeverity(Enum):
    """Severity levels for design drift."""
    INFO = "info"           # Minor difference, likely intentional
    WARNING = "warning"     # Noticeable difference, should review
    ERROR = "error"         # Significant drift, needs attention
    CRITICAL = "critical"   # Breaks design system, must fix


class TokenType(Enum):
    """Types of design tokens to verify."""
    COLOR = "color"
    SPACING = "spacing"
    FONT_SIZE = "font_size"
    FONT_FAMILY = "font_family"
    FONT_WEIGHT = "font_weight"
    BORDER_RADIUS = "border_radius"
    GAP = "gap"
    PADDING = "padding"
    WIDTH = "width"
    HEIGHT = "height"


@dataclass
class DesignToken:
    """A single design token extracted from .pen file."""
    token_type: TokenType
    value: Any
    node_id: str
    node_name: str
    path: str  # e.g., "Button/Primary/label"


@dataclass
class CodeToken:
    """A token found in code."""
    token_type: TokenType
    value: Any
    file_path: str
    line_number: int
    context: str  # The surrounding code


@dataclass
class DriftReport:
    """Report of drift between design and code."""
    severity: DriftSeverity
    token_type: TokenType
    design_value: Any
    code_value: Any
    design_location: str  # node path in .pen
    code_location: str    # file:line
    message: str
    suggestion: Optional[str] = None


@dataclass
class VerificationResult:
    """Complete verification result."""
    success: bool
    pen_file: str
    code_dir: str
    tokens_checked: int
    tokens_matched: int
    drifts: List[DriftReport] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    summary: str = ""


# Color normalization utilities
def normalize_color(color: str) -> str:
    """Normalize color to lowercase hex format."""
    if not color:
        return ""

    color = str(color).strip().lower()

    # Handle CSS variables - extract the variable name
    if color.startswith("var("):
        return color

    # Handle Pencil variables (start with $)
    if color.startswith("$"):
        return color.lower()

    # Handle hex colors
    if color.startswith("#"):
        # Expand shorthand hex
        if len(color) == 4:
            color = f"#{color[1]*2}{color[2]*2}{color[3]*2}"
        return color.lower()

    # Handle rgb/rgba
    if color.startswith("rgb"):
        # Extract numbers and convert to hex
        numbers = re.findall(r'\d+', color)
        if len(numbers) >= 3:
            r, g, b = int(numbers[0]), int(numbers[1]), int(numbers[2])
            return f"#{r:02x}{g:02x}{b:02x}"

    return color


def normalize_spacing(value: Any) -> List[int]:
    """Normalize spacing/padding to [top, right, bottom, left] format."""
    if isinstance(value, (int, float)):
        v = int(value)
        return [v, v, v, v]

    if isinstance(value, list):
        if len(value) == 1:
            return [value[0]] * 4
        elif len(value) == 2:
            return [value[0], value[1], value[0], value[1]]
        elif len(value) == 4:
            return list(value)
        else:
            return list(value) + [0] * (4 - len(value))

    return [0, 0, 0, 0]


def colors_match(design_color: str, code_color: str, tolerance: int = 0, css_var_map: Dict[str, str] = None) -> bool:
    """Check if two colors match, with optional tolerance for RGB values."""
    dc = normalize_color(design_color)
    cc = normalize_color(code_color)

    # Direct match
    if dc == cc:
        return True

    # Check variable mapping
    # e.g., "$--primary" in design might map to "var(--color-primary)" in code
    if dc.startswith("$") and cc.startswith("var("):
        design_var = dc[1:].replace("--", "").replace("-", "")
        code_var = cc.replace("var(", "").replace(")", "").replace("--color-", "").replace("-", "")
        return design_var.lower() == code_var.lower()

    # Check if code uses CSS variable that maps to design hex color
    # Common MSJ-style mapping: #8B5CF6 -> var(--color-primary)
    default_css_var_map = {
        "#8b5cf6": ["var(--color-primary)", "var(--primary)"],
        "#14b8a6": ["var(--color-secondary)", "var(--secondary)"],
        "#18181b": ["var(--color-text-primary)", "var(--color-foreground)"],
        "#71717a": ["var(--color-text-secondary)", "var(--color-muted-foreground)"],
        "#a1a1aa": ["var(--color-text-muted)"],
        "#ffffff": ["var(--color-background)", "var(--color-primary-foreground)", "white"],
        "#fafafa": ["var(--color-card)"],
        "#f4f4f5": ["var(--color-muted)"],
        "#e4e4e7": ["var(--color-border)"],
    }

    # Merge with provided map
    var_map = {**default_css_var_map, **(css_var_map or {})}

    # Check if design hex matches code CSS variable
    if dc in var_map:
        for var in var_map[dc]:
            if var.lower() in cc.lower() or cc.lower() in var.lower():
                return True

    # Check if code has CSS variable pattern
    if "var(--color-" in cc:
        # Extract variable name and check against hex
        for hex_color, vars in var_map.items():
            if dc == hex_color and any(v in cc for v in vars):
                return True

    return False


def spacing_matches(design_spacing: Any, code_spacing: str) -> bool:
    """Check if spacing values match."""
    design_norm = normalize_spacing(design_spacing)

    # Parse code spacing (e.g., "px-4 py-3" or "p-4" or direct values)
    code_values = []

    # Handle Tailwind classes
    tailwind_spacing = {
        '0': 0, '0.5': 2, '1': 4, '1.5': 6, '2': 8, '2.5': 10,
        '3': 12, '3.5': 14, '4': 16, '5': 20, '6': 24, '7': 28,
        '8': 32, '9': 36, '10': 40, '11': 44, '12': 48, '14': 56,
        '16': 64, '20': 80, '24': 96
    }

    # Check for p-X pattern
    p_match = re.search(r'\bp-(\d+(?:\.\d+)?)\b', code_spacing)
    if p_match:
        val = tailwind_spacing.get(p_match.group(1), int(float(p_match.group(1)) * 4))
        return design_norm == [val, val, val, val]

    # Check for px-X py-Y pattern
    px_match = re.search(r'\bpx-(\d+(?:\.\d+)?)\b', code_spacing)
    py_match = re.search(r'\bpy-(\d+(?:\.\d+)?)\b', code_spacing)
    if px_match or py_match:
        px = tailwind_spacing.get(px_match.group(1), 0) if px_match else 0
        py = tailwind_spacing.get(py_match.group(1), 0) if py_match else 0
        return design_norm == [py, px, py, px]

    # Check for direct pixel values
    px_values = re.findall(r'(\d+)px', code_spacing)
    if px_values:
        return normalize_spacing([int(v) for v in px_values]) == design_norm

    return False


# Design token extraction
def extract_design_tokens(node: Dict, path: str = "") -> List[DesignToken]:
    """Extract design tokens from a .pen node recursively."""
    tokens = []

    node_id = node.get("id", "unknown")
    node_name = node.get("name", node_id)
    current_path = f"{path}/{node_name}" if path else node_name

    # Extract color tokens
    if "fill" in node:
        fill = node["fill"]
        if isinstance(fill, str):
            tokens.append(DesignToken(
                token_type=TokenType.COLOR,
                value=fill,
                node_id=node_id,
                node_name=node_name,
                path=current_path
            ))

    # Extract text color
    if node.get("type") == "text" and "fill" in node:
        tokens.append(DesignToken(
            token_type=TokenType.COLOR,
            value=node["fill"],
            node_id=node_id,
            node_name=node_name,
            path=f"{current_path}/text-color"
        ))

    # Extract font properties
    if "fontSize" in node:
        tokens.append(DesignToken(
            token_type=TokenType.FONT_SIZE,
            value=node["fontSize"],
            node_id=node_id,
            node_name=node_name,
            path=current_path
        ))

    if "fontFamily" in node:
        tokens.append(DesignToken(
            token_type=TokenType.FONT_FAMILY,
            value=node["fontFamily"],
            node_id=node_id,
            node_name=node_name,
            path=current_path
        ))

    if "fontWeight" in node:
        tokens.append(DesignToken(
            token_type=TokenType.FONT_WEIGHT,
            value=node["fontWeight"],
            node_id=node_id,
            node_name=node_name,
            path=current_path
        ))

    # Extract spacing
    if "padding" in node:
        tokens.append(DesignToken(
            token_type=TokenType.PADDING,
            value=node["padding"],
            node_id=node_id,
            node_name=node_name,
            path=current_path
        ))

    if "gap" in node:
        tokens.append(DesignToken(
            token_type=TokenType.GAP,
            value=node["gap"],
            node_id=node_id,
            node_name=node_name,
            path=current_path
        ))

    # Extract border radius
    if "cornerRadius" in node:
        tokens.append(DesignToken(
            token_type=TokenType.BORDER_RADIUS,
            value=node["cornerRadius"],
            node_id=node_id,
            node_name=node_name,
            path=current_path
        ))

    # Extract dimensions
    if "width" in node and not node.get("width", "").startswith("fill"):
        tokens.append(DesignToken(
            token_type=TokenType.WIDTH,
            value=node["width"],
            node_id=node_id,
            node_name=node_name,
            path=current_path
        ))

    if "height" in node and not str(node.get("height", "")).startswith("fill"):
        tokens.append(DesignToken(
            token_type=TokenType.HEIGHT,
            value=node["height"],
            node_id=node_id,
            node_name=node_name,
            path=current_path
        ))

    # Recurse into children
    children = node.get("children", [])
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                tokens.extend(extract_design_tokens(child, current_path))

    return tokens


# Code scanning patterns
CODE_PATTERNS = {
    TokenType.COLOR: [
        r'(?:bg|text|border|fill|stroke)-\[([^\]]+)\]',  # Tailwind arbitrary: bg-[#8B5CF6]
        r'#[0-9A-Fa-f]{3,8}\b',  # Hex colors
        r'var\(--[\w-]+\)',  # CSS variables
        r'rgb\([^)]+\)',  # RGB
        r'rgba\([^)]+\)',  # RGBA
    ],
    TokenType.FONT_SIZE: [
        r'text-\[(\d+)px\]',  # text-[14px]
        r'fontSize:\s*(\d+)',  # fontSize: 14
        r'font-size:\s*(\d+)px',  # font-size: 14px
    ],
    TokenType.FONT_FAMILY: [
        r'font-(?:display|body|sans|serif|mono)',  # Tailwind font classes
        r'fontFamily:\s*["\']([^"\']+)["\']',  # fontFamily: "Inter"
        r'font-family:\s*([^;]+);',  # font-family: Inter;
    ],
    TokenType.BORDER_RADIUS: [
        r'rounded-\[(\d+)px\]',  # rounded-[16px]
        r'rounded-(?:none|sm|md|lg|xl|2xl|3xl|full)',  # Tailwind rounded
        r'borderRadius:\s*(\d+)',  # borderRadius: 16
        r'border-radius:\s*(\d+)px',  # border-radius: 16px
    ],
    TokenType.GAP: [
        r'gap-(\d+(?:\.\d+)?)',  # gap-4
        r'gap-\[(\d+)px\]',  # gap-[16px]
        r'gap:\s*(\d+)',  # gap: 16
    ],
    TokenType.PADDING: [
        r'p-(\d+(?:\.\d+)?)',  # p-4
        r'px-(\d+(?:\.\d+)?)',  # px-4
        r'py-(\d+(?:\.\d+)?)',  # py-4
        r'p-\[(\d+)px\]',  # p-[16px]
        r'padding:\s*([^;]+);',  # padding: 16px;
    ],
}


def scan_code_for_tokens(
    content: str,
    file_path: str,
    token_types: Optional[List[TokenType]] = None
) -> List[CodeToken]:
    """Scan code content for design tokens."""
    tokens = []
    lines = content.split('\n')

    search_types = token_types or list(CODE_PATTERNS.keys())

    for line_num, line in enumerate(lines, 1):
        for token_type in search_types:
            patterns = CODE_PATTERNS.get(token_type, [])
            for pattern in patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    tokens.append(CodeToken(
                        token_type=token_type,
                        value=match.group(0),
                        file_path=file_path,
                        line_number=line_num,
                        context=line.strip()
                    ))

    return tokens


def compare_tokens(
    design_tokens: List[DesignToken],
    code_tokens: List[CodeToken],
    component_name: str
) -> List[DriftReport]:
    """Compare design tokens to code tokens and report drift."""
    drifts = []

    # Group tokens by type
    design_by_type: Dict[TokenType, List[DesignToken]] = {}
    code_by_type: Dict[TokenType, List[CodeToken]] = {}

    for dt in design_tokens:
        design_by_type.setdefault(dt.token_type, []).append(dt)

    for ct in code_tokens:
        code_by_type.setdefault(ct.token_type, []).append(ct)

    # Check colors - need to check ALL code tokens, not just COLOR type
    # since CSS variables appear in various contexts
    all_code_values = " ".join([str(ct.value) + " " + str(ct.context) for ct in code_tokens])

    for design_color in design_by_type.get(TokenType.COLOR, []):
        found_match = False

        # Check against color tokens
        for code_color in code_by_type.get(TokenType.COLOR, []):
            if colors_match(design_color.value, code_color.value):
                found_match = True
                break

        # Also check if color appears in any code context (CSS variables)
        if not found_match:
            if colors_match(design_color.value, all_code_values):
                found_match = True

        if not found_match and not str(design_color.value).startswith("$"):
            # Only report if it's a concrete color, not a variable
            drifts.append(DriftReport(
                severity=DriftSeverity.WARNING,
                token_type=TokenType.COLOR,
                design_value=design_color.value,
                code_value="not found",
                design_location=design_color.path,
                code_location=f"{component_name}",
                message=f"Color {design_color.value} from design not found in code",
                suggestion=f"Add color: {design_color.value}"
            ))

    # Check font sizes
    for design_fs in design_by_type.get(TokenType.FONT_SIZE, []):
        found_match = False
        for code_fs in code_by_type.get(TokenType.FONT_SIZE, []):
            # Extract numeric value from code
            code_val = re.search(r'(\d+)', str(code_fs.value))
            if code_val and int(code_val.group(1)) == int(design_fs.value):
                found_match = True
                break

        if not found_match:
            drifts.append(DriftReport(
                severity=DriftSeverity.WARNING,
                token_type=TokenType.FONT_SIZE,
                design_value=f"{design_fs.value}px",
                code_value="not found or different",
                design_location=design_fs.path,
                code_location=component_name,
                message=f"Font size {design_fs.value}px from design may not match code",
                suggestion=f"Use text-[{design_fs.value}px] or fontSize: {design_fs.value}"
            ))

    # Check border radius
    for design_br in design_by_type.get(TokenType.BORDER_RADIUS, []):
        design_val = design_br.value
        found_match = False

        for code_br in code_by_type.get(TokenType.BORDER_RADIUS, []):
            code_val_match = re.search(r'(\d+)', str(code_br.value))
            if code_val_match and int(code_val_match.group(1)) == int(design_val):
                found_match = True
                break
            # Check Tailwind rounded classes
            tailwind_rounded = {
                'rounded-none': 0, 'rounded-sm': 2, 'rounded': 4,
                'rounded-md': 6, 'rounded-lg': 8, 'rounded-xl': 12,
                'rounded-2xl': 16, 'rounded-3xl': 24, 'rounded-full': 9999
            }
            for tw_class, tw_val in tailwind_rounded.items():
                if tw_class in str(code_br.value) and tw_val == int(design_val):
                    found_match = True
                    break

        if not found_match:
            drifts.append(DriftReport(
                severity=DriftSeverity.INFO,
                token_type=TokenType.BORDER_RADIUS,
                design_value=f"{design_val}px",
                code_value="not found or different",
                design_location=design_br.path,
                code_location=component_name,
                message=f"Border radius {design_val}px from design may differ",
                suggestion=f"Use rounded-[{design_val}px]"
            ))

    return drifts


def generate_summary(result: VerificationResult) -> str:
    """Generate a human-readable summary."""
    lines = [
        f"Design-to-Code Verification Report",
        f"=" * 40,
        f"Design file: {result.pen_file}",
        f"Code directory: {result.code_dir}",
        f"",
        f"Tokens checked: {result.tokens_checked}",
        f"Tokens matched: {result.tokens_matched}",
        f"Match rate: {result.tokens_matched / max(result.tokens_checked, 1) * 100:.1f}%",
        f"",
    ]

    if result.drifts:
        lines.append(f"Drift detected: {len(result.drifts)} issues")
        lines.append("")

        # Group by severity
        by_severity = {}
        for drift in result.drifts:
            by_severity.setdefault(drift.severity.value, []).append(drift)

        for severity in ['critical', 'error', 'warning', 'info']:
            items = by_severity.get(severity, [])
            if items:
                lines.append(f"  [{severity.upper()}] ({len(items)} items)")
                for drift in items[:5]:  # Show first 5
                    lines.append(f"    - {drift.message}")
                    if drift.suggestion:
                        lines.append(f"      Suggestion: {drift.suggestion}")
                if len(items) > 5:
                    lines.append(f"    ... and {len(items) - 5} more")
                lines.append("")
    else:
        lines.append("No drift detected - code matches design!")

    if result.errors:
        lines.append(f"Errors: {len(result.errors)}")
        for err in result.errors[:3]:
            lines.append(f"  - {err}")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            pen_file: str - path to .pen file
            code_dir: str - path to code directory
            node_id: str (optional) - specific node to check
            component_filter: str (optional) - regex to filter components
        }
        tools: {
            pencil_batch_get: callable - read from .pen files
            read_file: callable - read code files
            glob_files: callable - find files by pattern
        }
        context: {run_id, constraints}

    Returns:
        {success, report, summary, drifts_count, match_rate, errors}
    """
    pen_file = args.get("pen_file", "")
    code_dir = args.get("code_dir", "")
    node_id = args.get("node_id")
    component_filter = args.get("component_filter", r".*\.(tsx|jsx)$")

    if not pen_file:
        return {"success": False, "error": "pen_file is required"}
    if not code_dir:
        return {"success": False, "error": "code_dir is required"}

    result = VerificationResult(
        success=True,
        pen_file=pen_file,
        code_dir=code_dir,
        tokens_checked=0,
        tokens_matched=0
    )

    # Step 1: Extract design tokens from .pen file
    try:
        if node_id:
            pen_result = tools["pencil_batch_get"](
                filePath=pen_file,
                nodeIds=[node_id],
                readDepth=10
            )
        else:
            # Get reusable components
            pen_result = tools["pencil_batch_get"](
                filePath=pen_file,
                patterns=[{"reusable": True}],
                readDepth=5,
                searchDepth=5
            )

        if not pen_result:
            result.errors.append("No nodes found in .pen file")
            result.success = False
            return _format_result(result)

        design_tokens = []
        for node in pen_result:
            design_tokens.extend(extract_design_tokens(node))

        result.tokens_checked = len(design_tokens)

    except Exception as e:
        result.errors.append(f"Failed to read .pen file: {str(e)}")
        result.success = False
        return _format_result(result)

    # Step 2: Find and scan code files
    try:
        code_files = tools["glob_files"](
            pattern=f"**/*.tsx",
            path=code_dir
        )

        if not code_files:
            code_files = tools["glob_files"](
                pattern=f"**/*.jsx",
                path=code_dir
            )

        if not code_files:
            result.errors.append("No TSX/JSX files found in code directory")
            result.success = False
            return _format_result(result)

        all_code_tokens = []
        for code_file in code_files:
            try:
                content = tools["read_file"](code_file)
                tokens = scan_code_for_tokens(content, code_file)
                all_code_tokens.extend(tokens)
            except Exception as e:
                result.errors.append(f"Failed to read {code_file}: {str(e)}")

    except Exception as e:
        result.errors.append(f"Failed to scan code files: {str(e)}")
        result.success = False
        return _format_result(result)

    # Step 3: Compare tokens
    result.drifts = compare_tokens(
        design_tokens,
        all_code_tokens,
        os.path.basename(code_dir)
    )

    # Calculate match rate
    result.tokens_matched = result.tokens_checked - len(result.drifts)

    # Generate summary
    result.summary = generate_summary(result)

    return _format_result(result)


def _format_result(result: VerificationResult) -> Dict[str, Any]:
    """Format result for return."""
    return {
        "success": result.success and len(result.errors) == 0,
        "summary": result.summary,
        "tokens_checked": result.tokens_checked,
        "tokens_matched": result.tokens_matched,
        "match_rate": result.tokens_matched / max(result.tokens_checked, 1),
        "drifts_count": len(result.drifts),
        "drifts": [
            {
                "severity": d.severity.value,
                "type": d.token_type.value,
                "design_value": str(d.design_value),
                "code_value": str(d.code_value),
                "design_location": d.design_location,
                "code_location": d.code_location,
                "message": d.message,
                "suggestion": d.suggestion
            }
            for d in result.drifts
        ],
        "errors": result.errors
    }


# Standalone verification function for direct use
def verify_design_to_code(
    pen_file: str,
    code_dir: str,
    pencil_get_func,
    read_func,
    glob_func,
    node_id: Optional[str] = None
) -> VerificationResult:
    """
    Standalone function for direct verification.

    Args:
        pen_file: Path to .pen design file
        code_dir: Path to code directory
        pencil_get_func: Function to read from .pen files
        read_func: Function to read code files
        glob_func: Function to find files
        node_id: Optional specific node to check

    Returns:
        VerificationResult with full report
    """
    tools = {
        "pencil_batch_get": pencil_get_func,
        "read_file": read_func,
        "glob_files": glob_func
    }

    result = run(
        args={"pen_file": pen_file, "code_dir": code_dir, "node_id": node_id},
        tools=tools,
        context={}
    )

    return result


if __name__ == "__main__":
    print("design_to_code_verifier Skill v1.0")
    print("=" * 40)
    print(f"Requires: {REQUIRES}")
    print("\nToken types checked:")
    for tt in TokenType:
        print(f"  - {tt.value}")
    print("\nSeverity levels:")
    for ds in DriftSeverity:
        print(f"  - {ds.value}")
    print("\nUsage:")
    print("  Run via Duro orchestrator:")
    print("    duro_run_skill(skill_name='design_to_code_verifier', args={")
    print("        'pen_file': 'designs/app.pen',")
    print("        'code_dir': 'src/components'")
    print("    })")
