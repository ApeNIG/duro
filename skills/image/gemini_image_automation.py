"""
Gemini Image Automation Skill - Generate images via Gemini API with project management.

⚠️ NOTE: This uses the PAID Gemini API requiring GEMINI_API_KEY.
For FREE browser-based generation, see: imagefx_automation.py

Capabilities:
- Generate images via Gemini API (Imagen 3)
- Track generation parameters and seeds
- Integrate with image_project_manager
- Batch generation for variants
- Style consistency across project

Use imagefx_automation.py instead if you want:
- Zero cost (free web interface)
- No API key required
- Browser automation via Playwright

Phase 3.2.4
"""

import os
import json
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


SKILL_META = {
    "name": "gemini_image_automation",
    "description": "Generate images via Gemini API with scene-based project management integration",
    "tier": "tested",
    "version": "1.0.0",
    "phase": "3.2",
    "keywords": [
        "gemini", "image", "generation", "automation", "imagen",
        "brand", "assets", "ai", "google"
    ],
    "requires_network": True,
    "timeout_seconds": 600,
    "expected_runtime_seconds": 120,
    "dependencies": ["google-generativeai"],
    "side_effects": ["writes_file", "network_request", "api_call"],
}


@dataclass
class ImageGenerationRequest:
    """Request for image generation."""
    prompt: str
    num_variants: int = 2
    aspect_ratio: str = "1:1"
    negative_prompt: Optional[str] = None
    style: Optional[str] = None
    seed: Optional[int] = None


@dataclass
class ImageGenerationResult:
    """Result from image generation."""
    success: bool
    images: List[Dict[str, Any]] = None
    error: Optional[str] = None


