"""
Gemini Browser Automation - Browser-based image generation via Playwright MCP

Uses Gemini web interface (gemini.google.com/app) for free image generation.
No API key required - uses browser automation with Imagen 3.

URL: https://gemini.google.com/app

Workflow:
1. Navigate to Gemini
2. Click "Create image" button
3. Enter prompt and submit
4. Wait for generation (~30 seconds)
5. Download full size image
6. Record variant in project

Phase 3.2.5
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import json


SKILL_META = {
    "name": "gemini_browser_automation",
    "description": "Browser-based image generation via Gemini with Playwright automation",
    "tier": "tested",
    "version": "1.0.0",
    "phase": "3.2",
    "keywords": [
        "gemini", "image", "generation", "automation", "browser",
        "playwright", "imagen", "free"
    ],
    "requires_network": True,
    "timeout_seconds": 120,
    "expected_runtime_seconds": 45,
    "dependencies": ["playwright-mcp"],
    "side_effects": ["browser_interaction", "file_download"],
}


class GeminiBrowserAutomation:
    """Automates Gemini image generation via browser."""

    def __init__(self):
        """Initialize the automation."""
        self.gemini_url = "https://gemini.google.com/app"
        self.project_dir = Path.home() / "image_projects"

    def get_setup_instructions(self) -> Dict[str, Any]:
        """Get instructions for setting up Gemini automation.

        Returns:
            Dict with setup steps for Playwright MCP
        """
        return {
            "phase": "Setup",
            "steps": [
                {
                    "step": 1,
                    "action": "Navigate to Gemini",
                    "tool": "mcp__playwright__browser_navigate",
                    "params": {
                        "url": self.gemini_url
                    },
                    "description": "Open Gemini in browser"
                },
                {
                    "step": 2,
                    "action": "Take snapshot to find UI elements",
                    "tool": "mcp__playwright__browser_snapshot",
                    "description": "Get accessibility snapshot to locate Create image button"
                },
                {
                    "step": 3,
                    "action": "Click Create image button",
                    "tool": "mcp__playwright__browser_click",
                    "params": {
                        "ref": "<create_image_button_ref>",
                        "element": "Create image button"
                    },
                    "description": "Activate image generation mode"
                }
            ]
        }

    def get_generation_instructions(
        self,
        prompt: str,
        style: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get instructions for generating images in Gemini.

        Args:
            prompt: Image generation prompt
            style: Optional style preset (e.g., "Monochrome", "Sketch", "Cinematic")

        Returns:
            Dict with generation steps
        """
        steps = [
            {
                "step": 1,
                "action": "Take snapshot to find prompt input",
                "tool": "mcp__playwright__browser_snapshot",
                "description": "Get accessibility snapshot to locate prompt textbox"
            }
        ]

        # Optional: Select style if specified
        if style:
            steps.append({
                "step": 2,
                "action": f"Select {style} style",
                "tool": "mcp__playwright__browser_click",
                "params": {
                    "ref": f"<{style.lower()}_style_ref>",
                    "element": f"{style} style option"
                },
                "description": f"Apply {style} style preset"
            })

        steps.extend([
            {
                "step": 3 if style else 2,
                "action": "Enter prompt and submit",
                "tool": "mcp__playwright__browser_type",
                "params": {
                    "ref": "<textbox_ref>",
                    "text": prompt,
                    "submit": True
                },
                "description": f"Type: {prompt[:50]}... and press Enter"
            },
            {
                "step": 4 if style else 3,
                "action": "Wait for generation",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {
                    "time": 30
                },
                "description": "Gemini typically takes 20-40 seconds"
            },
            {
                "step": 5 if style else 4,
                "action": "Take screenshot to verify result",
                "tool": "mcp__playwright__browser_take_screenshot",
                "params": {
                    "filename": "gemini_result.png"
                },
                "description": "Capture generated image preview"
            }
        ])

        return {
            "phase": "Generation",
            "prompt": prompt,
            "style": style,
            "steps": steps
        }

    def get_download_instructions(self, output_filename: str) -> Dict[str, Any]:
        """Get instructions for downloading generated image.

        Args:
            output_filename: Desired filename for downloaded image

        Returns:
            Dict with download steps
        """
        return {
            "phase": "Download",
            "output_filename": output_filename,
            "steps": [
                {
                    "step": 1,
                    "action": "Take snapshot to find download button",
                    "tool": "mcp__playwright__browser_snapshot",
                    "description": "Locate 'Download full size image' button"
                },
                {
                    "step": 2,
                    "action": "Click download button",
                    "tool": "mcp__playwright__browser_click",
                    "params": {
                        "ref": "<download_button_ref>",
                        "element": "Download full size image"
                    },
                    "description": "Trigger download"
                },
                {
                    "step": 3,
                    "action": "Wait for download",
                    "tool": "mcp__playwright__browser_wait_for",
                    "params": {
                        "time": 5
                    },
                    "description": "Wait for file to save"
                }
            ],
            "note": "File downloads to .playwright-mcp/ folder as Gemini_Generated_Image_*.png"
        }

    def get_variation_instructions(self, variation_prompt: str) -> Dict[str, Any]:
        """Get instructions for generating variations.

        Args:
            variation_prompt: Prompt for variation (e.g., "give me 3 more variations")

        Returns:
            Dict with variation steps
        """
        return {
            "phase": "Variation",
            "steps": [
                {
                    "step": 1,
                    "action": "Enter variation request",
                    "tool": "mcp__playwright__browser_type",
                    "params": {
                        "ref": "<textbox_ref>",
                        "text": variation_prompt,
                        "submit": True
                    },
                    "description": "Request more variations"
                },
                {
                    "step": 2,
                    "action": "Wait for generation",
                    "tool": "mcp__playwright__browser_wait_for",
                    "params": {
                        "time": 30
                    },
                    "description": "Wait for new variations"
                }
            ]
        }

    def generate_workflow_instructions(
        self,
        scene_name: str,
        prompt: str,
        output_dir: str,
        style: Optional[str] = None,
        num_variants: int = 1
    ) -> Dict[str, Any]:
        """Generate complete workflow instructions for a scene.

        Args:
            scene_name: Name of the scene being generated
            prompt: Image generation prompt
            output_dir: Directory to save images
            style: Optional style preset
            num_variants: Number of variants to generate (requires multiple generations)

        Returns:
            Complete workflow instructions
        """
        workflow = [
            self.get_setup_instructions(),
            self.get_generation_instructions(prompt, style),
            self.get_download_instructions(f"{scene_name}_v1.png")
        ]

        # Add variation steps if more than 1 variant requested
        if num_variants > 1:
            workflow.append({
                "phase": "Additional Variants",
                "note": f"Repeat generation {num_variants - 1} more times with same or modified prompt",
                "variation_prompts": [
                    "generate another variation",
                    "try a different approach",
                    "make it more minimal"
                ]
            })

        return {
            "scene": scene_name,
            "prompt": prompt,
            "style": style,
            "num_variants": num_variants,
            "output_dir": output_dir,
            "workflow": workflow,
            "available_styles": [
                "Monochrome", "Color block", "Runway", "Risograph",
                "Technicolor", "Gothic clay", "Dynamite", "Salon",
                "Sketch", "Cinematic", "Steampunk", "Sunrise",
                "Mythic fighter", "Surreal", "Moody", "Enamel pin",
                "Cyborg", "Soft portrait", "Old cartoon", "Oil painting"
            ]
        }


