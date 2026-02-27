"""
Video Generate Skill - Multi-backend AI video generation with fallback chain.

Capabilities:
- Multi-backend: Minimax/Hailuo (free tier) -> Kling AI (excellent) -> Runway (premium)
- Text-to-video and Image-to-video generation
- Camera control instructions
- Cost tracking per generation
- Progress callbacks for long operations

Phase 3.2.2
"""

import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


SKILL_META = {
    "name": "video_generate",
    "description": "Generate AI videos with multi-backend fallback chain (Minimax, Kling)",
    "tier": "tested",
    "version": "1.0.0",
    "phase": "3.2",
    "keywords": [
        "video", "generate", "ai", "clip", "animation",
        "minimax", "hailuo", "kling", "text-to-video", "image-to-video"
    ],
    "requires_network": True,
    "timeout_seconds": 600,
    "expected_runtime_seconds": 120,
    "dependencies": [],
    "side_effects": ["writes_file", "network_request"],
}


class VideoBackend(Enum):
    """Available video generation backends."""
    MINIMAX = "minimax"     # Hailuo - free tier, good quality, ~$0.27/6s
    KLING = "kling"         # Kling AI - excellent quality, ~$0.30/5s
    RUNWAY = "runway"       # Runway Gen-3 - premium, ~$0.50+/5s


# Cost per second of video in USD
BACKEND_COSTS_PER_SECOND = {
    VideoBackend.MINIMAX: 0.045,  # ~$0.27 for 6s
    VideoBackend.KLING: 0.06,     # ~$0.30 for 5s
    VideoBackend.RUNWAY: 0.10,    # ~$0.50 for 5s
}


class VideoMode(Enum):
    """Video generation modes."""
    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_TO_VIDEO = "image_to_video"


@dataclass
class VideoResult:
    """Result from video generation."""
    success: bool
    path: Optional[str] = None
    backend_used: Optional[VideoBackend] = None
    prompt: str = ""
    duration_seconds: float = 0
    width: int = 0
    height: int = 0
    file_size_bytes: int = 0
    estimated_cost: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.backend_used:
            d["backend_used"] = self.backend_used.value
        return d


@dataclass
class VideoRequest:
    """Request for video generation."""
    prompt: str
    output_path: str
    mode: VideoMode = VideoMode.TEXT_TO_VIDEO
    image_path: Optional[str] = None  # For image-to-video
    duration: int = 5  # seconds
    width: int = 1280
    height: int = 720
    camera_control: Optional[str] = None  # e.g., "Pan left", "Zoom in"
    backends: List[VideoBackend] = field(default_factory=lambda: [
        VideoBackend.MINIMAX, VideoBackend.KLING
    ])


DEFAULT_CONFIG = {
    # Minimax/Hailuo settings
    "minimax_api_key_env": "MINIMAX_API_KEY",
    "minimax_base_url": "https://api.minimax.io/v1/video_generation",
    "minimax_model": "hailuo-2.3",
    "minimax_timeout": 600,
    "minimax_poll_interval": 5,
    # Kling settings
    "kling_api_key_env": "KLING_API_KEY",
    "kling_base_url": "https://api.klingai.com/v1",
    "kling_model": "kling-v1.6",
    "kling_timeout": 600,
    "kling_poll_interval": 5,
    # General settings
    "max_retries": 2,
    "retry_delay_seconds": 2,
}


# === Camera Control Helpers ===

CAMERA_CONTROLS = {
    "pan_left": "[Pan left]",
    "pan_right": "[Pan right]",
    "zoom_in": "[Zoom in]",
    "zoom_out": "[Zoom out]",
    "tilt_up": "[Tilt up]",
    "tilt_down": "[Tilt down]",
    "truck_left": "[Truck left]",
    "truck_right": "[Truck right]",
    "push_in": "[Push in]",
    "pull_out": "[Pull out]",
    "static": "[Static shot]",
    "tracking": "[Tracking shot]",
}


def add_camera_control(prompt: str, control: Optional[str]) -> str:
    """Add camera control instruction to prompt."""
    if not control:
        return prompt

    control_lower = control.lower().replace(" ", "_")
    if control_lower in CAMERA_CONTROLS:
        return f"{CAMERA_CONTROLS[control_lower]} {prompt}"
    elif control.startswith("["):
        return f"{control} {prompt}"
    else:
        return f"[{control}] {prompt}"


# === Backend Implementations ===

