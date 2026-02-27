"""
Production Cost Estimator Skill - Calculate costs before running AI generation jobs.

Capabilities:
- Estimate costs for image generation across backends
- Estimate costs for video generation across backends
- Calculate total production costs for multi-asset projects
- Compare backend costs to find optimal choices
- Budget validation before job execution

Phase 3.2.2
"""

import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


SKILL_META = {
    "name": "production_cost_estimator",
    "description": "Calculate AI generation costs before running jobs",
    "tier": "tested",
    "version": "1.0.1",
    "phase": "3.2",
    "keywords": [
        "cost", "estimate", "budget", "price", "production",
        "image", "video", "calculate", "plan", "compare"
    ],
    "requires_network": False,
    "timeout_seconds": 10,
    "expected_runtime_seconds": 1,
    "dependencies": [],
    "side_effects": [],
    "validated": "2026-02-18",
}


# === Pricing Data (USD) ===

# Image generation costs per image
IMAGE_COSTS = {
    "flux": {
        "name": "Flux Pro (FAL.ai)",
        "cost_per_image": 0.04,
        "quality": "excellent",
        "speed": "fast",
        "notes": "Best for photorealistic, professional quality"
    },
    "flux_dev": {
        "name": "Flux Dev (FAL.ai)",
        "cost_per_image": 0.025,
        "quality": "very_good",
        "speed": "fast",
        "notes": "Good balance of quality and cost"
    },
    "dalle": {
        "name": "DALL-E 3 (OpenAI)",
        "cost_per_image": 0.04,
        "quality": "excellent",
        "speed": "medium",
        "notes": "Best for creative/artistic images"
    },
    "dalle_hd": {
        "name": "DALL-E 3 HD (OpenAI)",
        "cost_per_image": 0.08,
        "quality": "excellent",
        "speed": "medium",
        "notes": "Higher resolution output"
    },
    "pollinations": {
        "name": "Pollinations",
        "cost_per_image": 0.0,
        "quality": "good",
        "speed": "fast",
        "notes": "Free but may have rate limits"
    },
    "comfyui": {
        "name": "ComfyUI (Self-hosted)",
        "cost_per_image": 0.0,
        "quality": "excellent",
        "speed": "varies",
        "notes": "Free when self-hosted, requires GPU"
    },
    "ideogram": {
        "name": "Ideogram 2.0",
        "cost_per_image": 0.02,
        "quality": "excellent",
        "speed": "fast",
        "notes": "Best for text rendering in images"
    },
    "midjourney": {
        "name": "Midjourney",
        "cost_per_image": 0.01,  # ~$30/mo for 3000 images
        "quality": "excellent",
        "speed": "medium",
        "notes": "Best aesthetics, subscription required"
    },
}

# Video generation costs per second
VIDEO_COSTS = {
    "minimax": {
        "name": "Minimax Hailuo 2.3",
        "cost_per_second": 0.045,
        "quality": "excellent",
        "max_duration": 6,
        "notes": "Free tier available, good for most use cases"
    },
    "minimax_fast": {
        "name": "Minimax Hailuo 2.3 Fast",
        "cost_per_second": 0.025,
        "quality": "very_good",
        "max_duration": 6,
        "notes": "50% cheaper, slightly lower quality"
    },
    "kling": {
        "name": "Kling AI 1.6",
        "cost_per_second": 0.06,
        "quality": "excellent",
        "max_duration": 10,
        "notes": "Best for realistic motion, longer videos"
    },
    "kling_fast": {
        "name": "Kling AI (Standard)",
        "cost_per_second": 0.04,
        "quality": "very_good",
        "max_duration": 5,
        "notes": "Faster generation, good quality"
    },
    "runway": {
        "name": "Runway Gen-3 Alpha",
        "cost_per_second": 0.10,
        "quality": "excellent",
        "max_duration": 10,
        "notes": "Industry standard, premium quality"
    },
    "luma": {
        "name": "Luma Dream Machine",
        "cost_per_second": 0.08,
        "quality": "very_good",
        "max_duration": 5,
        "notes": "Good for dreamy/artistic videos"
    },
    "pika": {
        "name": "Pika 1.5",
        "cost_per_second": 0.05,
        "quality": "good",
        "max_duration": 4,
        "notes": "Free tier available"
    },
}

