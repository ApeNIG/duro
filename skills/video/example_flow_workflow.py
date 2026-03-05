"""
Example: Complete Flow Video Project Workflow

This demonstrates how to use video_project_manager + Playwright MCP
for end-to-end client video production with Flow.

Usage:
    This is a reference implementation showing the integration.
    Actual execution requires Playwright MCP tools in a Claude Code session.
"""

import json
from pathlib import Path


# Example workflow for a client video project
def example_workflow():
    """
    Complete workflow: Client wants a 15-second product video.
    Breakdown: 3 scenes x 5 seconds each
    """

    workflow = {
        "project": {
            "name": "Acme Product Launch",
            "client": "Acme Corp",
            "deadline": "2026-03-10",
            "total_duration": 15,
            "scenes": [
                {
                    "name": "Hero Shot",
                    "order": 0,
                    "duration": 5,
                    "prompt": "Cinematic hero shot of sleek tech product on pedestal, soft dramatic lighting, camera slowly orbits around product",
                    "num_variants": 3
                },
                {
                    "name": "Feature Showcase",
                    "order": 1,
                    "duration": 5,
                    "prompt": "Close-up of product screen showing UI, smooth camera zoom into display, vibrant colors, modern interface",
                    "num_variants": 3
                },
                {
                    "name": "Lifestyle Context",
                    "order": 2,
                    "duration": 5,
                    "prompt": "Product being used in modern office setting, professional hands interacting, natural daylight, shallow depth of field",
                    "num_variants": 3
                }
            ]
        },
        "execution_plan": [
            {
                "phase": "Setup",
                "tools": ["video_project_manager"],
                "actions": [
                    {
                        "action": "Create project",
                        "code": """
# Step 1: Create project
import sys
sys.path.append('.duro/skills/video')
from video_project_manager import run

result = run(
    action="create_project",
    project_name="Acme Product Launch",
    description="15-second product launch video",
    metadata={
        "client": "Acme Corp",
        "deadline": "2026-03-10",
        "budget": "$500"
    }
)

project_id = result['project_id']
print(f"Created project: {project_id}")
"""
                    },
                    {
                        "action": "Add scenes",
                        "code": """
# Step 2: Add all scenes
scenes = [
    {"name": "Hero Shot", "prompt": "Cinematic hero shot of sleek tech product..."},
    {"name": "Feature Showcase", "prompt": "Close-up of product screen..."},
    {"name": "Lifestyle Context", "prompt": "Product being used in modern office..."}
]

for scene_data in scenes:
    result = run(
        action="add_scene",
        project_id=project_id,
        scene_name=scene_data["name"],
        prompt=scene_data["prompt"],
        aspect_ratio="16:9"
    )
    print(f"Added scene: {result['scene_id']}")
"""
                    }
                ]
            },
            {
                "phase": "Generation - Scene 1",
                "tools": ["Playwright MCP", "video_project_manager"],
                "actions": [
                    {
                        "action": "Navigate to Flow",
                        "mcp_tool": "mcp__playwright__browser_navigate",
                        "params": {
                            "url": "https://labs.google/fx/tools/flow/project/<YOUR_FLOW_PROJECT_ID>"
                        }
                    },
                    {
                        "action": "Setup network monitoring",
                        "mcp_tool": "mcp__playwright__browser_run_code",
                        "code": """
async (page) => {
  await page.evaluate(() => {
    window.capturedRequests = [];
  });

  page.on('request', request => {
    const url = request.url();
    if (url.includes('batchAsyncGenerateVideoText')) {
      page.evaluate((data) => {
        window.capturedRequests.push(data);
      }, {
        url: url,
        method: request.method(),
        postData: request.postData()
      });
    }
  });

  return "Network monitoring active";
}
"""
                    },
                    {
                        "action": "Generate Scene 1",
                        "mcp_tool": "mcp__playwright__browser_type",
                        "steps": [
                            "Click prompt textbox",
                            "Enter: 'Cinematic hero shot of sleek tech product on pedestal, soft dramatic lighting, camera slowly orbits around product'",
                            "Click Create button",
                            "Wait 90 seconds for generation"
                        ]
                    },
                    {
                        "action": "Extract metadata",
                        "mcp_tool": "mcp__playwright__browser_run_code",
                        "code": """
async (page) => {
  const requests = await page.evaluate(() => window.capturedRequests || []);

  // Extract seeds
  const seeds = [];
  for (const req of requests) {
    try {
      const data = JSON.parse(req.postData);
      for (const request of data.requests || []) {
        if (request.seed) seeds.push(request.seed);
      }
    } catch (e) {}
  }

  // Extract video URLs
  const urls = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a[href*="/edit/"]'));
    return links.slice(0, 2).map(l => l.href);
  });

  return { seeds, urls };
}
"""
                    },
                    {
                        "action": "Record variants",
                        "code": """
# Captured from browser: seeds=[5816, 14619], urls=[...]
metadata = {'seeds': [5816, 14619], 'urls': ['url1', 'url2']}

for i, (seed, url) in enumerate(zip(metadata['seeds'], metadata['urls'])):
    result = run(
        action="add_variant",
        project_id=project_id,
        scene_name="Hero Shot",
        seed=seed,
        flow_url=url
    )
    print(f"Added variant {i+1}: {result['variant_id']}")
"""
                    }
                ]
            },
            {
                "phase": "Client Review",
                "actions": [
                    {
                        "action": "Present variants to client",
                        "description": "Show Flow URLs, client picks favorite"
                    },
                    {
                        "action": "Download approved variant",
                        "description": "Use browser to download or direct download if URL available"
                    },
                    {
                        "action": "Approve in project",
                        "code": """
# Client picked Variant 2 (seed 14619)
result = run(
    action="approve_variant",
    project_id=project_id,
    scene_name="Hero Shot",
    variant_id="<variant_id_from_add_variant>",
    local_path="/path/to/downloaded/hero_shot.mp4"
)
"""
                    }
                ]
            },
            {
                "phase": "Repeat for Scene 2 & 3",
                "description": "Repeat Generation + Review phases for remaining scenes"
            },
            {
                "phase": "Composition",
                "tools": ["video_project_manager", "ffmpeg"],
                "actions": [
                    {
                        "action": "Check project status",
                        "code": """
result = run(action="status", project_id=project_id)
print(f"Approved scenes: {result['status']['approved_scenes']}/3")

if result['status']['ready_to_compose']:
    print("✓ Ready to compose final video")
"""
                    },
                    {
                        "action": "Compose final video",
                        "code": """
result = run(
    action="compose",
    project_id=project_id,
    output_path="/path/to/acme_product_launch_final.mp4"
)

if result['success']:
    print(f"✓ Final video: {result['output_path']}")
"""
                    }
                ]
            },
            {
                "phase": "Revision Example",
                "description": "Client wants to change Scene 2",
                "actions": [
                    {
                        "action": "Regenerate Scene 2 only",
                        "steps": [
                            "Navigate to Flow",
                            "Generate with modified prompt",
                            "Capture new seeds/URLs",
                            "Add new variants to existing scene",
                            "Client picks new favorite",
                            "Approve new variant",
                            "Re-compose (reuses Scene 1 & 3, replaces Scene 2)"
                        ]
                    }
                ]
            }
        ]
    }

    return workflow