def generate_minimax(
    request: VideoRequest,
    config: Dict[str, Any]
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Generate video using Minimax/Hailuo API.
    Returns: (success, output_path or None, error or None)
    """
    api_key_env = config.get("minimax_api_key_env", DEFAULT_CONFIG["minimax_api_key_env"])
    api_key = os.environ.get(api_key_env)

    if not api_key:
        return False, None, f"Minimax API key not found in {api_key_env}"

    base_url = config.get("minimax_base_url", DEFAULT_CONFIG["minimax_base_url"])
    model = config.get("minimax_model", DEFAULT_CONFIG["minimax_model"])
    timeout = config.get("minimax_timeout", DEFAULT_CONFIG["minimax_timeout"])
    poll_interval = config.get("minimax_poll_interval", DEFAULT_CONFIG["minimax_poll_interval"])

    # Add camera control to prompt
    prompt = add_camera_control(request.prompt, request.camera_control)

    try:
        # Step 1: Create generation task
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "prompt": prompt,
        }

        # Set mode based on request
        if request.mode == VideoMode.IMAGE_TO_VIDEO and request.image_path:
            # Read and encode image
            with open(request.image_path, "rb") as f:
                import base64
                image_data = base64.b64encode(f.read()).decode()
            payload["first_frame_image"] = f"data:image/png;base64,{image_data}"

        data = json.dumps(payload).encode()
        req = urllib.request.Request(base_url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read())

        task_id = result.get("task_id")
        if not task_id:
            return False, None, f"No task_id in Minimax response: {result}"

        # Step 2: Poll for completion
        status_url = f"{base_url}/{task_id}"
        start_time = time.time()

        while time.time() - start_time < timeout:
            time.sleep(poll_interval)

            status_req = urllib.request.Request(status_url, headers=headers, method="GET")
            with urllib.request.urlopen(status_req, timeout=30) as status_response:
                status_result = json.loads(status_response.read())

            status = status_result.get("status", "").lower()

            if status == "success" or status == "completed":
                video_url = status_result.get("file_id") or status_result.get("video_url")
                if not video_url:
                    # Try to find video in result
                    if "result" in status_result:
                        video_url = status_result["result"].get("video_url")

                if video_url:
                    # Download video
                    vid_req = urllib.request.Request(video_url, headers={"User-Agent": "Duro/1.0"})
                    with urllib.request.urlopen(vid_req, timeout=120) as vid_response:
                        video_data = vid_response.read()

                    Path(request.output_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(request.output_path, "wb") as f:
                        f.write(video_data)

                    return True, request.output_path, None
                else:
                    return False, None, f"No video URL in completed response: {status_result}"

            elif status == "failed" or status == "error":
                error_msg = status_result.get("error", {}).get("message", "Unknown error")
                return False, None, f"Minimax generation failed: {error_msg}"

        return False, None, f"Minimax timeout after {timeout}s"

    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return False, None, f"Minimax API error ({e.code}): {error_body[:200]}"
    except Exception as e:
        return False, None, f"Minimax error: {e}"


def generate_kling(
    request: VideoRequest,
    config: Dict[str, Any]
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Generate video using Kling AI API.
    Returns: (success, output_path or None, error or None)
    """
    api_key_env = config.get("kling_api_key_env", DEFAULT_CONFIG["kling_api_key_env"])
    api_key = os.environ.get(api_key_env)

    if not api_key:
        return False, None, f"Kling API key not found in {api_key_env}"

    base_url = config.get("kling_base_url", DEFAULT_CONFIG["kling_base_url"])
    model = config.get("kling_model", DEFAULT_CONFIG["kling_model"])
    timeout = config.get("kling_timeout", DEFAULT_CONFIG["kling_timeout"])
    poll_interval = config.get("kling_poll_interval", DEFAULT_CONFIG["kling_poll_interval"])

    # Add camera control to prompt
    prompt = add_camera_control(request.prompt, request.camera_control)

    try:
        # Step 1: Create generation task
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        endpoint = f"{base_url}/videos/text2video"
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": str(request.duration),
            "aspect_ratio": f"{request.width}:{request.height}",
        }

        # Image-to-video mode
        if request.mode == VideoMode.IMAGE_TO_VIDEO and request.image_path:
            endpoint = f"{base_url}/videos/image2video"
            with open(request.image_path, "rb") as f:
                import base64
                image_data = base64.b64encode(f.read()).decode()
            payload["image"] = image_data

        data = json.dumps(payload).encode()
        req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read())

        task_id = result.get("data", {}).get("task_id") or result.get("task_id")
        if not task_id:
            return False, None, f"No task_id in Kling response: {result}"

        # Step 2: Poll for completion
        status_url = f"{base_url}/videos/{task_id}"
        start_time = time.time()

        while time.time() - start_time < timeout:
            time.sleep(poll_interval)

            status_req = urllib.request.Request(status_url, headers=headers, method="GET")
            with urllib.request.urlopen(status_req, timeout=30) as status_response:
                status_result = json.loads(status_response.read())

            status = status_result.get("data", {}).get("status", "").lower()

            if status == "completed" or status == "succeed":
                video_url = status_result.get("data", {}).get("video_url")
                if not video_url:
                    videos = status_result.get("data", {}).get("videos", [])
                    if videos:
                        video_url = videos[0].get("url")

                if video_url:
                    # Download video
                    vid_req = urllib.request.Request(video_url, headers={"User-Agent": "Duro/1.0"})
                    with urllib.request.urlopen(vid_req, timeout=120) as vid_response:
                        video_data = vid_response.read()

                    Path(request.output_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(request.output_path, "wb") as f:
                        f.write(video_data)

                    return True, request.output_path, None
                else:
                    return False, None, f"No video URL in Kling response: {status_result}"

            elif status == "failed":
                error_msg = status_result.get("data", {}).get("error_message", "Unknown error")
                return False, None, f"Kling generation failed: {error_msg}"

        return False, None, f"Kling timeout after {timeout}s"

    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return False, None, f"Kling API error ({e.code}): {error_body[:200]}"
    except Exception as e:
        return False, None, f"Kling error: {e}"


BACKEND_HANDLERS = {
    VideoBackend.MINIMAX: generate_minimax,
    VideoBackend.KLING: generate_kling,
}


# === Main Generation Function ===

def generate_video(
    request: VideoRequest,
    config: Dict[str, Any],
    progress_callback: Optional[callable] = None
) -> VideoResult:
    """
    Generate a video using the fallback chain.
    """
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
            success, output_path, error = handler(request, config)

            if success and output_path:
                # Get file info
                try:
                    stat = Path(output_path).stat()
                    file_size = stat.st_size
                except Exception:
                    file_size = 0

                # Calculate estimated cost
                cost_per_second = BACKEND_COSTS_PER_SECOND.get(backend, 0)
                estimated_cost = cost_per_second * request.duration

                return VideoResult(
                    success=True,
                    path=output_path,
                    backend_used=backend,
                    prompt=request.prompt,
                    duration_seconds=request.duration,
                    width=request.width,
                    height=request.height,
                    file_size_bytes=file_size,
                    estimated_cost=estimated_cost,
                    metadata={
                        "mode": request.mode.value,
                        "camera_control": request.camera_control,
                    }
                )

            last_error = error
            if attempt < max_retries:
                time.sleep(retry_delay)

    return VideoResult(
        success=False,
        prompt=request.prompt,
        error=f"All backends failed. Last error: {last_error}",
    )


# === Skill Entry Point ===

def run(
    args: Dict[str, Any],
    tools: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for the video_generate skill.

    Args:
        prompt: Text description of video to generate
        output_path: Where to save the video
        mode: "text_to_video" or "image_to_video"
        image_path: Source image for image-to-video mode
        duration: Video duration in seconds (default 5)
        width: Video width (default 1280)
        height: Video height (default 720)
        camera_control: Camera movement instruction
        backends: List of backends to try ["minimax", "kling"]
        config: Override default configuration

    Returns:
        {
            "success": bool,
            "result": VideoResult dict,
            "summary": str,
            "estimated_cost": float,
        }
    """
    config = {**DEFAULT_CONFIG, **args.get("config", {})}
    progress_callback = tools.get("_progress_callback")

    prompt = args.get("prompt", "")
    output_path = args.get("output_path", "")

    if not prompt:
        return {"success": False, "error": "No prompt provided"}
    if not output_path:
        return {"success": False, "error": "No output_path provided"}

    # Parse mode
    mode_str = args.get("mode", "text_to_video")
    try:
        mode = VideoMode(mode_str)
    except ValueError:
        mode = VideoMode.TEXT_TO_VIDEO

    # Parse backends
    backends = [VideoBackend.MINIMAX, VideoBackend.KLING]
    if "backends" in args:
        backends = []
        for b in args["backends"]:
            try:
                backends.append(VideoBackend(b.lower()))
            except ValueError:
                pass

    request = VideoRequest(
        prompt=prompt,
        output_path=output_path,
        mode=mode,
        image_path=args.get("image_path"),
        duration=args.get("duration", 5),
        width=args.get("width", 1280),
        height=args.get("height", 720),
        camera_control=args.get("camera_control"),
        backends=backends,
    )

    result = generate_video(request, config, progress_callback)

    return {
        "success": result.success,
        "result": result.to_dict(),
        "summary": f"Generated {result.duration_seconds}s video via {result.backend_used.value}" if result.success else f"Failed: {result.error}",
        "estimated_cost": result.estimated_cost,
    }


def estimate_cost(
    duration_seconds: int,
    backend: str = "minimax",
    count: int = 1
) -> Dict[str, Any]:
    """
    Estimate cost for video generation.

    Returns:
        {
            "backend": str,
            "duration_seconds": int,
            "count": int,
            "cost_per_video": float,
            "total_cost": float,
        }
    """
    try:
        backend_enum = VideoBackend(backend.lower())
    except ValueError:
        backend_enum = VideoBackend.MINIMAX

    cost_per_second = BACKEND_COSTS_PER_SECOND.get(backend_enum, 0)
    cost_per_video = cost_per_second * duration_seconds
    total_cost = cost_per_video * count

    return {
        "backend": backend_enum.value,
        "duration_seconds": duration_seconds,
        "count": count,
        "cost_per_video": round(cost_per_video, 4),
        "total_cost": round(total_cost, 4),
    }


if __name__ == "__main__":
    # Quick test - estimate costs
    print("Video Generation Cost Estimates:")
    for backend in ["minimax", "kling"]:
        for duration in [5, 10]:
            est = estimate_cost(duration, backend)
            print(f"  {backend} {duration}s: ${est['cost_per_video']:.3f}/video")
