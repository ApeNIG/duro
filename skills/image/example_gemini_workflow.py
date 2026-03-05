"""
Example: Complete Gemini Image Project Workflow

This demonstrates how to use image_project_manager + gemini_image_automation
for end-to-end client image production with Gemini Imagen 3.

Usage:
    python example_gemini_workflow.py
"""

import json
from pathlib import Path


def example_brand_kit_workflow():
    """
    Complete workflow: Client wants a brand asset kit.
    Includes: Logo, Icon, Social Banner, Business Card
    """

    workflow = {
        "project": {
            "name": "TechFlow Brand Kit",
            "client": "TechFlow Inc",
            "deadline": "2026-03-15",
            "project_type": "brand_kit",
            "scenes": [
                {
                    "name": "Logo",
                    "order": 0,
                    "scene_type": "logo",
                    "prompt": "Modern tech company logo for TechFlow, blue gradient, abstract flowing shapes representing data streams, clean geometric design, professional",
                    "aspect_ratio": "1:1",
                    "num_variants": 3,
                    "style": "modern minimalist vector"
                },
                {
                    "name": "App Icon",
                    "order": 1,
                    "scene_type": "icon",
                    "prompt": "Mobile app icon for TechFlow, simplified version of logo, recognizable at small size, blue gradient, rounded square",
                    "aspect_ratio": "1:1",
                    "num_variants": 2,
                    "style": "flat design"
                },
                {
                    "name": "Social Banner",
                    "order": 2,
                    "scene_type": "banner",
                    "prompt": "Social media banner for TechFlow tech company, modern office environment with flowing data visualization, professional atmosphere, blue and white color scheme",
                    "aspect_ratio": "16:9",
                    "num_variants": 3,
                    "style": "corporate photography"
                },
                {
                    "name": "Business Card",
                    "order": 3,
                    "scene_type": "card",
                    "prompt": "Business card design for TechFlow, minimalist layout, blue accent line, clean typography, elegant professional",
                    "aspect_ratio": "3:2",
                    "num_variants": 2,
                    "style": "print design minimalist"
                }
            ]
        },
        "style_guide": {
            "colors": ["#0066FF", "#00A3FF", "#FFFFFF", "#F5F5F5"],
            "style": "modern minimalist",
            "mood": "professional, innovative, trustworthy",
            "avoid": "cluttered, dark, aggressive, overly playful"
        },
        "execution_plan": [
            {
                "phase": "Setup",
                "tools": ["image_project_manager"],
                "actions": [
                    {
                        "action": "Create project",
                        "code": """
# Step 1: Create project
import sys
sys.path.append('.duro/skills/image')
from image_project_manager import run

result = run(
    action="create_project",
    project_name="TechFlow Brand Kit",
    description="Complete brand asset package for TechFlow Inc",
    project_type="brand_kit",
    metadata={
        "client": "TechFlow Inc",
        "deadline": "2026-03-15",
        "budget": "$800"
    }
)

project_id = result['project_id']
print(f"Created project: {project_id}")
"""
                    },
                    {
                        "action": "Add scenes",
                        "code": """
# Step 2: Add all asset scenes
scenes = [
    {
        "name": "Logo",
        "scene_type": "logo",
        "prompt": "Modern tech company logo for TechFlow...",
        "aspect_ratio": "1:1"
    },
    {
        "name": "App Icon",
        "scene_type": "icon",
        "prompt": "Mobile app icon for TechFlow...",
        "aspect_ratio": "1:1"
    },
    {
        "name": "Social Banner",
        "scene_type": "banner",
        "prompt": "Social media banner for TechFlow...",
        "aspect_ratio": "16:9"
    },
    {
        "name": "Business Card",
        "scene_type": "card",
        "prompt": "Business card design for TechFlow...",
        "aspect_ratio": "3:2"
    }
]

for scene_data in scenes:
    result = run(
        action="add_scene",
        project_id=project_id,
        scene_name=scene_data["name"],
        scene_type=scene_data["scene_type"],
        prompt=scene_data["prompt"],
        aspect_ratio=scene_data["aspect_ratio"]
    )
    print(f"Added scene: {scene_data['name']} ({result['scene_id']})")
"""
                    }
                ]
            },
            {
                "phase": "Generation - Logo",
                "tools": ["gemini_image_automation", "image_project_manager"],
                "actions": [
                    {
                        "action": "Generate Logo variants",
                        "code": """
# Step 3: Generate Logo
from gemini_image_automation import run as gemini_run

result = gemini_run(
    action="generate",
    prompt="Modern tech company logo for TechFlow, blue gradient, abstract flowing shapes representing data streams, clean geometric design, professional",
    num_variants=3,
    aspect_ratio="1:1",
    style="modern minimalist vector",
    negative_prompt="cluttered, dark, aggressive, text",
    output_dir=f"~/image_projects/{project_id}/scenes/logo"
)

if result['success']:
    print(f"Generated {len(result['images'])} logo variants")
else:
    print(f"Error: {result['error']}")
"""
                    },
                    {
                        "action": "Record variants in project",
                        "code": """
# Step 4: Record generated variants
for img_data in result['images']:
    variant_result = run(
        action="add_variant",
        project_id=project_id,
        scene_name="Logo",
        generation_params={
            "prompt": img_data['prompt'],
            "aspect_ratio": img_data['aspect_ratio'],
            "timestamp": img_data['timestamp']
        },
        local_path=img_data['local_path']
    )
    print(f"Recorded variant: {variant_result['variant_id']}")
"""
                    }
                ]
            },
            {
                "phase": "Client Review - Logo",
                "actions": [
                    {
                        "action": "Present variants to client",
                        "description": "Show 3 logo variants, client picks favorite"
                    },
                    {
                        "action": "Approve selected variant",
                        "code": """
# Client picked Variant 2
result = run(
    action="approve_variant",
    project_id=project_id,
    scene_name="Logo",
    variant_id="<variant_id_from_add_variant>"
)

print(f"Logo approved: {result['variant_id']}")
"""
                    }
                ]
            },
            {
                "phase": "Repeat for Remaining Assets",
                "description": "Repeat Generation + Review for: App Icon, Social Banner, Business Card"
            },
            {
                "phase": "Export Deliverables",
                "tools": ["image_project_manager"],
                "actions": [
                    {
                        "action": "Check project status",
                        "code": """
result = run(action="status", project_id=project_id)
print(f"Approved assets: {result['status']['approved_scenes']}/4")

if result['status']['ready_to_export']:
    print("✓ Ready to export deliverables")
"""
                    },
                    {
                        "action": "Export individual files",
                        "code": """
# Export each asset separately
result = run(
    action="export",
    project_id=project_id,
    format="individual",
    output_dir="~/deliverables/techflow_brand_kit"
)

if result['success']:
    print(f"Exported {result['count']} files to {result['output_dir']}")
"""
                    },
                    {
                        "action": "Export as grid",
                        "code": """
# Create brand kit overview grid
result = run(
    action="export",
    project_id=project_id,
    format="grid",
    output_path="~/deliverables/techflow_brand_kit_overview.png",
    grid_cols=2,
    spacing=40,
    background="#F5F5F5"
)

print(f"Grid exported: {result['output_path']}")
"""
                    },
                    {
                        "action": "Export as carousel",
                        "code": """
# Create interactive carousel for client presentation
result = run(
    action="export",
    project_id=project_id,
    format="carousel_html",
    output_path="~/deliverables/techflow_carousel.html"
)

print(f"Carousel exported: {result['output_path']}")
"""
                    }
                ]
            },
            {
                "phase": "Revision Example",
                "description": "Client wants to change logo color",
                "actions": [
                    {
                        "action": "Regenerate Logo only",
                        "code": """
# Generate with purple instead of blue
result = gemini_run(
    action="generate",
    prompt="Modern tech company logo for TechFlow, PURPLE gradient instead of blue, abstract flowing shapes, clean geometric design",
    num_variants=2,
    aspect_ratio="1:1",
    style="modern minimalist vector",
    output_dir=f"~/image_projects/{project_id}/scenes/logo"
)

# Add new variants
for img_data in result['images']:
    run(action="add_variant",
        project_id=project_id,
        scene_name="Logo",
        generation_params={...},
        local_path=img_data['local_path'])

# Client picks new favorite, approve it
run(action="approve_variant",
    project_id=project_id,
    scene_name="Logo",
    variant_id="<new_variant_id>")

# Re-export (keeps other assets, replaces logo)
run(action="export",
    project_id=project_id,
    format="grid",
    output_path="~/deliverables/techflow_brand_kit_v2.png")
"""
                    }
                ]
            }
        ]
    }

    return workflow


