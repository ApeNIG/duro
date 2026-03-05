"""
Skill: pencil_design_tokens
Description: Extract and manage design tokens from Pencil files.
Version: 1.0.0
Tier: tested

Purpose: Extract design tokens (colors, spacing, typography, radii) from Pencil
files and compare against code tokens to detect drift.

Process:
1. Read current .pen file variables
2. Extract: colors, spacing, typography, radii
3. Store as fact in Duro memory
4. Compare against project's code tokens (if provided)
5. Flag drift between design and code

Usage:
    duro_run_skill(skill_name="pencil_design_tokens", args={
        "file_path": "design.pen",
        "code_tokens_path": "src/styles/tokens.ts",
        "store_as_fact": True
    })
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


SKILL_META = {
    "name": "pencil_design_tokens",
    "description": "Extract and manage design tokens from Pencil files",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["extract tokens", "design tokens", "get tokens", "token drift"],
    "keywords": ["design", "tokens", "colors", "spacing", "typography", "pencil", "drift"],
}

REQUIRES = ["pencil_get_variables", "pencil_batch_get", "duro_store_fact", "read_file"]


@dataclass
class DesignTokens:
    """Extracted design tokens."""
    colors: Dict[str, str] = field(default_factory=dict)
    spacing: Dict[str, int] = field(default_factory=dict)
    typography: Dict[str, Any] = field(default_factory=dict)
    radii: Dict[str, int] = field(default_factory=dict)
    shadows: Dict[str, str] = field(default_factory=dict)
    source: str = ""
    extracted_at: str = ""


@dataclass
class TokenDrift:
    """Detected token drift between design and code."""
    token_type: str
    token_name: str
    design_value: Any
    code_value: Any
    drift_type: str  # "missing_in_code", "missing_in_design", "value_mismatch"
    severity: str  # "high", "medium", "low"


def extract_colors_from_variables(variables: Dict) -> Dict[str, str]:
    """Extract color tokens from Pencil variables."""
    colors = {}

    for name, value in variables.items():
        # Check if it's a color value
        if isinstance(value, str):
            if value.startswith("#") or value.startswith("rgb") or value.startswith("hsl"):
                # Normalize name
                clean_name = name.replace("--", "").replace("-", "_")
                colors[clean_name] = value.lower() if value.startswith("#") else value

    return colors


def extract_spacing_from_variables(variables: Dict) -> Dict[str, int]:
    """Extract spacing tokens from Pencil variables."""
    spacing = {}

    spacing_keywords = ["spacing", "space", "gap", "padding", "margin", "size"]

    for name, value in variables.items():
        name_lower = name.lower()

        # Check if it's a spacing variable
        if any(kw in name_lower for kw in spacing_keywords):
            if isinstance(value, (int, float)):
                clean_name = name.replace("--", "").replace("-", "_")
                spacing[clean_name] = int(value)
            elif isinstance(value, str) and "px" in value:
                # Extract number from "16px"
                match = re.match(r"(\d+)px", value)
                if match:
                    clean_name = name.replace("--", "").replace("-", "_")
                    spacing[clean_name] = int(match.group(1))

    return spacing


def extract_typography_from_variables(variables: Dict) -> Dict[str, Any]:
    """Extract typography tokens from Pencil variables."""
    typography = {
        "font_families": {},
        "font_sizes": {},
        "font_weights": {},
        "line_heights": {},
    }

    for name, value in variables.items():
        name_lower = name.lower()

        if "font-family" in name_lower or "fontfamily" in name_lower:
            clean_name = name.replace("--", "").replace("-", "_")
            typography["font_families"][clean_name] = value

        elif "font-size" in name_lower or "fontsize" in name_lower:
            clean_name = name.replace("--", "").replace("-", "_")
            if isinstance(value, (int, float)):
                typography["font_sizes"][clean_name] = int(value)
            elif isinstance(value, str) and "px" in value:
                match = re.match(r"(\d+)px", value)
                if match:
                    typography["font_sizes"][clean_name] = int(match.group(1))

        elif "font-weight" in name_lower or "fontweight" in name_lower:
            clean_name = name.replace("--", "").replace("-", "_")
            typography["font_weights"][clean_name] = value

        elif "line-height" in name_lower or "lineheight" in name_lower:
            clean_name = name.replace("--", "").replace("-", "_")
            typography["line_heights"][clean_name] = value

    return typography


def extract_radii_from_variables(variables: Dict) -> Dict[str, int]:
    """Extract border radius tokens from Pencil variables."""
    radii = {}

    radius_keywords = ["radius", "rounded", "corner"]

    for name, value in variables.items():
        name_lower = name.lower()

        if any(kw in name_lower for kw in radius_keywords):
            if isinstance(value, (int, float)):
                clean_name = name.replace("--", "").replace("-", "_")
                radii[clean_name] = int(value)
            elif isinstance(value, str) and "px" in value:
                match = re.match(r"(\d+)px", value)
                if match:
                    clean_name = name.replace("--", "").replace("-", "_")
                    radii[clean_name] = int(match.group(1))

    return radii


def parse_code_tokens(content: str, file_type: str = "ts") -> DesignTokens:
    """
    Parse design tokens from code file.

    Supports:
    - TypeScript/JavaScript token files
    - CSS variables
    - Tailwind config
    """
    tokens = DesignTokens()

    if file_type in ["ts", "js"]:
        # Parse object definitions
        # Look for colors: { ... }
        colors_match = re.search(r'colors?\s*[=:]\s*\{([^}]+)\}', content, re.DOTALL)
        if colors_match:
            pairs = re.findall(r'(\w+)\s*:\s*[\'"]([^"\']+)[\'"]', colors_match.group(1))
            for name, value in pairs:
                tokens.colors[name] = value

        # Look for spacing
        spacing_match = re.search(r'spacing\s*[=:]\s*\{([^}]+)\}', content, re.DOTALL)
        if spacing_match:
            pairs = re.findall(r'(\w+)\s*:\s*(\d+)', spacing_match.group(1))
            for name, value in pairs:
                tokens.spacing[name] = int(value)

    elif file_type == "css":
        # Parse CSS variables from :root
        var_pattern = r'--([a-zA-Z0-9-]+)\s*:\s*([^;]+);'
        for match in re.finditer(var_pattern, content):
            name = match.group(1).replace("-", "_")
            value = match.group(2).strip()

            if value.startswith("#") or "rgb" in value:
                tokens.colors[name] = value
            elif "px" in value:
                num_match = re.match(r"(\d+)px", value)
                if num_match:
                    tokens.spacing[name] = int(num_match.group(1))

    return tokens


def compare_tokens(design: DesignTokens, code: DesignTokens) -> List[TokenDrift]:
    """Compare design tokens to code tokens and find drift."""
    drifts = []

    # Compare colors
    for name, design_value in design.colors.items():
        if name in code.colors:
            code_value = code.colors[name]
            if design_value.lower() != code_value.lower():
                drifts.append(TokenDrift(
                    token_type="color",
                    token_name=name,
                    design_value=design_value,
                    code_value=code_value,
                    drift_type="value_mismatch",
                    severity="high"
                ))
        else:
            drifts.append(TokenDrift(
                token_type="color",
                token_name=name,
                design_value=design_value,
                code_value=None,
                drift_type="missing_in_code",
                severity="medium"
            ))

    # Check for colors in code but not in design
    for name, code_value in code.colors.items():
        if name not in design.colors:
            drifts.append(TokenDrift(
                token_type="color",
                token_name=name,
                design_value=None,
                code_value=code_value,
                drift_type="missing_in_design",
                severity="low"
            ))

    # Compare spacing
    for name, design_value in design.spacing.items():
        if name in code.spacing:
            code_value = code.spacing[name]
            if design_value != code_value:
                drifts.append(TokenDrift(
                    token_type="spacing",
                    token_name=name,
                    design_value=design_value,
                    code_value=code_value,
                    drift_type="value_mismatch",
                    severity="medium"
                ))
        else:
            drifts.append(TokenDrift(
                token_type="spacing",
                token_name=name,
                design_value=design_value,
                code_value=None,
                drift_type="missing_in_code",
                severity="low"
            ))

    return drifts


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract design tokens from Pencil file and optionally compare to code.

    Args:
        args: {
            file_path: str - Path to .pen file
            code_tokens_path: str - Path to code tokens file (optional)
            store_as_fact: bool - Store tokens as Duro fact (default: False)
            node_id: str - Extract from specific node (optional)
        }
        tools: {
            pencil_get_variables: func,
            pencil_batch_get: func,
            duro_store_fact: func,
            read_file: func
        }
        context: execution context

    Returns:
        {success, tokens, drift, report}
    """
    file_path = args.get("file_path", "")
    code_tokens_path = args.get("code_tokens_path")
    store_as_fact = args.get("store_as_fact", False)
    node_id = args.get("node_id")

    tokens = DesignTokens(
        source=file_path,
        extracted_at=datetime.now().isoformat()
    )

    # === Step 1: Get Pencil variables ===
    get_variables = tools.get("pencil_get_variables")
    if get_variables:
        try:
            variables_result = get_variables(filePath=file_path)
            if isinstance(variables_result, dict):
                variables = variables_result.get("variables", variables_result)

                tokens.colors = extract_colors_from_variables(variables)
                tokens.spacing = extract_spacing_from_variables(variables)
                tokens.typography = extract_typography_from_variables(variables)
                tokens.radii = extract_radii_from_variables(variables)
        except Exception as e:
            return {"success": False, "error": f"Failed to get variables: {str(e)}"}

    # === Step 2: Extract additional tokens from nodes ===
    if node_id:
        batch_get = tools.get("pencil_batch_get")
        if batch_get:
            try:
                nodes = batch_get(filePath=file_path, nodeIds=[node_id], readDepth=5)
                if nodes:
                    # Extract colors used in nodes
                    node_colors = set()

                    def walk(node):
                        if isinstance(node, dict):
                            if "fill" in node:
                                fill = node["fill"]
                                if isinstance(fill, str) and fill.startswith("#"):
                                    node_colors.add(fill.lower())
                            for child in node.get("children", []):
                                walk(child)

                    for node in nodes if isinstance(nodes, list) else [nodes]:
                        walk(node)

                    # Add discovered colors
                    for i, color in enumerate(node_colors):
                        if color not in tokens.colors.values():
                            tokens.colors[f"discovered_{i}"] = color

            except Exception:
                pass

    # === Step 3: Compare to code tokens if provided ===
    drifts = []
    code_tokens = None

    if code_tokens_path:
        read_file = tools.get("read_file")
        if read_file:
            try:
                content = read_file(code_tokens_path)
                if content:
                    # Determine file type
                    if code_tokens_path.endswith(".ts") or code_tokens_path.endswith(".tsx"):
                        file_type = "ts"
                    elif code_tokens_path.endswith(".js") or code_tokens_path.endswith(".jsx"):
                        file_type = "js"
                    elif code_tokens_path.endswith(".css"):
                        file_type = "css"
                    else:
                        file_type = "ts"

                    code_tokens = parse_code_tokens(content, file_type)
                    drifts = compare_tokens(tokens, code_tokens)

            except Exception as e:
                drifts = []  # Non-fatal

    # === Step 4: Store as fact if requested ===
    fact_id = None
    if store_as_fact:
        store_fact = tools.get("duro_store_fact")
        if store_fact:
            try:
                fact_result = store_fact(
                    claim=f"Design tokens extracted from {file_path}",
                    provenance="tool_output",
                    confidence=0.9,
                    snippet=json.dumps({
                        "colors": len(tokens.colors),
                        "spacing": len(tokens.spacing),
                        "radii": len(tokens.radii)
                    }),
                    tags=["design-tokens", "pencil"]
                )
                if isinstance(fact_result, dict):
                    fact_id = fact_result.get("artifact_id")
            except Exception:
                pass

    # === Step 5: Generate report ===
    lines = [
        "# Design Tokens Report",
        f"",
        f"**Source:** {file_path}",
        f"**Extracted:** {tokens.extracted_at}",
        f"",
    ]

    # Colors
    lines.append(f"## Colors ({len(tokens.colors)})")
    for name, value in list(tokens.colors.items())[:10]:
        lines.append(f"- `{name}`: {value}")
    if len(tokens.colors) > 10:
        lines.append(f"- ... and {len(tokens.colors) - 10} more")
    lines.append("")

    # Spacing
    lines.append(f"## Spacing ({len(tokens.spacing)})")
    for name, value in list(tokens.spacing.items())[:10]:
        lines.append(f"- `{name}`: {value}px")
    lines.append("")

    # Radii
    if tokens.radii:
        lines.append(f"## Border Radii ({len(tokens.radii)})")
        for name, value in tokens.radii.items():
            lines.append(f"- `{name}`: {value}px")
        lines.append("")

    # Typography
    if tokens.typography.get("font_families"):
        lines.append(f"## Typography")
        lines.append(f"- Fonts: {list(tokens.typography['font_families'].values())}")
        lines.append(f"- Sizes: {list(tokens.typography.get('font_sizes', {}).values())}")
        lines.append("")

    # Drift report
    if drifts:
        lines.append(f"## Token Drift ({len(drifts)} issues)")
        for drift in drifts[:10]:
            if drift.drift_type == "value_mismatch":
                lines.append(f"- **{drift.token_name}** ({drift.token_type}): design={drift.design_value}, code={drift.code_value}")
            elif drift.drift_type == "missing_in_code":
                lines.append(f"- **{drift.token_name}** ({drift.token_type}): missing in code (design={drift.design_value})")
            else:
                lines.append(f"- **{drift.token_name}** ({drift.token_type}): only in code ({drift.code_value})")
        lines.append("")
    elif code_tokens_path:
        lines.append("## No Drift Detected")
        lines.append("Design tokens match code tokens.")

    report = "\n".join(lines)

    return {
        "success": True,
        "tokens": {
            "colors": tokens.colors,
            "spacing": tokens.spacing,
            "typography": tokens.typography,
            "radii": tokens.radii,
        },
        "counts": {
            "colors": len(tokens.colors),
            "spacing": len(tokens.spacing),
            "radii": len(tokens.radii),
        },
        "drift": [
            {
                "type": d.token_type,
                "name": d.token_name,
                "design_value": str(d.design_value),
                "code_value": str(d.code_value),
                "drift_type": d.drift_type,
                "severity": d.severity
            }
            for d in drifts
        ],
        "drift_count": len(drifts),
        "has_drift": len(drifts) > 0,
        "fact_id": fact_id,
        "report": report
    }


if __name__ == "__main__":
    print("pencil_design_tokens v1.0.0")
    print("=" * 50)
    print("Extract and manage design tokens from Pencil files")
    print("")
    print("Extracts:")
    print("  - Colors (from variables and nodes)")
    print("  - Spacing (padding, gap, margin)")
    print("  - Typography (fonts, sizes, weights)")
    print("  - Border radii")
    print("")
    print("Detects drift between design and code tokens")