class GeminiImageAutomation:
    """Automates Gemini image generation with project management."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the automation.

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set. Get one at: https://ai.google.dev/")

    def generate_scene_variants(
        self,
        prompt: str,
        num_variants: int = 2,
        aspect_ratio: str = "1:1",
        negative_prompt: Optional[str] = None,
        style: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> ImageGenerationResult:
        """Generate image variants for a scene.

        Args:
            prompt: Image generation prompt
            num_variants: Number of variants to generate
            aspect_ratio: Image aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4)
            negative_prompt: Things to avoid in the image
            style: Style guide (photorealistic, artistic, minimalist, etc.)
            output_dir: Directory to save images

        Returns:
            ImageGenerationResult with generated images
        """
        try:
            import google.generativeai as genai
        except ImportError:
            return ImageGenerationResult(
                success=False,
                error="google-generativeai required (pip install google-generativeai)"
            )

        # Configure API
        genai.configure(api_key=self.api_key)

        # Build full prompt
        full_prompt = prompt
        if style:
            full_prompt = f"{style} style: {prompt}"
        if negative_prompt:
            full_prompt += f" | Avoid: {negative_prompt}"

        images = []
        errors = []

        # Generate variants
        for i in range(num_variants):
            try:
                # Use Gemini Imagen 3
                model = genai.ImageGenerationModel("imagen-3.0-generate-001")

                response = model.generate_images(
                    prompt=full_prompt,
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    safety_filter_level="block_only_high",
                    person_generation="allow_adult"
                )

                # Save image
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    timestamp = int(time.time() * 1000)
                    filename = f"variant_{i+1}_{timestamp}.png"
                    filepath = os.path.join(output_dir, filename)

                    # Save from response
                    if hasattr(response, 'images') and response.images:
                        response.images[0].save(filepath)

                        images.append({
                            "variant_index": i + 1,
                            "local_path": filepath,
                            "prompt": full_prompt,
                            "aspect_ratio": aspect_ratio,
                            "timestamp": timestamp
                        })
                    else:
                        errors.append(f"Variant {i+1}: No image in response")
                else:
                    # Return response data
                    images.append({
                        "variant_index": i + 1,
                        "response": response,
                        "prompt": full_prompt
                    })

            except Exception as e:
                errors.append(f"Variant {i+1}: {str(e)}")

        if not images:
            return ImageGenerationResult(
                success=False,
                error=f"All generations failed: {'; '.join(errors)}"
            )

        return ImageGenerationResult(
            success=True,
            images=images,
            error='; '.join(errors) if errors else None
        )

    def generate_brand_kit(
        self,
        brand_name: str,
        brand_description: str,
        style_guide: Dict[str, Any],
        output_dir: str
    ) -> Dict[str, Any]:
        """Generate a complete brand kit.

        Args:
            brand_name: Name of the brand
            brand_description: Brand description
            style_guide: Style guide dict (colors, style, mood)
            output_dir: Output directory

        Returns:
            Dict with generation results for each asset type
        """
        # Extract style from guide
        colors = style_guide.get("colors", [])
        mood = style_guide.get("mood", "professional")
        style = style_guide.get("style", "modern minimalist")

        color_str = ", ".join(colors) if colors else "brand colors"

        # Define asset types
        assets = {
            "logo": {
                "prompt": f"Clean {style} logo for {brand_name}, {color_str}, simple geometric shapes, professional, vector style, centered on white background",
                "aspect_ratio": "1:1",
                "num_variants": 3
            },
            "icon": {
                "prompt": f"App icon for {brand_name}, {style} design, {color_str}, simple and recognizable, flat design",
                "aspect_ratio": "1:1",
                "num_variants": 2
            },
            "social_banner": {
                "prompt": f"Social media banner for {brand_name}, {style} design, {mood} mood, {brand_description}, {color_str}, professional",
                "aspect_ratio": "16:9",
                "num_variants": 2
            },
            "business_card": {
                "prompt": f"Business card design for {brand_name}, {style}, elegant, {color_str}, minimalist",
                "aspect_ratio": "3:2",
                "num_variants": 2
            }
        }

        results = {}

        for asset_type, config in assets.items():
            asset_dir = os.path.join(output_dir, asset_type)
            result = self.generate_scene_variants(
                prompt=config["prompt"],
                num_variants=config["num_variants"],
                aspect_ratio=config["aspect_ratio"],
                style=style,
                output_dir=asset_dir
            )

            results[asset_type] = {
                "success": result.success,
                "images": result.images if result.success else [],
                "error": result.error
            }

        return results

    def create_workflow_from_template(
        self,
        template_type: str,
        **params
    ) -> Dict[str, Any]:
        """Create a workflow from a template.

        Args:
            template_type: Template type (brand_kit, product_mockup, carousel)
            **params: Template-specific parameters

        Returns:
            Workflow configuration dict
        """
        if template_type == "brand_kit":
            return {
                "name": f"{params.get('brand_name', 'Brand')} Kit",
                "project_type": "brand_kit",
                "scenes": [
                    {
                        "name": "Logo",
                        "scene_type": "logo",
                        "prompt": f"Logo for {params.get('brand_name', 'company')}",
                        "aspect_ratio": "1:1",
                        "num_variants": 3
                    },
                    {
                        "name": "Icon",
                        "scene_type": "icon",
                        "prompt": f"App icon for {params.get('brand_name', 'company')}",
                        "aspect_ratio": "1:1",
                        "num_variants": 2
                    },
                    {
                        "name": "Social Banner",
                        "scene_type": "banner",
                        "prompt": f"Social media banner for {params.get('brand_name', 'company')}",
                        "aspect_ratio": "16:9",
                        "num_variants": 2
                    }
                ]
            }

        elif template_type == "product_mockup":
            return {
                "name": f"{params.get('product_name', 'Product')} Mockups",
                "project_type": "product_mockups",
                "scenes": [
                    {
                        "name": "Hero Shot",
                        "scene_type": "product",
                        "prompt": f"{params.get('product_description', 'product')} on white background, professional photography",
                        "aspect_ratio": "1:1",
                        "num_variants": 3
                    },
                    {
                        "name": "Lifestyle Shot",
                        "scene_type": "product",
                        "prompt": f"{params.get('product_description', 'product')} in use, lifestyle photography",
                        "aspect_ratio": "16:9",
                        "num_variants": 2
                    },
                    {
                        "name": "Detail Shot",
                        "scene_type": "product",
                        "prompt": f"Close-up of {params.get('product_description', 'product')}, highlighting features",
                        "aspect_ratio": "4:3",
                        "num_variants": 2
                    }
                ]
            }

        elif template_type == "carousel":
            num_slides = params.get('num_slides', 5)
            topic = params.get('topic', 'topic')

            return {
                "name": f"{topic} Carousel",
                "project_type": "carousel",
                "scenes": [
                    {
                        "name": f"Slide {i+1}",
                        "scene_type": "slide",
                        "prompt": f"Slide {i+1} for {topic} carousel, minimalist design, text overlay ready",
                        "aspect_ratio": "1:1",
                        "num_variants": 2
                    }
                    for i in range(num_slides)
                ]
            }

        return {"error": f"Unknown template type: {template_type}"}


def run(
    action: str,
    prompt: Optional[str] = None,
    num_variants: int = 2,
    aspect_ratio: str = "1:1",
    negative_prompt: Optional[str] = None,
    style: Optional[str] = None,
    output_dir: Optional[str] = None,
    template_type: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Execute Gemini image automation actions.

    Args:
        action: Action to perform (generate, generate_brand_kit, create_workflow)
        prompt: Image generation prompt
        num_variants: Number of variants to generate
        aspect_ratio: Image aspect ratio
        negative_prompt: Things to avoid
        style: Style guide
        output_dir: Output directory
        template_type: Template type (brand_kit, product_mockup, carousel)
        **kwargs: Additional arguments

    Returns:
        Result dictionary
    """
    try:
        automation = GeminiImageAutomation()

        if action == "generate":
            if not prompt:
                return {"success": False, "error": "prompt required"}

            result = automation.generate_scene_variants(
                prompt=prompt,
                num_variants=num_variants,
                aspect_ratio=aspect_ratio,
                negative_prompt=negative_prompt,
                style=style,
                output_dir=output_dir
            )

            if result.success:
                return {
                    "success": True,
                    "images": result.images,
                    "warning": result.error
                }
            else:
                return {"success": False, "error": result.error}

        elif action == "generate_brand_kit":
            brand_name = kwargs.get("brand_name")
            brand_description = kwargs.get("brand_description")
            style_guide = kwargs.get("style_guide", {})

            if not brand_name or not output_dir:
                return {"success": False, "error": "brand_name and output_dir required"}

            results = automation.generate_brand_kit(
                brand_name=brand_name,
                brand_description=brand_description or f"{brand_name} brand",
                style_guide=style_guide,
                output_dir=output_dir
            )

            return {
                "success": True,
                "results": results
            }

        elif action == "create_workflow":
            if not template_type:
                return {"success": False, "error": "template_type required"}

            workflow = automation.create_workflow_from_template(
                template_type=template_type,
                **kwargs
            )

            return {
                "success": True,
                "workflow": workflow
            }

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Test workflow creation
    result = run(
        action="create_workflow",
        template_type="brand_kit",
        brand_name="Test Company"
    )
    print(json.dumps(result, indent=2))
