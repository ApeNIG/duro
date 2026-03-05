"""
Flow Project Automation Skill - End-to-end Flow video generation with project management.

Capabilities:
- Automate Flow video generation via Playwright
- Capture seed values from network traffic
- Download generated videos
- Track projects with video_project_manager
- Full scene-based workflow automation

Phase 3.2.3
"""

import os
import json
import time
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


SKILL_META = {
    "name": "flow_project_automation",
    "description": "End-to-end Flow video generation automation with scene-based project management",
    "tier": "tested",
    "version": "1.0.0",
    "phase": "3.2",
    "keywords": [
        "flow", "automation", "video", "project", "playwright",
        "scene", "workflow", "seed", "download"
    ],
    "requires_network": True,
    "timeout_seconds": 3600,
    "expected_runtime_seconds": 600,
    "dependencies": ["playwright", "video_project_manager"],
    "side_effects": ["writes_file", "network_request", "browser_automation"],
}


FLOW_BASE_URL = "https://labs.google/fx/tools/flow"


@dataclass
class FlowGenerationResult:
    """Result from Flow video generation."""
    success: bool
    variant_ids: List[str] = None
    seeds: List[int] = None
    flow_urls: List[str] = None
    error: Optional[str] = None


class FlowProjectAutomation:
    """Automates Flow video generation with project management."""

    def __init__(self, mcp_available: bool = True):
        """Initialize the automation.

        Args:
            mcp_available: Whether Playwright MCP is available
        """
        self.mcp_available = mcp_available
        self.captured_requests = []

    def generate_scene_variants(
        self,
        project_name: str,
        prompt: str,
        num_variants: int = 2,
        aspect_ratio: str = "16:9"
    ) -> Dict[str, Any]:
        """Generate variants for a scene in Flow.

        This function should be called with Playwright MCP tools.
        It navigates Flow, generates videos, and captures metadata.

        Args:
            project_name: Flow project name (e.g., "Cinematch")
            prompt: Video generation prompt
            num_variants: Number of variants to generate
            aspect_ratio: Video aspect ratio

        Returns:
            Result dictionary with generation details
        """
        if not self.mcp_available:
            return {
                "success": False,
                "error": "Playwright MCP not available"
            }

        # Note: This function returns instructions for the calling context
        # The actual browser automation must be done via MCP tools

        return {
            "success": True,
            "instructions": {
                "steps": [
                    "Navigate to Flow project",
                    "Set up network monitoring for seed capture",
                    "Enter prompt and generate videos",
                    "Wait for completion",
                    "Extract seeds and URLs from network traffic",
                    "Return metadata"
                ],
                "project_url": f"{FLOW_BASE_URL}/project/{{project_id}}",
                "prompt": prompt,
                "num_variants": num_variants,
                "aspect_ratio": aspect_ratio
            }
        }

    def extract_seeds_from_requests(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[int]:
        """Extract seed values from captured network requests.

        Args:
            requests: List of captured HTTP requests

        Returns:
            List of seed values
        """
        seeds = []

        for req in requests:
            if 'batchAsyncGenerateVideoText' not in req.get('url', ''):
                continue

            post_data = req.get('postData')
            if not post_data:
                continue

            try:
                data = json.loads(post_data)
                for request in data.get('requests', []):
                    seed = request.get('seed')
                    if seed:
                        seeds.append(seed)
            except json.JSONDecodeError:
                continue

        return seeds

    def extract_video_urls_from_page(
        self,
        page_content: str
    ) -> List[str]:
        """Extract Flow video URLs from page content.

        Args:
            page_content: HTML or snapshot content

        Returns:
            List of Flow video edit URLs
        """
        urls = []

        # Pattern: /fx/tools/flow/project/{project_id}/edit/{video_id}
        pattern = r'/fx/tools/flow/project/[\w-]+/edit/([\w-]+)'
        matches = re.findall(pattern, page_content)

        for video_id in matches:
            urls.append(f"{FLOW_BASE_URL}/project/{{project_id}}/edit/{video_id}")

        return urls

    def download_video_from_flow(
        self,
        video_url: str,
        output_path: str
    ) -> Tuple[bool, str]:
        """Download a video from Flow.

        Args:
            video_url: Flow video edit URL
            output_path: Local file path to save video

        Returns:
            (success, path_or_error)
        """
        # This requires browser automation to:
        # 1. Navigate to video edit page
        # 2. Find download button/link
        # 3. Trigger download
        # 4. Wait for download to complete
        # 5. Move to output_path

        return False, "Browser automation required - use Playwright MCP"

    def create_workflow_instructions(
        self,
        action: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create step-by-step instructions for browser automation.

        Args:
            action: Workflow action
            **kwargs: Action-specific parameters

        Returns:
            Instructions dictionary
        """
        if action == "generate_scene":
            return {
                "action": "generate_scene",
                "steps": [
                    {
                        "step": 1,
                        "action": "navigate",
                        "url": f"{FLOW_BASE_URL}/project/{kwargs.get('project_id')}",
                        "description": "Navigate to Flow project"
                    },
                    {
                        "step": 2,
                        "action": "setup_monitoring",
                        "description": "Set up network request monitoring to capture seeds",
                        "code": """
page.on('request', request => {
    const url = request.url();
    if (url.includes('batchAsyncGenerateVideoText')) {
        window.capturedRequests = window.capturedRequests || [];
        window.capturedRequests.push({
            url: url,
            method: request.method(),
            postData: request.postData()
        });
    }
});
"""
                    },
                    {
                        "step": 3,
                        "action": "enter_prompt",
                        "selector": "textbox",
                        "value": kwargs.get('prompt'),
                        "description": "Enter generation prompt"
                    },
                    {
                        "step": 4,
                        "action": "click_create",
                        "selector": "button[name='Create']",
                        "description": "Trigger video generation"
                    },
                    {
                        "step": 5,
                        "action": "wait_for_completion",
                        "timeout": 120,
                        "description": "Wait for videos to generate"
                    },
                    {
                        "step": 6,
                        "action": "extract_metadata",
                        "description": "Extract seeds and video URLs",
                        "code": """
const requests = await page.evaluate(() => window.capturedRequests || []);
const seeds = extractSeedsFromRequests(requests);
const urls = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a[href*="/edit/"]'));
    return links.map(l => l.href);
});
"""
                    }
                ],
                "expected_output": {
                    "seeds": "List[int]",
                    "video_urls": "List[str]",
                    "num_variants": kwargs.get('num_variants', 2)
                }
            }

        elif action == "download_video":
            return {
                "action": "download_video",
                "steps": [
                    {
                        "step": 1,
                        "action": "navigate",
                        "url": kwargs.get('video_url'),
                        "description": "Navigate to video edit page"
                    },
                    {
                        "step": 2,
                        "action": "wait_for_video",
                        "description": "Wait for video to load"
                    },
                    {
                        "step": 3,
                        "action": "find_download_link",
                        "description": "Locate download button or video URL"
                    },
                    {
                        "step": 4,
                        "action": "download",
                        "output_path": kwargs.get('output_path'),
                        "description": "Download video file"
                    }
                ],
                "expected_output": {
                    "local_path": kwargs.get('output_path'),
                    "success": "bool"
                }
            }

        return {"error": f"Unknown action: {action}"}


def run(
    action: str,
    project_name: Optional[str] = None,
    project_id: Optional[str] = None,
    flow_project_id: Optional[str] = None,
    scene_name: Optional[str] = None,
    prompt: Optional[str] = None,
    num_variants: int = 2,
    requests: Optional[List[Dict[str, Any]]] = None,
    video_url: Optional[str] = None,
    output_path: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Execute Flow project automation actions.

    Args:
        action: Action to perform (generate_scene, extract_seeds, download_video, full_workflow)
        project_name: Video project name
        project_id: Video project ID (from video_project_manager)
        flow_project_id: Flow project ID (UUID from Flow URL)
        scene_name: Scene name
        prompt: Video generation prompt
        num_variants: Number of variants to generate
        requests: Captured network requests
        video_url: Flow video URL
        output_path: Output file path
        **kwargs: Additional arguments

    Returns:
        Result dictionary
    """
    automation = FlowProjectAutomation()

    try:
        if action == "generate_scene":
            # Return instructions for browser automation
            if not prompt:
                return {"success": False, "error": "prompt required"}

            result = automation.generate_scene_variants(
                project_name=flow_project_id or "default",
                prompt=prompt,
                num_variants=num_variants
            )

            return result

        elif action == "extract_seeds":
            # Extract seeds from captured requests
            if not requests:
                return {"success": False, "error": "requests required"}

            seeds = automation.extract_seeds_from_requests(requests)

            return {
                "success": True,
                "seeds": seeds,
                "count": len(seeds)
            }

        elif action == "extract_urls":
            # Extract video URLs from page content
            page_content = kwargs.get('page_content', '')
            if not page_content:
                return {"success": False, "error": "page_content required"}

            urls = automation.extract_video_urls_from_page(page_content)

            return {
                "success": True,
                "urls": urls,
                "count": len(urls)
            }

        elif action == "workflow_instructions":
            # Generate step-by-step workflow instructions
            workflow_action = kwargs.get('workflow_action')
            if not workflow_action:
                return {"success": False, "error": "workflow_action required"}

            instructions = automation.create_workflow_instructions(
                action=workflow_action,
                **kwargs
            )

            return {
                "success": True,
                "instructions": instructions
            }

        elif action == "full_workflow":
            # Return complete workflow for end-to-end automation
            return {
                "success": True,
                "workflow": {
                    "name": "Flow Scene Generation Workflow",
                    "description": "Complete workflow for generating and tracking video scenes",
                    "phases": [
                        {
                            "phase": 1,
                            "name": "Setup",
                            "steps": [
                                "Create video project with video_project_manager",
                                "Add scene to project with prompt",
                                "Open Flow in browser (Playwright)"
                            ]
                        },
                        {
                            "phase": 2,
                            "name": "Generation",
                            "steps": [
                                "Navigate to Flow project",
                                "Set up network monitoring",
                                "Generate videos with prompt",
                                "Wait for completion",
                                "Capture seeds and URLs"
                            ]
                        },
                        {
                            "phase": 3,
                            "name": "Review",
                            "steps": [
                                "Add variants to scene with seeds/URLs",
                                "Present variants to client",
                                "Client selects preferred variant"
                            ]
                        },
                        {
                            "phase": 4,
                            "name": "Download",
                            "steps": [
                                "Download approved variant",
                                "Save to project directory",
                                "Update variant with local_path"
                            ]
                        },
                        {
                            "phase": 5,
                            "name": "Approval",
                            "steps": [
                                "Approve variant in project",
                                "Mark scene as approved",
                                "Move to next scene or compose"
                            ]
                        },
                        {
                            "phase": 6,
                            "name": "Composition",
                            "steps": [
                                "Wait for all scenes approved",
                                "Compose final video with ffmpeg",
                                "Deliver to client"
                            ]
                        }
                    ],
                    "tools_required": [
                        "video_project_manager",
                        "Playwright MCP",
                        "ffmpeg"
                    ]
                }
            }

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Show workflow example
    result = run(action="full_workflow")
    print(json.dumps(result, indent=2))