# Audio generation costs
AUDIO_COSTS = {
    "edge_tts": {
        "name": "Edge TTS",
        "cost_per_minute": 0.0,
        "quality": "good",
        "notes": "Free, good for drafts"
    },
    "elevenlabs": {
        "name": "ElevenLabs",
        "cost_per_minute": 0.30,
        "quality": "excellent",
        "notes": "Best voice cloning"
    },
    "openai_tts": {
        "name": "OpenAI TTS",
        "cost_per_minute": 0.09,
        "quality": "very_good",
        "notes": "Good quality, reasonable price"
    },
}


@dataclass
class CostEstimate:
    """Cost estimate for a production."""
    images: Dict[str, Any] = field(default_factory=dict)
    videos: Dict[str, Any] = field(default_factory=dict)
    audio: Dict[str, Any] = field(default_factory=dict)
    total_cost: float = 0.0
    breakdown: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def estimate_image_cost(
    count: int,
    backend: str = "flux",
    resolution: str = "1024x1024"
) -> Dict[str, Any]:
    """
    Estimate cost for image generation.

    Args:
        count: Number of images to generate
        backend: Backend to use (flux, dalle, pollinations, etc.)
        resolution: Image resolution (affects some backends)

    Returns:
        Cost breakdown dict
    """
    backend_lower = backend.lower()
    if backend_lower not in IMAGE_COSTS:
        backend_lower = "flux"

    info = IMAGE_COSTS[backend_lower]
    cost_per_image = info["cost_per_image"]

    # HD resolution multiplier for DALL-E
    if backend_lower == "dalle" and "hd" in resolution.lower():
        cost_per_image = IMAGE_COSTS["dalle_hd"]["cost_per_image"]

    total = cost_per_image * count

    return {
        "backend": info["name"],
        "backend_id": backend_lower,
        "count": count,
        "cost_per_image": cost_per_image,
        "total_cost": round(total, 4),
        "quality": info["quality"],
        "notes": info["notes"],
    }


def estimate_video_cost(
    count: int,
    duration_seconds: int = 5,
    backend: str = "minimax"
) -> Dict[str, Any]:
    """
    Estimate cost for video generation.

    Args:
        count: Number of videos to generate
        duration_seconds: Duration of each video
        backend: Backend to use (minimax, kling, runway, etc.)

    Returns:
        Cost breakdown dict
    """
    backend_lower = backend.lower()
    if backend_lower not in VIDEO_COSTS:
        backend_lower = "minimax"

    info = VIDEO_COSTS[backend_lower]
    cost_per_video = info["cost_per_second"] * min(duration_seconds, info["max_duration"])
    total = cost_per_video * count

    return {
        "backend": info["name"],
        "backend_id": backend_lower,
        "count": count,
        "duration_seconds": duration_seconds,
        "cost_per_video": round(cost_per_video, 4),
        "total_cost": round(total, 4),
        "quality": info["quality"],
        "max_duration": info["max_duration"],
        "notes": info["notes"],
    }


def estimate_audio_cost(
    duration_minutes: float,
    backend: str = "edge_tts"
) -> Dict[str, Any]:
    """
    Estimate cost for audio generation.

    Args:
        duration_minutes: Total audio duration in minutes
        backend: Backend to use (edge_tts, elevenlabs, openai_tts)

    Returns:
        Cost breakdown dict
    """
    backend_lower = backend.lower()
    if backend_lower not in AUDIO_COSTS:
        backend_lower = "edge_tts"

    info = AUDIO_COSTS[backend_lower]
    total = info["cost_per_minute"] * duration_minutes

    return {
        "backend": info["name"],
        "backend_id": backend_lower,
        "duration_minutes": duration_minutes,
        "cost_per_minute": info["cost_per_minute"],
        "total_cost": round(total, 4),
        "quality": info["quality"],
        "notes": info["notes"],
    }


