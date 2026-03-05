"""
ImageFX Automation - Browser-based image generation via Playwright MCP

This mirrors the Flow workflow but for Gemini ImageFX (free web interface).
No API key required - uses browser automation to generate images.

URL: https://aitestkitchen.withgoogle.com/tools/image-fx

Workflow:
1. Navigate to ImageFX
2. Setup network monitoring to capture generation metadata
3. Enter prompt and generate images
4. Extract image URLs and metadata from network requests
5. Download generated images
6. Record variants in project

Phase 3.2.5
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import json


SKILL_META = {
    "name": "imagefx_automation",
    "description": "Browser-based image generation via ImageFX with Playwright automation",
    "tier": "tested",
    "version": "1.0.0",
    "phase": "3.2",
    "keywords": [
        "imagefx", "image", "generation", "automation", "browser",
        "playwright", "gemini", "free"
    ],
    "requires_network": True,
    "timeout_seconds": 300,
    "expected_runtime_seconds": 90,
    "dependencies": ["playwright-mcp"],
    "side_effects": ["browser_interaction", "file_download"],
}


class ImageFXAutomation:
    """Automates ImageFX image generation via browser."""

    def __init__(self):
        """Initialize the automation."""
        self.imagefx_url = "https://aitestkitchen.withgoogle.com/tools/image-fx"
        self.project_dir = Path.home() / "image_projects"

    def get_setup_instructions(self) -> Dict[str, Any]:
        """Get instructions for setting up ImageFX automation.

        Returns:
            Dict with setup steps for Playwright MCP
        """
        return {
            "phase": "Setup",
            "steps": [
                {
                    "step": 1,
                    "action": "Navigate to ImageFX",
                    "tool": "mcp__playwright__browser_navigate",
                    "params": {
                        "url": self.imagefx_url
                    },
                    "description": "Open ImageFX in browser"
                },
                {
                    "step": 2,
                    "action": "Setup network monitoring",
                    "tool": "mcp__playwright__browser_run_code",
                    "code": """
async (page) => {
    await page.evaluate(() => {
        window.capturedRequests = [];
        window.capturedResponses = [];
    });

    // Monitor requests for generation parameters
    page.on('request', request => {
        const url = request.url();
        // ImageFX uses different API endpoints than Flow
        if (url.includes('generateImages') || url.includes('imagen')) {
            page.evaluate((data) => {
                window.capturedRequests.push(data);
            }, {
                url: url,
                method: request.method(),
                postData: request.postData(),
                timestamp: Date.now()
            });
        }
    });

    // Monitor responses for image URLs
    page.on('response', async response => {
        const url = response.url();
        if (url.includes('generateImages') || url.includes('imagen')) {
            try {
                const data = await response.json();
                await page.evaluate((responseData) => {
                    window.capturedResponses.push(responseData);
                }, {
                    url: url,
                    data: data,
                    timestamp: Date.now()
                });
            } catch (e) {
                // Not JSON response, skip
            }
        }
    });

    return "Network monitoring active";
}
""",
                    "description": "Capture generation requests and image URLs"
                }
            ]
        }

    def get_generation_instructions(
        self,
        prompt: str,
        num_variants: int = 4
    ) -> Dict[str, Any]:
        """Get instructions for generating images in ImageFX.

        Args:
            prompt: Image generation prompt
            num_variants: Number of variants (ImageFX typically generates 4)

        Returns:
            Dict with generation steps
        """
        return {
            "phase": "Generation",
            "prompt": prompt,
            "num_variants": num_variants,
            "steps": [
                {
                    "step": 1,
                    "action": "Take snapshot to find prompt input",
                    "tool": "mcp__playwright__browser_snapshot",
                    "description": "Get accessibility snapshot to locate prompt textbox"
                },
                {
                    "step": 2,
                    "action": "Enter prompt",
                    "tool": "mcp__playwright__browser_type",
                    "params": {
                        "ref": "<textbox_ref_from_snapshot>",
                        "text": prompt
                    },
                    "description": f"Type: {prompt[:50]}..."
                },
                {
                    "step": 3,
                    "action": "Click generate button",
                    "tool": "mcp__playwright__browser_click",
                    "params": {
                        "ref": "<button_ref_from_snapshot>"
                    },
                    "description": "Start generation"
                },
                {
                    "step": 4,
                    "action": "Wait for generation",
                    "tool": "mcp__playwright__browser_wait_for",
                    "params": {
                        "time": 45
                    },
                    "description": "ImageFX typically takes 30-60 seconds"
                },
                {
                    "step": 5,
                    "action": "Extract metadata and URLs",
                    "tool": "mcp__playwright__browser_run_code",
                    "code": """
