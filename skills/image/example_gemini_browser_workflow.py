"""
Example: Complete Gemini Browser Workflow

This demonstrates browser-based image generation using Gemini (free)
with Playwright automation.

Usage:
    python example_gemini_browser_workflow.py
"""

import json
from pathlib import Path


def example_browser_workflow():
    """
    Complete workflow: Client brand kit using free Gemini.
    No API key required.
    """

    workflow = {
        "project": {
            "name": "Artisan Bakery Brand Kit",
            "client": "Flour & Fire Bakery",
            "deadline": "2026-03-12",
            "project_type": "brand_kit",
            "cost": "$0 (using free Gemini)",
            "scenes": [
                {
                    "name": "Logo",
                    "order": 0,
                    "scene_type": "logo",
                    "prompt": "Artisan bakery logo, wheat grain symbol, rustic elegant design, warm gold and cream colors, hand-crafted feel, minimalist",
                    "aspect_ratio": "1:1",
                    "style": "Sketch",
                    "variants_needed": 2
                },
                {
                    "name": "Storefront Sign",
                    "order": 1,
                    "scene_type": "signage",
                    "prompt": "Bakery storefront sign design, elegant typography, vintage inspired, warm lighting, inviting atmosphere",
                    "aspect_ratio": "16:9",
                    "style": "Cinematic",
                    "variants_needed": 2
                },
                {
                    "name": "Product Tag",
                    "order": 2,
                    "scene_type": "label",
                    "prompt": "Product price tag design for artisan bread, minimalist label, wheat pattern, natural paper texture",
                    "aspect_ratio": "3:2",
                    "style": "Enamel pin",
                    "variants_needed": 2
                }
            ]
        },
        "execution_plan": [
            {
                "phase": "Setup - Python",
                "tools": ["image_project_manager"],
                "code": """
# Step 1: Create project
import sys
sys.path.append('.duro/skills/image')
from image_project_manager import run

result = run(
    action="create_project",
    project_name="Artisan Bakery Brand Kit",
    description="Complete brand assets for artisan bakery",
    project_type="brand_kit",
    metadata={
        "client": "Flour & Fire Bakery",
        "deadline": "2026-03-12",
        "cost": "$0 (Gemini browser)"
    }
)

project_id = result['project_id']
print(f"Created project: {project_id}")

# Step 2: Add all scenes
scenes = [
    {
        "name": "Logo",
        "scene_type": "logo",
        "prompt": "Artisan bakery logo, wheat grain symbol...",
        "aspect_ratio": "1:1"
    },
    {
        "name": "Storefront Sign",
        "scene_type": "signage",
        "prompt": "Bakery storefront sign design...",
        "aspect_ratio": "16:9"
    },
    {
        "name": "Product Tag",
        "scene_type": "label",
        "prompt": "Product price tag design...",
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
            },
            {
                "phase": "Generation - Logo (Browser)",
                "tools": ["Playwright MCP", "gemini_browser_automation"],
                "steps": [
                    {
                        "step": "1. Navigate to Gemini",
                        "tool": "mcp__playwright__browser_navigate",
                        "params": {
                            "url": "https://gemini.google.com/app"
                        }
                    },
                    {
                        "step": "2. Get UI snapshot",
                        "tool": "mcp__playwright__browser_snapshot",
                        "description": "Find 'Create image' button ref"
                    },
                    {
                        "step": "3. Click 'Create image'",
                        "tool": "mcp__playwright__browser_click",
                        "params": {
                            "ref": "<create_image_ref>",
                            "element": "Create image button"
                        }
                    },
                    {
                        "step": "4. (Optional) Select style",
                        "tool": "mcp__playwright__browser_click",
                        "params": {
                            "ref": "<sketch_style_ref>",
                            "element": "Sketch style"
                        },
                        "note": "Style picker appears after clicking Create image"
                    },
                    {
                        "step": "5. Enter prompt and submit",
                        "tool": "mcp__playwright__browser_type",
                        "params": {
                            "ref": "<textbox_ref>",
                            "text": "Artisan bakery logo, wheat grain symbol, rustic elegant design, warm gold and cream colors, hand-crafted feel, minimalist",
                            "submit": True
                        }
                    },
                    {
                        "step": "6. Wait for generation",
                        "tool": "mcp__playwright__browser_wait_for",
                        "params": {
                            "time": 30
                        },
                        "note": "Gemini takes ~20-40 seconds"
                    },
                    {
                        "step": "7. Take screenshot to verify",
                        "tool": "mcp__playwright__browser_take_screenshot",
                        "params": {
                            "filename": "logo_v1_preview.png"
                        }
                    },
                    {
                        "step": "8. Download full size",
                        "tool": "mcp__playwright__browser_snapshot",
                        "then": "mcp__playwright__browser_click",
                        "params": {
                            "ref": "<download_button_ref>",
                            "element": "Download full size image"
                        },
                        "output": "~/.playwright-mcp/Gemini_Generated_Image_*.png"
                    },
                    {
                        "step": "9. Generate variant 2",
                        "tool": "mcp__playwright__browser_type",
                        "params": {
                            "ref": "<textbox_ref>",
                            "text": "generate another variation with slightly different composition",
                            "submit": True
                        }
                    },
                    {
                        "step": "10. Wait and download variant 2",
                        "description": "Repeat steps 6-8 for second variant"
                    }
                ]
            },
            {
                "phase": "Record Variants - Python",
                "tools": ["image_project_manager"],
                "code": """
# Step 3: Record downloaded Logo variants
image_files = [
    {"local_path": "~/.playwright-mcp/Gemini_Generated_Image_v1.png"},
    {"local_path": "~/.playwright-mcp/Gemini_Generated_Image_v2.png"}
]

for i, img in enumerate(image_files):
    result = run(
        action="add_variant",
        project_id=project_id,
        scene_name="Logo",
        generation_params={
            "prompt": "Artisan bakery logo...",
            "timestamp": 1709461234567 + i,
            "source": "gemini_browser",
            "style": "Sketch",
            "variant_index": i + 1
        },
        local_path=img['local_path']
    )
    print(f"Recorded variant {i+1}: {result['variant_id']}")
"""
            },
            {
                "phase": "Client Review - Logo",
                "description": "Client reviews 2 variants and picks favorite",
                "code": """
# Client picked Variant 1
result = run(
    action="approve_variant",
    project_id=project_id,
    scene_name="Logo",
    variant_id="<variant_1_id>"
)
print(f"Logo approved: {result['variant_id']}")
"""
            },
            {
                "phase": "Repeat for Remaining Scenes",
                "description": "Repeat Browser Generation + Record + Review for Storefront Sign and Product Tag",
                "note": "Each scene takes ~3-5 minutes (30s generation × 2 variants + download + record + review)"
            },
            {
                "phase": "Export Deliverables - Python",
                "tools": ["image_project_manager"],
                "code": """
# Check status
result = run(action="status", project_id=project_id)
print(f"Approved: {result['status']['approved_scenes']}/3")

if result['status']['ready_to_export']:
    # Export individual files
    run(
        action="export",
        project_id=project_id,
        format="individual",
        output_dir="~/deliverables/bakery_brand_kit"
    )

    # Export grid overview
    run(
        action="export",
        project_id=project_id,
        format="grid",
        output_path="~/deliverables/bakery_overview.png",
        grid_cols=3,
        spacing=30
    )

    # Export carousel
    run(
        action="export",
        project_id=project_id,
        format="carousel_html",
        output_path="~/deliverables/bakery_carousel.html"
    )

    print("All deliverables exported")
"""
            }
        ],
        "workflow_summary": {
            "total_scenes": 3,
            "variants_per_scene": 2,
            "total_variants_generated": 6,
            "approved_variants": 3,
            "cost": "$0",
            "estimated_time": "10-15 minutes",
            "time_breakdown": {
                "setup": "2 min",
                "generation_per_scene": "3-5 min x 3 = 9-15 min",
                "export": "1 min"
            }
        },
        "available_styles": [
            "Monochrome", "Color block", "Runway", "Risograph",
            "Technicolor", "Gothic clay", "Dynamite", "Salon",
            "Sketch", "Cinematic", "Steampunk", "Sunrise",
            "Mythic fighter", "Surreal", "Moody", "Enamel pin",
            "Cyborg", "Soft portrait", "Old cartoon", "Oil painting"
        ]
    }

    return workflow


def print_workflow_summary():
    """Print workflow summary."""
    workflow = example_browser_workflow()

    print("=" * 70)
    print("GEMINI BROWSER WORKFLOW")
    print("=" * 70)
    print()
    print(f"Project: {workflow['project']['name']}")
    print(f"Client: {workflow['project']['client']}")
    print(f"Cost: {workflow['project']['cost']}")
    print(f"Scenes: {len(workflow['project']['scenes'])}")
    print()

    print("=" * 70)
    print("SCENES TO GENERATE")
    print("=" * 70)
    print()

    for i, scene in enumerate(workflow['project']['scenes'], 1):
        print(f"{i}. {scene['name']} ({scene['aspect_ratio']})")
        print(f"   Type: {scene['scene_type']}")
        print(f"   Style: {scene.get('style', 'Default')}")
        print(f"   Prompt: {scene['prompt'][:60]}...")
        print(f"   Variants: {scene['variants_needed']}")
        print()

    print("=" * 70)
    print("EXECUTION PHASES")
    print("=" * 70)
    print()

    for phase in workflow['execution_plan']:
        print(f"* {phase['phase']}")
        if 'tools' in phase:
            print(f"  Tools: {', '.join(phase['tools'])}")
        if 'description' in phase:
            print(f"  {phase['description']}")
        print()

    print("=" * 70)
    print("WORKFLOW SUMMARY")
    print("=" * 70)
    print()
    summary = workflow['workflow_summary']
    print(f"Total Scenes: {summary['total_scenes']}")
    print(f"Total Variants: {summary['total_variants_generated']}")
    print(f"Cost: {summary['cost']}")
    print(f"Time: {summary['estimated_time']}")
    print()
    print("Time Breakdown:")
    for phase, time in summary['time_breakdown'].items():
        print(f"  {phase}: {time}")


def save_workflow_template(output_path: str = "gemini_workflow_template.json"):
    """Save workflow as JSON template."""
    workflow = example_browser_workflow()

    output = Path(output_path)
    with open(output, 'w') as f:
        json.dump(workflow, f, indent=2)

    print()
    print(f"Workflow template saved to: {output}")
    return str(output)


if __name__ == "__main__":
    print_workflow_summary()
    save_workflow_template()

    print()
    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print()
    print("1. Navigate to Gemini: https://gemini.google.com/app")
    print("2. Sign in with Google account")
    print("3. Follow the browser automation steps in execution_plan above")
    print()
    print("No API key required - completely free!")
    print()
    print("See GEMINI_BROWSER_INTEGRATION.md for complete documentation.")