def estimate_production(
    images: Optional[Dict[str, Any]] = None,
    videos: Optional[Dict[str, Any]] = None,
    audio: Optional[Dict[str, Any]] = None,
    budget: Optional[float] = None
) -> CostEstimate:
    """
    Estimate total production cost.

    Args:
        images: {"count": N, "backend": "flux"}
        videos: {"count": N, "duration": 5, "backend": "minimax"}
        audio: {"duration_minutes": N, "backend": "edge_tts"}
        budget: Optional budget limit for validation

    Returns:
        CostEstimate with full breakdown
    """
    result = CostEstimate()
    total = 0.0

    # Images
    if images:
        img_est = estimate_image_cost(
            count=images.get("count", 0),
            backend=images.get("backend", "flux"),
            resolution=images.get("resolution", "1024x1024")
        )
        result.images = img_est
        total += img_est["total_cost"]
        result.breakdown.append({
            "type": "images",
            **img_est
        })

    # Videos
    if videos:
        vid_est = estimate_video_cost(
            count=videos.get("count", 0),
            duration_seconds=videos.get("duration", 5),
            backend=videos.get("backend", "minimax")
        )
        result.videos = vid_est
        total += vid_est["total_cost"]
        result.breakdown.append({
            "type": "videos",
            **vid_est
        })

    # Audio
    if audio:
        aud_est = estimate_audio_cost(
            duration_minutes=audio.get("duration_minutes", 0),
            backend=audio.get("backend", "edge_tts")
        )
        result.audio = aud_est
        total += aud_est["total_cost"]
        result.breakdown.append({
            "type": "audio",
            **aud_est
        })

    result.total_cost = round(total, 4)

    # Generate recommendations
    if images and images.get("count", 0) > 0:
        img_backend = images.get("backend", "flux").lower()
        if img_backend == "dalle" and images.get("count", 0) > 10:
            result.recommendations.append(
                "Consider using Flux instead of DALL-E for bulk image generation (same cost, faster)"
            )
        if img_backend in ["flux", "dalle"] and images.get("count", 0) > 50:
            result.recommendations.append(
                "For large batches, consider Ideogram ($0.02/image) or Midjourney subscription"
            )

    if videos and videos.get("count", 0) > 0:
        vid_backend = videos.get("backend", "minimax").lower()
        if vid_backend == "runway" and videos.get("count", 0) > 5:
            result.recommendations.append(
                "Consider Minimax or Kling for bulk video generation (50-70% cheaper than Runway)"
            )

    # Budget validation
    if budget is not None:
        if total > budget:
            result.recommendations.append(
                f"WARNING: Estimated cost (${total:.2f}) exceeds budget (${budget:.2f})"
            )
        else:
            remaining = budget - total
            result.recommendations.append(
                f"Within budget: ${remaining:.2f} remaining"
            )

    return result


def compare_backends(
    asset_type: str,
    count: int = 1,
    duration_seconds: int = 5
) -> List[Dict[str, Any]]:
    """
    Compare all backends for a given asset type.

    Args:
        asset_type: "image", "video", or "audio"
        count: Number of assets
        duration_seconds: For video, duration per clip

    Returns:
        List of backend comparisons sorted by cost
    """
    results = []

    if asset_type == "image":
        for backend_id, info in IMAGE_COSTS.items():
            total = info["cost_per_image"] * count
            results.append({
                "backend": info["name"],
                "backend_id": backend_id,
                "cost_per_unit": info["cost_per_image"],
                "total_cost": round(total, 4),
                "quality": info["quality"],
                "notes": info["notes"],
            })

    elif asset_type == "video":
        for backend_id, info in VIDEO_COSTS.items():
            effective_duration = min(duration_seconds, info["max_duration"])
            cost_per_video = info["cost_per_second"] * effective_duration
            total = cost_per_video * count
            results.append({
                "backend": info["name"],
                "backend_id": backend_id,
                "cost_per_unit": round(cost_per_video, 4),
                "total_cost": round(total, 4),
                "quality": info["quality"],
                "max_duration": info["max_duration"],
                "notes": info["notes"],
            })

    elif asset_type == "audio":
        duration_minutes = duration_seconds / 60.0
        for backend_id, info in AUDIO_COSTS.items():
            total = info["cost_per_minute"] * duration_minutes * count
            results.append({
                "backend": info["name"],
                "backend_id": backend_id,
                "cost_per_unit": info["cost_per_minute"],
                "total_cost": round(total, 4),
                "quality": info["quality"],
                "notes": info["notes"],
            })

    # Sort by cost (free first, then cheapest)
    results.sort(key=lambda x: (x["total_cost"], x["quality"] != "excellent"))

    return results


