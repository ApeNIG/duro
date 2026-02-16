"""
Image Generate Skill - Multi-backend image generation with fallback chain.

Capabilities:
- Multi-backend: Pollinations (free) -> DALL-E -> Stock photos
- Face detection routing to Face Distortion rule
- Prompt enhancement with style modifiers
- Caching and deduplication
- Progress callbacks for batch operations

Phase 3.2.1
"""

import os
import re
import json
import hashlib
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import base64


# ComfyUI client import (optional, graceful fallback)
_COMFYUI_CLIENT_PATH = "C:/Users/sibag/Desktop/BUILD/comfy-api-service/sdk/python"
_comfyui_available = False

try:
    import sys
    if _COMFYUI_CLIENT_PATH not in sys.path:
        sys.path.insert(0, _COMFYUI_CLIENT_PATH)
    from comfyui_client import ComfyUIClient
    from comfyui_client.exceptions import JobFailedError, TimeoutError as JobTimeoutError
    _comfyui_available = True
except ImportError:
    _comfyui_available = False


SKILL_META = {
    "name": "image_generate",
    "description": "Generate images with multi-backend fallback chain",
    "tier": "tested",
    "version": "1.1.0",
    "phase": "3.2",
    "keywords": [
        "image", "generate", "ai", "picture", "photo",
        "pollinations", "comfyui", "dalle", "stock", "illustration"
    ],
    "requires_network": True,
    "timeout_seconds": 600,
    "expected_runtime_seconds": 30,
    "dependencies": [],
    "side_effects": ["writes_file", "network_request"],
}


class Backend(Enum):
    """Available image generation backends."""
    POLLINATIONS = "pollinations"
    COMFYUI = "comfyui"
    DALLE = "dalle"
    STOCK = "stock"


class ImageFormat(Enum):
    """Supported image formats."""
    PNG = "png"
    JPG = "jpg"
    WEBP = "webp"


@dataclass
class GenerationResult:
    """Result from image generation."""
    success: bool
    path: Optional[str] = None
    backend_used: Optional[Backend] = None
    prompt: str = ""
    enhanced_prompt: str = ""
    width: int = 0
    height: int = 0
    file_size_bytes: int = 0
    cached: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.backend_used:
            d["backend_used"] = self.backend_used.value
        return d


@dataclass
class ImageRequest:
    """Request for image generation."""
    prompt: str
    output_path: str
    width: int = 1024
    height: int = 1024
    format: ImageFormat = ImageFormat.PNG
    style: Optional[str] = None
    negative_prompt: Optional[str] = None
    enhance_prompt: bool = True
    generate_thumbnail: bool = False
    thumbnail_size: int = 256
    backends: List[Backend] = field(default_factory=lambda: [
        Backend.POLLINATIONS, Backend.COMFYUI, Backend.DALLE, Backend.STOCK
    ])
    skip_cache: bool = False
    face_override: Optional[bool] = None  # None = auto-detect


DEFAULT_CONFIG = {
    "cache_enabled": True,
    "cache_dir": ".image_cache",
    "cache_expiry_hours": 168,  # 1 week
    "face_detection_keywords": [
        "face", "portrait", "person", "people", "human", "man", "woman",
        "child", "girl", "boy", "headshot", "selfie", "photo of"
    ],
    "face_confidence_threshold": 0.7,
    "default_style": None,
    "pollinations_base_url": "https://image.pollinations.ai/prompt",
    "unsplash_base_url": "https://source.unsplash.com",
    "dalle_api_key_env": "OPENAI_API_KEY",
    "comfyui_base_url": "http://localhost:8000",
    "comfyui_api_key_env": "COMFYUI_API_KEY",
    "comfyui_timeout": 600,
    "comfyui_poll_interval": 2,
    "comfyui_steps": 20,
    "comfyui_cfg_scale": 7.0,
    "comfyui_sampler": "euler_ancestral",
    "max_retries": 2,
    "retry_delay_seconds": 1,
}


# === Face Detection ===