async (page) => {
    const requests = await page.evaluate(() => window.capturedRequests || []);
    const responses = await page.evaluate(() => window.capturedResponses || []);

    // Extract generation parameters from requests
    const params = [];
    for (const req of requests) {
        try {
            const data = JSON.parse(req.postData || '{}');
            params.push({
                prompt: data.prompt || data.textInput,
                timestamp: req.timestamp,
                url: req.url
            });
        } catch (e) {}
    }

    // Extract image URLs from responses
    const imageUrls = [];
    for (const resp of responses) {
        if (resp.data && resp.data.images) {
            for (const img of resp.data.images) {
                if (img.url || img.imageUrl) {
                    imageUrls.push(img.url || img.imageUrl);
                }
            }
        }
    }

    // Alternative: Extract from DOM if not in API responses
    if (imageUrls.length === 0) {
        const domImages = await page.evaluate(() => {
            const imgs = Array.from(document.querySelectorAll('img[src*="googleusercontent"], img[src*="imagen"]'));
            return imgs.map(img => img.src);
        });
        imageUrls.push(...domImages);
    }

    return {
        generation_params: params,
        image_urls: imageUrls,
        count: imageUrls.length
    };
}
""",
                    "description": "Extract generation metadata and image URLs"
                }
            ]
        }

    def get_download_instructions(
        self,
        image_urls: List[str],
        output_dir: str
    ) -> Dict[str, Any]:
        """Get instructions for downloading generated images.

        Args:
            image_urls: List of image URLs from generation
            output_dir: Directory to save images

        Returns:
            Dict with download steps
        """
        return {
            "phase": "Download",
            "image_count": len(image_urls),
            "output_dir": output_dir,
            "steps": [
                {
                    "step": 1,
                    "action": "Download images via browser",
                    "tool": "mcp__playwright__browser_run_code",
                    "code": f"""
async (page) => {{
    const urls = {json.dumps(image_urls)};
    const outputDir = "{output_dir}";
    const fs = require('fs');
    const path = require('path');
    const https = require('https');

    // Ensure output directory exists
    if (!fs.existsSync(outputDir)) {{
        fs.mkdirSync(outputDir, {{ recursive: true }});
    }}

    const downloads = [];

    for (let i = 0; i < urls.length; i++) {{
        const url = urls[i];
        const filename = `variant_${{i+1}}_${{Date.now()}}.png`;
        const filepath = path.join(outputDir, filename);

        // Download using page.goto or fetch
        try {{
            const response = await page.evaluate(async (imageUrl) => {{
                const resp = await fetch(imageUrl);
                const blob = await resp.blob();
                const reader = new FileReader();
                return new Promise((resolve) => {{
                    reader.onloadend = () => resolve(reader.result);
                    reader.readAsDataURL(blob);
                }});
            }}, url);

            // Write base64 to file
            const base64Data = response.replace(/^data:image\\/\\w+;base64,/, '');
            fs.writeFileSync(filepath, base64Data, 'base64');

            downloads.push({{
                variant_index: i + 1,
                url: url,
                local_path: filepath
            }});
        }} catch (e) {{
            downloads.push({{
                variant_index: i + 1,
                url: url,
                error: e.message
            }});
        }}
    }}

    return downloads;
}}
""",
                    "description": "Download all generated images to local storage"
                }
            ],
            "alternative": {
                "method": "Manual right-click save",
                "description": "If automatic download fails, manually right-click each image and save"
            }
        }

    def generate_workflow_instructions(
        self,
        scene_name: str,
        prompt: str,
        output_dir: str,
        num_variants: int = 4
    ) -> Dict[str, Any]:
        """Generate complete workflow instructions for a scene.

        Args:
            scene_name: Name of the scene being generated
            prompt: Image generation prompt
            output_dir: Directory to save images
            num_variants: Number of variants to generate

        Returns:
            Complete workflow instructions
        """
        return {
            "scene": scene_name,
            "prompt": prompt,
            "num_variants": num_variants,
            "workflow": [
                self.get_setup_instructions(),
                self.get_generation_instructions(prompt, num_variants),
                {
                    "phase": "Post-Generation",
                    "note": "After images are generated, extract URLs and download them",
                    "then": "Record variants in image_project_manager"
                }
            ]
        }


def run(
    action: str,
    scene_name: Optional[str] = None,
    prompt: Optional[str] = None,
    output_dir: Optional[str] = None,
    num_variants: int = 4,
    **kwargs
) -> Dict[str, Any]:
    """Execute ImageFX automation actions.

    Args:
        action: Action to perform (setup, generate, download, workflow)
        scene_name: Scene name for workflow
        prompt: Image generation prompt
        output_dir: Output directory for downloads
        num_variants: Number of variants to generate
        **kwargs: Additional arguments

    Returns:
        Result dictionary with instructions
    """
    automation = ImageFXAutomation()

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
            "instructions": automation.get_generation_instructions(prompt, num_variants)
        }

    elif action == "download":
        image_urls = kwargs.get("image_urls", [])
        if not image_urls or not output_dir:
            return {"success": False, "error": "image_urls and output_dir required"}

        return {
            "success": True,
            "instructions": automation.get_download_instructions(image_urls, output_dir)
        }

    elif action == "workflow":
        if not scene_name or not prompt or not output_dir:
            return {"success": False, "error": "scene_name, prompt, and output_dir required"}

        return {
            "success": True,
            "instructions": automation.generate_workflow_instructions(
                scene_name, prompt, output_dir, num_variants
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
        num_variants=4
    )

    print(json.dumps(result, indent=2))