# === Skill Entry Point ===

def run(
    args: Dict[str, Any],
    tools: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for the production_cost_estimator skill.

    Args:
        action: "estimate", "compare", or "production"

        For "estimate":
            type: "image", "video", or "audio"
            count: Number of assets
            backend: Backend to use
            duration: Duration in seconds (video) or minutes (audio)

        For "compare":
            type: "image", "video", or "audio"
            count: Number of assets
            duration: Duration per asset

        For "production":
            images: {"count": N, "backend": "flux"}
            videos: {"count": N, "duration": 5, "backend": "minimax"}
            audio: {"duration_minutes": N, "backend": "edge_tts"}
            budget: Optional budget limit

    Returns:
        Cost estimate or comparison results
    """
    action = args.get("action", "estimate")

    if action == "compare":
        asset_type = args.get("type", "image")
        count = args.get("count", 1)
        duration = args.get("duration", 5)

        comparisons = compare_backends(asset_type, count, duration)

        return {
            "success": True,
            "action": "compare",
            "asset_type": asset_type,
            "count": count,
            "comparisons": comparisons,
            "cheapest": comparisons[0] if comparisons else None,
            "best_quality": next(
                (c for c in comparisons if c["quality"] == "excellent"),
                comparisons[0] if comparisons else None
            ),
        }

    elif action == "production":
        estimate = estimate_production(
            images=args.get("images"),
            videos=args.get("videos"),
            audio=args.get("audio"),
            budget=args.get("budget")
        )

        return {
            "success": True,
            "action": "production",
            "estimate": estimate.to_dict(),
            "total_cost": estimate.total_cost,
            "summary": f"Total estimated cost: ${estimate.total_cost:.2f}",
            "recommendations": estimate.recommendations,
        }

    else:  # Default: single estimate
        asset_type = args.get("type", "image")
        count = args.get("count", 1)
        backend = args.get("backend", "flux" if asset_type == "image" else "minimax")
        duration = args.get("duration", 5)

        if asset_type == "image":
            result = estimate_image_cost(count, backend)
        elif asset_type == "video":
            result = estimate_video_cost(count, duration, backend)
        elif asset_type == "audio":
            result = estimate_audio_cost(duration / 60.0, backend)
        else:
            return {"success": False, "error": f"Unknown asset type: {asset_type}"}

        return {
            "success": True,
            "action": "estimate",
            "result": result,
            "summary": f"{count}x {asset_type}(s) via {result['backend']}: ${result['total_cost']:.2f}",
        }


if __name__ == "__main__":
    # Demo: Full production estimate
    print("=== Production Cost Estimator Demo ===\n")

    # Compare video backends
    print("Video Backend Comparison (10x 5s videos):")
    for comp in compare_backends("video", count=10, duration_seconds=5):
        print(f"  {comp['backend']}: ${comp['total_cost']:.2f} ({comp['quality']})")

    print("\n" + "="*50 + "\n")

    # Full production estimate
    estimate = estimate_production(
        images={"count": 20, "backend": "flux"},
        videos={"count": 5, "duration": 6, "backend": "minimax"},
        audio={"duration_minutes": 10, "backend": "edge_tts"},
        budget=5.00
    )

    print("Full Production Estimate:")
    print(f"  Images: {estimate.images.get('count', 0)}x via {estimate.images.get('backend', 'N/A')}")
    print(f"          ${estimate.images.get('total_cost', 0):.2f}")
    print(f"  Videos: {estimate.videos.get('count', 0)}x {estimate.videos.get('duration_seconds', 0)}s via {estimate.videos.get('backend', 'N/A')}")
    print(f"          ${estimate.videos.get('total_cost', 0):.2f}")
    print(f"  Audio:  {estimate.audio.get('duration_minutes', 0):.1f}min via {estimate.audio.get('backend', 'N/A')}")
    print(f"          ${estimate.audio.get('total_cost', 0):.2f}")
    print(f"\n  TOTAL:  ${estimate.total_cost:.2f}")

    if estimate.recommendations:
        print("\nRecommendations:")
        for rec in estimate.recommendations:
            print(f"  - {rec}")