def print_workflow_summary():
    """Print workflow summary for reference."""
    workflow = example_workflow()

    print("=" * 70)
    print("FLOW VIDEO PROJECT WORKFLOW")
    print("=" * 70)
    print()
    print(f"Project: {workflow['project']['name']}")
    print(f"Scenes: {len(workflow['project']['scenes'])}")
    print(f"Total Duration: {workflow['project']['total_duration']}s")
    print()

    for i, scene in enumerate(workflow['project']['scenes'], 1):
        print(f"{i}. {scene['name']} ({scene['duration']}s)")
        print(f"   Prompt: {scene['prompt'][:60]}...")
        print(f"   Variants: {scene['num_variants']}")
        print()

    print("=" * 70)
    print("EXECUTION PHASES")
    print("=" * 70)
    print()

    for phase in workflow['execution_plan']:
        print(f"• {phase['phase']}")
        if 'tools' in phase:
            print(f"  Tools: {', '.join(phase['tools'])}")
        print()


def save_workflow_template(output_path: str = "flow_workflow_template.json"):
    """Save workflow as JSON template."""
    workflow = example_workflow()

    output = Path(output_path)
    with open(output, 'w') as f:
        json.dump(workflow, f, indent=2)

    print(f"Workflow template saved to: {output}")
    return str(output)


if __name__ == "__main__":
    # Print summary
    print_workflow_summary()

    # Save template
    print()
    save_workflow_template()
