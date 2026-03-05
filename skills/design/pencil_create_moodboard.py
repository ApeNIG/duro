"""
Skill: pencil_create_moodboard
Description: Automated moodboard creation in Pencil.
Version: 1.0.0
Tier: tested

Purpose: Create a structured moodboard frame in Pencil based on keywords,
design references, and style guide. This sets visual direction before
detailed design work.

Process:
1. Accept keywords/adjectives for design direction
2. Query design references matching keywords
3. Load style guide from Pencil
4. Create moodboard frame with:
   - Color palette section
   - Typography samples
   - Reference info cards
   - Style keywords
5. Return node ID for review

Usage:
    duro_run_skill(skill_name="pencil_create_moodboard", args={
        "keywords": ["minimal", "dark", "professional"],
        "project_type": "saas_dashboard",
        "project_name": "Analytics Dashboard"
    })
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


SKILL_META = {
    "name": "pencil_create_moodboard",
    "description": "Automated moodboard creation in Pencil",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["create moodboard", "make moodboard", "design direction", "visual exploration"],
    "keywords": ["design", "moodboard", "pencil", "direction", "inspiration", "palette", "typography"],
}

REQUIRES = [
    "pencil_batch_design",
    "pencil_get_style_guide",
    "pencil_get_style_guide_tags",
    "recall_design_refs",
    "pencil_find_empty_space"
]


# Default colors for sections (will be overridden by style guide)
DEFAULT_SECTION_BG = "#1a1a1a"
DEFAULT_TEXT_COLOR = "#ffffff"
DEFAULT_ACCENT = "#8b5cf6"


@dataclass
class MoodboardSection:
    """A section of the moodboard."""
    title: str
    content: List[Dict]
    width: int
    height: int


def generate_color_palette_section(colors: List[str], width: int = 400) -> str:
    """Generate operations to create color palette section."""
    operations = []

    # Container for palette
    operations.append(f'palette=I(moodboard, {{"type": "frame", "name": "Color Palette", "layout": "vertical", "gap": 16, "padding": 24, "fill": "{DEFAULT_SECTION_BG}", "cornerRadius": 12, "width": {width}}})')

    # Title
    operations.append(f'paletteTitle=I(palette, {{"type": "text", "content": "Color Palette", "fontSize": 18, "fontWeight": "bold", "fill": "{DEFAULT_TEXT_COLOR}"}})')

    # Color swatches container
    operations.append(f'swatches=I(palette, {{"type": "frame", "layout": "horizontal", "gap": 12, "wrap": true}})')

    # Add color swatches (max 8)
    for i, color in enumerate(colors[:8]):
        operations.append(f'swatch{i}=I(swatches, {{"type": "frame", "width": 60, "height": 60, "cornerRadius": 8, "fill": "{color}"}})')

    # Color values list
    operations.append(f'colorList=I(palette, {{"type": "frame", "layout": "vertical", "gap": 4}})')
    for i, color in enumerate(colors[:8]):
        operations.append(f'colorVal{i}=I(colorList, {{"type": "text", "content": "{color}", "fontSize": 12, "fill": "#888888", "fontFamily": "monospace"}})')

    return "\n".join(operations)


def generate_typography_section(fonts: List[Dict], width: int = 400) -> str:
    """Generate operations to create typography section."""
    operations = []

    # Container
    operations.append(f'typography=I(moodboard, {{"type": "frame", "name": "Typography", "layout": "vertical", "gap": 16, "padding": 24, "fill": "{DEFAULT_SECTION_BG}", "cornerRadius": 12, "width": {width}}})')

    # Title
    operations.append(f'typoTitle=I(typography, {{"type": "text", "content": "Typography", "fontSize": 18, "fontWeight": "bold", "fill": "{DEFAULT_TEXT_COLOR}"}})')

    # Font samples
    for i, font in enumerate(fonts[:3]):
        font_name = font.get("name", "Inter")
        operations.append(f'fontSample{i}=I(typography, {{"type": "frame", "layout": "vertical", "gap": 8}})')
        operations.append(f'fontName{i}=I(fontSample{i}, {{"type": "text", "content": "{font_name}", "fontSize": 12, "fill": "#888888"}})')
        operations.append(f'fontDisplay{i}=I(fontSample{i}, {{"type": "text", "content": "The quick brown fox", "fontSize": 24, "fontFamily": "{font_name}", "fill": "{DEFAULT_TEXT_COLOR}"}})')

    return "\n".join(operations)


def generate_keywords_section(keywords: List[str], width: int = 400) -> str:
    """Generate operations to create keywords section."""
    operations = []

    # Container
    operations.append(f'keywords=I(moodboard, {{"type": "frame", "name": "Keywords", "layout": "vertical", "gap": 16, "padding": 24, "fill": "{DEFAULT_SECTION_BG}", "cornerRadius": 12, "width": {width}}})')

    # Title
    operations.append(f'keywordsTitle=I(keywords, {{"type": "text", "content": "Style Keywords", "fontSize": 18, "fontWeight": "bold", "fill": "{DEFAULT_TEXT_COLOR}"}})')

    # Keywords as tags
    operations.append(f'keywordTags=I(keywords, {{"type": "frame", "layout": "horizontal", "gap": 8, "wrap": true}})')

    for i, keyword in enumerate(keywords[:10]):
        operations.append(f'tag{i}=I(keywordTags, {{"type": "frame", "padding": [6, 12], "cornerRadius": 16, "fill": "{DEFAULT_ACCENT}"}})')
        operations.append(f'tagText{i}=I(tag{i}, {{"type": "text", "content": "{keyword}", "fontSize": 12, "fill": "{DEFAULT_TEXT_COLOR}"}})')

    return "\n".join(operations)


def generate_references_section(references: List[Dict], width: int = 400) -> str:
    """Generate operations to create references section."""
    operations = []

    # Container
    operations.append(f'refs=I(moodboard, {{"type": "frame", "name": "References", "layout": "vertical", "gap": 16, "padding": 24, "fill": "{DEFAULT_SECTION_BG}", "cornerRadius": 12, "width": {width}}})')

    # Title
    operations.append(f'refsTitle=I(refs, {{"type": "text", "content": "Design References", "fontSize": 18, "fontWeight": "bold", "fill": "{DEFAULT_TEXT_COLOR}"}})')

    # Reference cards
    for i, ref in enumerate(references[:4]):
        product = ref.get("product_name", "Reference")
        pattern = ref.get("pattern", "")
        rules = ref.get("stealable_rules", [])[:2]

        operations.append(f'refCard{i}=I(refs, {{"type": "frame", "layout": "vertical", "gap": 8, "padding": 16, "cornerRadius": 8, "fill": "#2a2a2a", "width": "fill_container"}})')
        operations.append(f'refName{i}=I(refCard{i}, {{"type": "text", "content": "{product}", "fontSize": 14, "fontWeight": "bold", "fill": "{DEFAULT_TEXT_COLOR}"}})')
        operations.append(f'refPattern{i}=I(refCard{i}, {{"type": "text", "content": "Pattern: {pattern}", "fontSize": 11, "fill": "#888888"}})')

        for j, rule in enumerate(rules):
            # Escape quotes in rules
            safe_rule = rule.replace('"', '\\"')
            operations.append(f'refRule{i}_{j}=I(refCard{i}, {{"type": "text", "content": "• {safe_rule}", "fontSize": 11, "fill": "#aaaaaa"}})')

    return "\n".join(operations)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create an automated moodboard in Pencil.

    Args:
        args: {
            file_path: str - Path to .pen file (optional, uses active editor)
            keywords: List[str] - Style keywords for direction
            project_type: str - Project type (saas_dashboard, landing_page, etc.)
            project_name: str - Name of the project
            width: int - Moodboard width (default: 1200)
            include_references: bool - Include design references (default: True)
        }
        tools: {
            pencil_batch_design: func,
            pencil_get_style_guide: func,
            pencil_get_style_guide_tags: func,
            recall_design_refs: func,
            pencil_find_empty_space: func
        }
        context: execution context

    Returns:
        {success, moodboard_id, report}
    """
    file_path = args.get("file_path", "")
    keywords = args.get("keywords", ["modern", "clean"])
    project_type = args.get("project_type", "saas_dashboard")
    project_name = args.get("project_name", "New Project")
    width = args.get("width", 1200)
    include_references = args.get("include_references", True)

    # Ensure keywords is a list
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",")]

    # === Step 1: Get style guide for colors/fonts ===
    colors = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#1a1a1a", "#ffffff"]
    fonts = [{"name": "Inter"}, {"name": "Plus Jakarta Sans"}]

    get_style_guide = tools.get("pencil_get_style_guide")
    if get_style_guide:
        try:
            style_result = get_style_guide(tags=keywords[:5])
            if isinstance(style_result, dict):
                # Extract colors from style guide
                style_colors = style_result.get("colors", {})
                if style_colors:
                    colors = list(style_colors.values())[:8]

                # Extract fonts
                style_fonts = style_result.get("typography", {})
                if style_fonts:
                    fonts = [{"name": f} for f in style_fonts.get("families", ["Inter"])]
        except Exception:
            pass  # Use defaults

    # === Step 2: Get design references ===
    references = []
    if include_references:
        recall_refs = tools.get("recall_design_refs")
        if recall_refs:
            try:
                refs_result = recall_refs(
                    style_tags=keywords,
                    project_type=project_type,
                    limit=4,
                    include_brief=False
                )
                if isinstance(refs_result, dict):
                    references = refs_result.get("references", [])
            except Exception:
                pass

    # === Step 3: Find empty space for moodboard ===
    x, y = 100, 100  # Default position

    find_space = tools.get("pencil_find_empty_space")
    if find_space:
        try:
            space_result = find_space(
                filePath=file_path,
                width=width,
                height=800,
                padding=50,
                direction="right"
            )
            if isinstance(space_result, dict):
                x = space_result.get("x", 100)
                y = space_result.get("y", 100)
        except Exception:
            pass

    # === Step 4: Build moodboard operations ===
    operations = []

    # Main moodboard container
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    operations.append(f'moodboard=I(document, {{"type": "frame", "name": "Moodboard - {project_name}", "x": {x}, "y": {y}, "width": {width}, "layout": "horizontal", "gap": 24, "padding": 32, "fill": "#0a0a0a", "cornerRadius": 16}})')

    # Header row
    operations.append(f'header=I(moodboard, {{"type": "frame", "layout": "vertical", "gap": 8, "width": "fill_container"}})')
    operations.append(f'title=I(header, {{"type": "text", "content": "Moodboard: {project_name}", "fontSize": 28, "fontWeight": "bold", "fill": "#ffffff"}})')
    operations.append(f'subtitle=I(header, {{"type": "text", "content": "Project Type: {project_type} | Created: {timestamp}", "fontSize": 12, "fill": "#666666"}})')

    # Left column
    operations.append(f'leftCol=I(moodboard, {{"type": "frame", "layout": "vertical", "gap": 24, "width": 380}})')

    # Color palette in left column
    color_ops = generate_color_palette_section(colors, 360)
    # Modify to use leftCol as parent
    color_ops = color_ops.replace("I(moodboard,", "I(leftCol,", 1)
    operations.append(color_ops)

    # Typography in left column
    typo_ops = generate_typography_section(fonts, 360)
    typo_ops = typo_ops.replace("I(moodboard,", "I(leftCol,", 1)
    operations.append(typo_ops)

    # Right column
    operations.append(f'rightCol=I(moodboard, {{"type": "frame", "layout": "vertical", "gap": 24, "width": 380}})')

    # Keywords in right column
    keywords_ops = generate_keywords_section(keywords, 360)
    keywords_ops = keywords_ops.replace("I(moodboard,", "I(rightCol,", 1)
    operations.append(keywords_ops)

    # References in right column (if available)
    if references:
        refs_ops = generate_references_section(references, 360)
        refs_ops = refs_ops.replace("I(moodboard,", "I(rightCol,", 1)
        operations.append(refs_ops)

    # === Step 5: Execute operations ===
    batch_design = tools.get("pencil_batch_design")
    if not batch_design:
        return {"success": False, "error": "pencil_batch_design tool not available"}

    try:
        # Join all operations
        all_ops = "\n".join(operations)

        result = batch_design(
            filePath=file_path,
            operations=all_ops
        )

        # Extract moodboard ID from result
        moodboard_id = None
        if isinstance(result, dict):
            # Result might contain created node IDs
            moodboard_id = result.get("moodboard") or result.get("created", {}).get("moodboard")

        # Generate report
        report_lines = [
            f"# Moodboard Created",
            f"",
            f"**Project:** {project_name}",
            f"**Type:** {project_type}",
            f"**Position:** ({x}, {y})",
            f"**Width:** {width}px",
            f"",
            f"## Contents",
            f"- Color Palette: {len(colors)} colors",
            f"- Typography: {len(fonts)} fonts",
            f"- Keywords: {len(keywords)} tags",
            f"- References: {len(references)} examples",
            f"",
            f"## Keywords Used",
            ", ".join(keywords),
            f"",
        ]

        if references:
            report_lines.extend([
                f"## Referenced Designs",
            ])
            for ref in references:
                report_lines.append(f"- {ref.get('product_name', 'Unknown')} ({ref.get('pattern', '')})")

        return {
            "success": True,
            "moodboard_id": moodboard_id,
            "position": {"x": x, "y": y},
            "width": width,
            "colors": colors,
            "fonts": [f.get("name") for f in fonts],
            "keywords": keywords,
            "references_count": len(references),
            "report": "\n".join(report_lines)
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to create moodboard: {str(e)}"}


if __name__ == "__main__":
    print("pencil_create_moodboard v1.0.0")
    print("=" * 50)
    print("Automated moodboard creation in Pencil")
    print("")
    print("Creates:")
    print("  - Color palette section")
    print("  - Typography samples")
    print("  - Style keywords")
    print("  - Design references (from taste library)")
    print("")
    print("Usage:")
    print('  keywords=["minimal", "dark", "professional"]')
    print('  project_type="saas_dashboard"')
