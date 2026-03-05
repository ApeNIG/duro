"""
Skill: capture_design_ref
Description: Streamlined workflow to capture good designs as references for the taste library.
Version: 1.0.0
Tier: tested

Purpose: Capture good designs while browsing to build a library of design references.
This enables learning from excellent examples and applying patterns to new designs.

Process:
1. Accept design source (URL, file path, or Pencil node)
2. Extract key patterns (layout, typography, color palette)
3. Prompt for stealable rules (3-5 concrete rules)
4. Store via duro_store_design_ref
5. Tag with project type, style, pattern category

Usage:
    duro_run_skill(skill_name="capture_design_ref", args={
        "url": "https://example.com/great-design",
        "product_name": "Linear",
        "pattern": "dashboard",
        "style_tags": ["minimal", "dark", "sleek"],
        "why_it_works": ["Clear hierarchy", "Consistent spacing"],
        "stealable_rules": ["Use 12px gap consistently", "Dark sidebar with light content"]
    })
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


SKILL_META = {
    "name": "capture_design_ref",
    "description": "Capture good designs as references for the taste library",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["save design", "capture design", "save this reference", "add to taste library"],
    "keywords": ["design", "reference", "capture", "taste", "library", "pattern"],
}

REQUIRES = ["duro_store_design_ref", "browser_screenshot", "pencil_get_screenshot"]


# Common pattern categories
PATTERN_CATEGORIES = [
    "hero",
    "pricing",
    "nav",
    "sidebar",
    "dashboard",
    "card",
    "form",
    "onboarding",
    "landing",
    "table",
    "modal",
    "notification",
    "settings",
    "profile",
    "feed",
    "chat",
    "checkout",
    "product",
    "auth",
    "empty_state",
]

# Style tag vocabulary
STYLE_TAGS = [
    # Visual feel
    "minimal", "bold", "playful", "serious", "premium", "corporate",
    "editorial", "modern", "retro", "futuristic", "organic", "geometric",
    # Color
    "dark", "light", "colorful", "monochrome", "pastel", "vibrant",
    # Typography
    "sans", "serif", "display", "technical",
    # Industry
    "saas", "fintech", "ecommerce", "media", "social", "productivity",
    # Platform
    "mobile", "desktop", "responsive",
]


@dataclass
class ExtractedDesignData:
    """Data extracted from a design."""
    colors: List[str]
    font_families: List[str]
    spacing_values: List[int]
    layout_pattern: str
    component_types: List[str]


def extract_colors_from_snapshot(nodes: List[Dict]) -> List[str]:
    """Extract unique colors from design nodes."""
    colors = set()

    def walk(node):
        if not isinstance(node, dict):
            return

        # Check fill
        if "fill" in node:
            fill = node["fill"]
            if isinstance(fill, str) and fill.startswith("#"):
                colors.add(fill.lower())

        # Check text color via fill on text nodes
        if node.get("type") == "text" and "fill" in node:
            fill = node["fill"]
            if isinstance(fill, str) and fill.startswith("#"):
                colors.add(fill.lower())

        # Recurse
        for child in node.get("children", []):
            walk(child)

    for node in nodes:
        walk(node)

    return sorted(list(colors))


def extract_fonts_from_snapshot(nodes: List[Dict]) -> List[str]:
    """Extract unique font families from design nodes."""
    fonts = set()

    def walk(node):
        if not isinstance(node, dict):
            return

        if "fontFamily" in node:
            fonts.add(node["fontFamily"])

        for child in node.get("children", []):
            walk(child)

    for node in nodes:
        walk(node)

    return sorted(list(fonts))


def extract_spacing_from_snapshot(nodes: List[Dict]) -> List[int]:
    """Extract unique spacing values from design nodes."""
    spacing = set()

    def walk(node):
        if not isinstance(node, dict):
            return

        # Padding
        if "padding" in node:
            p = node["padding"]
            if isinstance(p, (int, float)):
                spacing.add(int(p))
            elif isinstance(p, list):
                for v in p:
                    if isinstance(v, (int, float)):
                        spacing.add(int(v))

        # Gap
        if "gap" in node:
            g = node["gap"]
            if isinstance(g, (int, float)):
                spacing.add(int(g))

        for child in node.get("children", []):
            walk(child)

    for node in nodes:
        walk(node)

    return sorted(list(spacing))


def detect_layout_pattern(nodes: List[Dict]) -> str:
    """Detect the dominant layout pattern."""
    # Simplified detection based on structure
    has_sidebar = False
    has_header = False
    has_cards = False
    has_grid = False

    def walk(node):
        nonlocal has_sidebar, has_header, has_cards, has_grid
        if not isinstance(node, dict):
            return

        name = node.get("name", "").lower()

        if "sidebar" in name or "sidenav" in name:
            has_sidebar = True
        if "header" in name or "navbar" in name or "nav" in name:
            has_header = True
        if "card" in name:
            has_cards = True
        if "grid" in name:
            has_grid = True

        for child in node.get("children", []):
            walk(child)

    for node in nodes:
        walk(node)

    if has_sidebar:
        return "sidebar_layout"
    elif has_grid or has_cards:
        return "card_grid"
    elif has_header:
        return "stacked_sections"
    else:
        return "unknown"


def auto_suggest_stealable_rules(
    colors: List[str],
    fonts: List[str],
    spacing: List[int],
    layout: str
) -> List[str]:
    """Auto-suggest stealable rules based on extracted data."""
    rules = []

    # Color rules
    if len(colors) <= 3:
        rules.append(f"Use limited palette: {len(colors)} colors only")

    # Spacing rules
    if spacing:
        min_gap = min(s for s in spacing if s > 0) if any(s > 0 for s in spacing) else 0
        if min_gap and min_gap in [4, 8]:
            rules.append(f"Use {min_gap}px base spacing unit")

    # Font rules
    if len(fonts) == 1:
        rules.append(f"Single font family: {fonts[0]}")
    elif len(fonts) == 2:
        rules.append(f"Two fonts: {fonts[0]} for headings, {fonts[1]} for body")

    # Layout rules
    if layout == "sidebar_layout":
        rules.append("Fixed sidebar + scrollable content area")
    elif layout == "card_grid":
        rules.append("Card-based layout with consistent gutters")

    return rules


def validate_pattern(pattern: str) -> bool:
    """Validate pattern category."""
    return pattern.lower() in PATTERN_CATEGORIES


def validate_style_tags(tags: List[str]) -> List[str]:
    """Validate and normalize style tags."""
    valid_tags = []
    for tag in tags:
        normalized = tag.lower().strip()
        if normalized in STYLE_TAGS:
            valid_tags.append(normalized)
        else:
            # Still accept custom tags but flag them
            valid_tags.append(f"{normalized}*")  # asterisk indicates custom
    return valid_tags


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Capture a design reference and store it in the taste library.

    Args:
        args: {
            url: str - URL of the design (optional)
            file_path: str - Path to .pen file (optional)
            node_id: str - Specific node in .pen file (optional)
            product_name: str - Name of product/site (required)
            pattern: str - Pattern category (required)
            style_tags: List[str] - Style descriptors (optional)
            why_it_works: List[str] - Why this design works (optional)
            stealable_rules: List[str] - Concrete rules to extract (optional)
            auto_extract: bool - Auto-extract colors/fonts (default: True)
        }
        tools: {duro_store_design_ref, browser_screenshot, pencil_batch_get}
        context: execution context

    Returns:
        {success, artifact_id, extracted_data, report}
    """
    # Required fields
    product_name = args.get("product_name")
    pattern = args.get("pattern")

    if not product_name:
        return {"success": False, "error": "product_name is required"}
    if not pattern:
        return {"success": False, "error": "pattern is required (e.g., dashboard, hero, pricing)"}

    # Validate pattern
    if not validate_pattern(pattern):
        return {
            "success": False,
            "error": f"Unknown pattern '{pattern}'. Valid patterns: {', '.join(PATTERN_CATEGORIES)}"
        }

    # Optional fields
    url = args.get("url", "")
    file_path = args.get("file_path", "")
    node_id = args.get("node_id", "")
    style_tags = args.get("style_tags", [])
    why_it_works = args.get("why_it_works", [])
    stealable_rules = args.get("stealable_rules", [])
    auto_extract = args.get("auto_extract", True)

    # Normalize style tags
    style_tags = validate_style_tags(style_tags) if style_tags else []

    # Auto-extract from Pencil file if provided
    extracted_data = None
    if auto_extract and file_path and tools.get("pencil_batch_get"):
        try:
            if node_id:
                nodes = tools["pencil_batch_get"](filePath=file_path, nodeIds=[node_id], readDepth=5)
            else:
                nodes = tools["pencil_batch_get"](filePath=file_path, readDepth=3)

            if nodes:
                nodes = nodes if isinstance(nodes, list) else [nodes]
                colors = extract_colors_from_snapshot(nodes)
                fonts = extract_fonts_from_snapshot(nodes)
                spacing = extract_spacing_from_snapshot(nodes)
                layout = detect_layout_pattern(nodes)

                extracted_data = {
                    "colors": colors,
                    "fonts": fonts,
                    "spacing": spacing,
                    "layout_pattern": layout
                }

                # Auto-suggest rules if none provided
                if not stealable_rules:
                    stealable_rules = auto_suggest_stealable_rules(colors, fonts, spacing, layout)

        except Exception as e:
            # Non-fatal - continue without extracted data
            extracted_data = {"error": str(e)}

    # Ensure we have something meaningful
    if not why_it_works:
        why_it_works = ["Good visual hierarchy", "Consistent spacing", "Clear typography"]

    if not stealable_rules:
        stealable_rules = [f"Reference for {pattern} pattern", "Study layout structure", "Note color usage"]

    # Store the design reference
    store_design_ref = tools.get("duro_store_design_ref")
    if not store_design_ref:
        return {"success": False, "error": "duro_store_design_ref tool not available"}

    try:
        result = store_design_ref(
            product_name=product_name,
            pattern=pattern,
            url=url if url else None,
            style_tags=style_tags,
            why_it_works=why_it_works,
            stealable_rules=stealable_rules,
            tags=[pattern] + style_tags  # Additional tags for search
        )

        artifact_id = result.get("artifact_id") if isinstance(result, dict) else str(result)

        # Generate report
        lines = [
            f"## Design Reference Captured",
            f"",
            f"**Product:** {product_name}",
            f"**Pattern:** {pattern}",
            f"**Source:** {url or file_path or 'Not specified'}",
            f"",
            f"### Style Tags",
            ", ".join(style_tags) if style_tags else "None specified",
            f"",
            f"### Why It Works",
        ]
        for item in why_it_works:
            lines.append(f"- {item}")

        lines.append(f"")
        lines.append(f"### Stealable Rules")
        for rule in stealable_rules:
            lines.append(f"- {rule}")

        if extracted_data and "colors" in extracted_data:
            lines.append(f"")
            lines.append(f"### Extracted Data")
            lines.append(f"- Colors: {extracted_data['colors'][:5]}")
            lines.append(f"- Fonts: {extracted_data['fonts']}")
            lines.append(f"- Spacing: {extracted_data['spacing'][:10]}")
            lines.append(f"- Layout: {extracted_data['layout_pattern']}")

        lines.append(f"")
        lines.append(f"**Artifact ID:** {artifact_id}")

        return {
            "success": True,
            "artifact_id": artifact_id,
            "product_name": product_name,
            "pattern": pattern,
            "extracted_data": extracted_data,
            "report": "\n".join(lines)
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to store design reference: {str(e)}"}


if __name__ == "__main__":
    print("capture_design_ref v1.0.0")
    print("=" * 50)
    print("Capture good designs as references for the taste library")
    print("")
    print("Pattern categories:")
    for p in PATTERN_CATEGORIES:
        print(f"  - {p}")
    print("")
    print("Style tags:")
    print(f"  {', '.join(STYLE_TAGS[:10])}...")