def detect_face_prompt(prompt: str, config: Dict[str, Any]) -> Tuple[bool, float]:
    """
    Detect if prompt likely contains human faces.

    Returns:
        Tuple of (is_face_prompt, confidence)
    """
    prompt_lower = prompt.lower()
    keywords = config.get("face_detection_keywords", DEFAULT_CONFIG["face_detection_keywords"])

    matches = []
    for keyword in keywords:
        if keyword in prompt_lower:
            matches.append(keyword)

    if not matches:
        return False, 0.0

    # Higher confidence for more specific face terms
    high_confidence_terms = ["portrait", "headshot", "selfie", "face"]
    medium_confidence_terms = ["person", "people", "human", "man", "woman", "child"]
    has_high_confidence = any(term in prompt_lower for term in high_confidence_terms)
    has_medium_confidence = any(term in prompt_lower for term in medium_confidence_terms)

    # Start with base confidence based on match count
    confidence = min(0.5 + (len(matches) * 0.2), 1.0)
    if has_high_confidence:
        confidence = min(confidence + 0.25, 1.0)
    elif has_medium_confidence:
        confidence = min(confidence + 0.15, 1.0)

    threshold = config.get("face_confidence_threshold", DEFAULT_CONFIG["face_confidence_threshold"])
    return confidence >= threshold, confidence


# === Prompt Enhancement ===

STYLE_MODIFIERS = {
    "photorealistic": "photorealistic, highly detailed, professional photography, 8k resolution",
    "illustration": "digital illustration, vibrant colors, clean lines, professional artwork",
    "anime": "anime style, detailed, vibrant, studio quality",
    "sketch": "pencil sketch, hand-drawn, detailed linework",
    "watercolor": "watercolor painting, soft colors, artistic, traditional media",
    "3d": "3D render, octane render, highly detailed, professional CGI",
    "cinematic": "cinematic lighting, dramatic, film still, movie quality",
    "minimalist": "minimalist design, clean, simple, modern aesthetic",
}


def enhance_prompt(
    prompt: str,
    style: Optional[str] = None,
    negative_prompt: Optional[str] = None
) -> str:
    """
    Enhance prompt for better image generation results.
    """
    enhanced = prompt.strip()

    # Add style modifier
    if style and style.lower() in STYLE_MODIFIERS:
        enhanced = f"{enhanced}, {STYLE_MODIFIERS[style.lower()]}"

    # Add quality terms if not already present
    quality_terms = ["high quality", "detailed", "professional"]
    has_quality = any(term in enhanced.lower() for term in quality_terms)
    if not has_quality:
        enhanced = f"{enhanced}, high quality, detailed"

    return enhanced


# === Caching ===