def example_product_mockup_workflow():
    """Product mockup workflow example."""

    workflow = {
        "project": {
            "name": "SmartWatch Pro Mockups",
            "client": "WearTech Corp",
            "project_type": "product_mockups",
            "scenes": [
                {
                    "name": "Hero Shot",
                    "scene_type": "product",
                    "prompt": "Premium fitness smartwatch in black with silver accents, professional product photography, white background, centered, soft studio lighting",
                    "aspect_ratio": "1:1",
                    "num_variants": 3
                },
                {
                    "name": "Lifestyle Shot",
                    "scene_type": "product",
                    "prompt": "Person wearing black smartwatch while running outdoors, fitness lifestyle, natural daylight, shallow depth of field, active movement",
                    "aspect_ratio": "16:9",
                    "num_variants": 2
                },
                {
                    "name": "Detail Shot",
                    "scene_type": "product",
                    "prompt": "Close-up macro shot of smartwatch screen showing fitness metrics, vibrant OLED display, sharp details, modern UI",
                    "aspect_ratio": "4:3",
                    "num_variants": 2
                }
            ]
        }
    }

    return workflow


def print_workflow_summary():
    """Print workflow summary for reference."""
    workflow = example_brand_kit_workflow()

    print("=" * 70)
    print("GEMINI IMAGE PROJECT WORKFLOW")
    print("=" * 70)
    print()
    print(f"Project: {workflow['project']['name']}")
    print(f"Client: {workflow['project']['client']}")
    print(f"Type: {workflow['project']['project_type']}")
    print(f"Assets: {len(workflow['project']['scenes'])}")
    print()

    print("Style Guide:")
    for key, value in workflow['style_guide'].items():
        if isinstance(value, list):
            print(f"  {key}: {', '.join(value)}")
        else:
            print(f"  {key}: {value}")
    print()

    print("=" * 70)
    print("ASSETS TO GENERATE")
    print("=" * 70)
    print()

    for i, scene in enumerate(workflow['project']['scenes'], 1):
        print(f"{i}. {scene['name']} ({scene['aspect_ratio']})")
        print(f"   Type: {scene['scene_type']}")
        print(f"   Prompt: {scene['prompt'][:60]}...")
        print(f"   Variants: {scene['num_variants']}")
        print(f"   Style: {scene.get('style', 'N/A')}")
        print()

    print("=" * 70)
    print("EXECUTION PHASES")
    print("=" * 70)
    print()

    for phase in workflow['execution_plan']:
        print(f"• {phase['phase']}")
        if 'tools' in phase:
            print(f"  Tools: {', '.join(phase['tools'])}")
        if 'description' in phase:
            print(f"  {phase['description']}")
        print()


def save_workflow_template(output_path: str = "gemini_workflow_template.json"):
    """Save workflow as JSON template."""
    brand_kit = example_brand_kit_workflow()
    product_mockup = example_product_mockup_workflow()

    templates = {
        "brand_kit": brand_kit,
        "product_mockup": product_mockup
    }

    output = Path(output_path)
    with open(output, 'w') as f:
        json.dump(templates, f, indent=2)

    print(f"Workflow templates saved to: {output}")
    return str(output)


if __name__ == "__main__":
    # Print summary
    print_workflow_summary()

    # Save templates
    print()
    save_workflow_template()

    print()
    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print()
    print("1. Set GEMINI_API_KEY environment variable")
    print("2. Install dependencies: pip install google-generativeai pillow")
    print("3. Run the workflow:")
    print()
    print("   from image_project_manager import run")
    print("   from gemini_image_automation import run as gemini_run")
    print()
    print("   # Follow the code examples in execution_plan above")
    print()
    print("See GEMINI_INTEGRATION.md for complete documentation.")