def run(
    action: str,
    scene_name: Optional[str] = None,
    prompt: Optional[str] = None,
    output_dir: Optional[str] = None,
    style: Optional[str] = None,
    num_variants: int = 1,
    **kwargs
) -> Dict[str, Any]:
    """Execute Gemini automation actions.

    Args:
        action: Action to perform (setup, generate, download, workflow)
        scene_name: Scene name for workflow
        prompt: Image generation prompt
        output_dir: Output directory for downloads
        style: Style preset to apply
        num_variants: Number of variants to generate
        **kwargs: Additional arguments

    Returns:
        Result dictionary with instructions
    """
    automation = GeminiBrowserAutomation()

    if action == "setup":
        return {
            "success": True,
            "instructions": automation.get_setup_instructions()
        }

    elif action == "generate":
        if not prompt:
            return {"success": False, "error": "prompt required"}

        return {
            "success": True,
            "instructions": automation.get_generation_instructions(prompt, style)
        }

    elif action == "download":
        output_filename = kwargs.get("output_filename", "generated_image.png")
        return {
            "success": True,
            "instructions": automation.get_download_instructions(output_filename)
        }

    elif action == "variation":
        variation_prompt = kwargs.get("variation_prompt", "generate another variation")
        return {
            "success": True,
            "instructions": automation.get_variation_instructions(variation_prompt)
        }

    elif action == "workflow":
        if not scene_name or not prompt or not output_dir:
            return {"success": False, "error": "scene_name, prompt, and output_dir required"}

        return {
            "success": True,
            "instructions": automation.generate_workflow_instructions(
                scene_name, prompt, output_dir, style, num_variants
            )
        }

    else:
        return {"success": False, "error": f"Unknown action: {action}"}


if __name__ == "__main__":
    # Example: Get workflow instructions for Logo generation
    result = run(
        action="workflow",
        scene_name="Logo",
        prompt="Modern minimalist coffee shop logo, simple coffee bean icon, warm brown and cream colors",
        output_dir="~/image_projects/test/logo",
        style="Sketch",
        num_variants=2
    )

    print(json.dumps(result, indent=2))