def get_cache_key(request: ImageRequest) -> str:
    """Generate cache key from request parameters."""
    key_data = {
        "prompt": request.prompt,
        "width": request.width,
        "height": request.height,
        "style": request.style,
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()[:16]


def get_cached_image(
    request: ImageRequest,
    config: Dict[str, Any]
) -> Optional[str]:
    """Check if image exists in cache."""
    if not config.get("cache_enabled", True) or request.skip_cache:
        return None

    cache_dir = Path(config.get("cache_dir", DEFAULT_CONFIG["cache_dir"]))
    if not cache_dir.exists():
        return None

    cache_key = get_cache_key(request)
    cache_meta_path = cache_dir / f"{cache_key}.json"

    if not cache_meta_path.exists():
        return None

    try:
        with open(cache_meta_path) as f:
            meta = json.load(f)

        # Check expiry
        expiry_hours = config.get("cache_expiry_hours", DEFAULT_CONFIG["cache_expiry_hours"])
        cached_time = meta.get("timestamp", 0)
        if time.time() - cached_time > expiry_hours * 3600:
            return None

        cached_path = meta.get("path")
        if cached_path and Path(cached_path).exists():
            return cached_path
    except Exception:
        pass

    return None


def save_to_cache(
    request: ImageRequest,
    result_path: str,
    config: Dict[str, Any]
) -> None:
    """Save generated image to cache."""
    if not config.get("cache_enabled", True):
        return

    cache_dir = Path(config.get("cache_dir", DEFAULT_CONFIG["cache_dir"]))
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_key = get_cache_key(request)
    cache_meta_path = cache_dir / f"{cache_key}.json"

    meta = {
        "prompt": request.prompt,
        "path": result_path,
        "timestamp": time.time(),
        "width": request.width,
        "height": request.height,
    }

    with open(cache_meta_path, "w") as f:
        json.dump(meta, f)


# === Backend Implementations ===

def generate_pollinations(
    prompt: str,
    width: int,
    height: int,
    output_path: str,
    config: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Generate image using Pollinations API (free, no auth).
    """
    base_url = config.get("pollinations_base_url", DEFAULT_CONFIG["pollinations_base_url"])
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"{base_url}/{encoded_prompt}?width={width}&height={height}&nologo=true"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Duro/1.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            image_data = response.read()

        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(image_data)

        return True, None
    except urllib.error.URLError as e:
        return False, f"Network error: {e.reason}"
    except Exception as e:
        return False, str(e)


def generate_comfyui(
    prompt: str,
    width: int,
    height: int,
    output_path: str,
    config: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Generate image using ComfyUI API service (self-hosted, more control).
    """
    if not _comfyui_available:
        return False, "ComfyUI client SDK not available"

    base_url = config.get("comfyui_base_url", DEFAULT_CONFIG["comfyui_base_url"])
    api_key_env = config.get("comfyui_api_key_env", DEFAULT_CONFIG["comfyui_api_key_env"])
    api_key = os.environ.get(api_key_env) if api_key_env else None

    try:
        client = ComfyUIClient(base_url, api_key=api_key, timeout=30)
        job = client.generate(
            prompt=prompt,
            width=width,
            height=height,
            steps=config.get("comfyui_steps", DEFAULT_CONFIG["comfyui_steps"]),
            cfg_scale=config.get("comfyui_cfg_scale", DEFAULT_CONFIG["comfyui_cfg_scale"]),
            sampler=config.get("comfyui_sampler", DEFAULT_CONFIG["comfyui_sampler"]),
            seed=config.get("comfyui_seed"),
        )
        result = job.wait_for_completion(
            timeout=config.get("comfyui_timeout", DEFAULT_CONFIG["comfyui_timeout"]),
            poll_interval=config.get("comfyui_poll_interval", DEFAULT_CONFIG["comfyui_poll_interval"])
        )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result.download_image(index=0, save_path=output_path)

        return True, None
    except JobFailedError as e:
        return False, f"ComfyUI job failed: {e}"
    except JobTimeoutError as e:
        return False, f"ComfyUI timeout: {e}"
    except Exception as e:
        return False, f"ComfyUI error: {e}"


def generate_dalle(
    prompt: str,
    width: int,
    height: int,
    output_path: str,
    config: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Generate image using DALL-E API (requires API key).
    """
    api_key_env = config.get("dalle_api_key_env", DEFAULT_CONFIG["dalle_api_key_env"])
    api_key = os.environ.get(api_key_env)

    if not api_key:
        return False, f"DALL-E API key not found in {api_key_env}"

    # Map to DALL-E supported sizes
    size = "1024x1024"
    if width >= 1792 or height >= 1792:
        size = "1792x1024" if width > height else "1024x1792"

    try:
        url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = json.dumps({
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }).encode()

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=90) as response:
            result = json.loads(response.read())

        image_b64 = result["data"][0]["b64_json"]
        image_data = base64.b64decode(image_b64)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(image_data)

        return True, None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return False, f"DALL-E API error ({e.code}): {error_body[:200]}"
    except Exception as e:
        return False, str(e)


def generate_stock(
    prompt: str,
    width: int,
    height: int,
    output_path: str,
    config: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Fetch stock photo from Unsplash based on prompt keywords.
    """
    # Extract key terms from prompt
    words = re.findall(r'\b\w+\b', prompt.lower())
    stop_words = {"a", "an", "the", "of", "in", "on", "at", "to", "for", "with", "and", "or"}
    keywords = [w for w in words if w not in stop_words and len(w) > 2][:5]

    if not keywords:
        keywords = ["nature"]  # Fallback

    base_url = config.get("unsplash_base_url", DEFAULT_CONFIG["unsplash_base_url"])
    search_term = ",".join(keywords)
    url = f"{base_url}/{width}x{height}/?{search_term}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Duro/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            image_data = response.read()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(image_data)

        return True, None
    except Exception as e:
        return False, str(e)


BACKEND_HANDLERS = {
    Backend.POLLINATIONS: generate_pollinations,
    Backend.COMFYUI: generate_comfyui,
    Backend.DALLE: generate_dalle,
    Backend.STOCK: generate_stock,
}


# === Main Generation Function ===

def generate_image(
    request: ImageRequest,
    config: Dict[str, Any],
    progress_callback: Optional[callable] = None
) -> GenerationResult:
    """
    Generate an image using the fallback chain.
    """
    # Check cache first
    cached_path = get_cached_image(request, config)
    if cached_path:
        try:
            stat = Path(cached_path).stat()
            return GenerationResult(
                success=True,
                path=cached_path,
                backend_used=None,
                prompt=request.prompt,
                enhanced_prompt=request.prompt,
                file_size_bytes=stat.st_size,
                cached=True,
            )
        except Exception:
            pass  # Cache invalid, continue with generation

    # Check for face content
    is_face, face_confidence = detect_face_prompt(request.prompt, config)
    if request.face_override is not None:
        is_face = request.face_override

    # Enhance prompt
    enhanced_prompt = request.prompt
    if request.enhance_prompt:
        enhanced_prompt = enhance_prompt(
            request.prompt,
            request.style,
            request.negative_prompt
        )

    # Try backends in order
    last_error = None
    for i, backend in enumerate(request.backends):
        if progress_callback:
            progress_callback({
                "stage": "generating",
                "backend": backend.value,
                "attempt": i + 1,
                "total_backends": len(request.backends),
            })

        handler = BACKEND_HANDLERS.get(backend)
        if not handler:
            continue

        max_retries = config.get("max_retries", DEFAULT_CONFIG["max_retries"])
        retry_delay = config.get("retry_delay_seconds", DEFAULT_CONFIG["retry_delay_seconds"])

        for attempt in range(max_retries + 1):
            success, error = handler(
                enhanced_prompt,
                request.width,
                request.height,
                request.output_path,
                config
            )

            if success:
                # Get file info
                try:
                    stat = Path(request.output_path).stat()
                    file_size = stat.st_size
                except Exception:
                    file_size = 0

                # Save to cache
                save_to_cache(request, request.output_path, config)

                result = GenerationResult(
                    success=True,
                    path=request.output_path,
                    backend_used=backend,
                    prompt=request.prompt,
                    enhanced_prompt=enhanced_prompt,
                    width=request.width,
                    height=request.height,
                    file_size_bytes=file_size,
                    cached=False,
                    metadata={
                        "is_face_content": is_face,
                        "face_confidence": face_confidence,
                        "style": request.style,
                    }
                )

                # Generate thumbnail if requested
                if request.generate_thumbnail:
                    thumb_path = _generate_thumbnail(
                        request.output_path,
                        request.thumbnail_size
                    )
                    if thumb_path:
                        result.metadata["thumbnail_path"] = thumb_path

                return result

            last_error = error
            if attempt < max_retries:
                time.sleep(retry_delay)

    return GenerationResult(
        success=False,
        prompt=request.prompt,
        enhanced_prompt=enhanced_prompt,
        error=f"All backends failed. Last error: {last_error}",
    )


def _generate_thumbnail(image_path: str, size: int) -> Optional[str]:
    """Generate a thumbnail (requires PIL, gracefully degrades)."""
    try:
        from PIL import Image

        img = Image.open(image_path)
        img.thumbnail((size, size))

        thumb_path = str(Path(image_path).with_suffix(f".thumb{Path(image_path).suffix}"))
        img.save(thumb_path)
        return thumb_path
    except ImportError:
        return None
    except Exception:
        return None


# === Batch Generation ===

def generate_batch(
    requests: List[ImageRequest],
    config: Dict[str, Any],
    progress_callback: Optional[callable] = None
) -> List[GenerationResult]:
    """
    Generate multiple images with progress reporting.
    """
    results = []
    total = len(requests)

    for i, request in enumerate(requests):
        if progress_callback:
            progress_callback({
                "stage": "batch",
                "current": i + 1,
                "total": total,
                "prompt": request.prompt[:50],
            })

        result = generate_image(request, config, progress_callback)
        results.append(result)

    return results


# === Skill Entry Point ===

def run(
    args: Dict[str, Any],
    tools: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for the image_generate skill.

    Args:
        prompt: Text description of image to generate
        output_path: Where to save the image
        width: Image width (default 1024)
        height: Image height (default 1024)
        style: Style preset (photorealistic, illustration, anime, etc.)
        backends: List of backends to try ["pollinations", "dalle", "stock"]
        skip_cache: Force regeneration even if cached
        batch: List of {prompt, output_path} for batch generation
        config: Override default configuration

    Returns:
        {
            "success": bool,
            "results": List of generation results,
            "summary": str,
            "cached_count": int,
            "generated_count": int,
        }
    """
    config = {**DEFAULT_CONFIG, **args.get("config", {})}
    progress_callback = tools.get("_progress_callback")

    # Handle batch mode
    if "batch" in args:
        requests = []
        for item in args["batch"]:
            req = ImageRequest(
                prompt=item["prompt"],
                output_path=item["output_path"],
                width=item.get("width", 1024),
                height=item.get("height", 1024),
                style=item.get("style", args.get("style")),
                skip_cache=item.get("skip_cache", args.get("skip_cache", False)),
            )
            requests.append(req)

        results = generate_batch(requests, config, progress_callback)

        success_count = sum(1 for r in results if r.success)
        cached_count = sum(1 for r in results if r.cached)

        return {
            "success": success_count > 0,
            "results": [r.to_dict() for r in results],
            "summary": f"Generated {success_count}/{len(results)} images ({cached_count} from cache)",
            "cached_count": cached_count,
            "generated_count": success_count - cached_count,
            "failed_count": len(results) - success_count,
        }

    # Single image mode
    prompt = args.get("prompt", "")
    output_path = args.get("output_path", "")

    if not prompt:
        return {"success": False, "error": "No prompt provided"}
    if not output_path:
        return {"success": False, "error": "No output_path provided"}

    # Parse backends
    backends = [Backend.POLLINATIONS, Backend.COMFYUI, Backend.DALLE, Backend.STOCK]
    if "backends" in args:
        backends = []
        for b in args["backends"]:
            try:
                backends.append(Backend(b.lower()))
            except ValueError:
                pass

    request = ImageRequest(
        prompt=prompt,
        output_path=output_path,
        width=args.get("width", 1024),
        height=args.get("height", 1024),
        style=args.get("style"),
        negative_prompt=args.get("negative_prompt"),
        enhance_prompt=args.get("enhance_prompt", True),
        generate_thumbnail=args.get("generate_thumbnail", False),
        thumbnail_size=args.get("thumbnail_size", 256),
        backends=backends,
        skip_cache=args.get("skip_cache", False),
        face_override=args.get("face_override"),
    )

    result = generate_image(request, config, progress_callback)

    return {
        "success": result.success,
        "result": result.to_dict(),
        "summary": f"Generated image via {result.backend_used.value if result.backend_used else 'cache'}" if result.success else f"Failed: {result.error}",
        "cached": result.cached,
    }


if __name__ == "__main__":
    # Quick test
    test_result = run(
        {
            "prompt": "A serene mountain landscape at sunset",
            "output_path": "test_output.png",
            "backends": ["pollinations"],
        },
        {},
        {}
    )
    print(json.dumps(test_result, indent=2))
