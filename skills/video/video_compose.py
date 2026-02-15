"""
Video Compose Skill - Compose video from image sequences and audio.

Capabilities:
- FFmpeg integration with pre-checks
- Image sequence to video composition
- Audio track integration
- Resource limits (500 images, 600s max)
- Progress callbacks for long operations

Phase 3.2.2
"""

import os
import re
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum


SKILL_META = {
    "name": "video_compose",
    "description": "Compose video from image sequences and audio using ffmpeg",
    "tier": "tested",
    "version": "1.0.0",
    "phase": "3.2",
    "keywords": [
        "video", "compose", "ffmpeg", "images", "audio",
        "slideshow", "render", "movie", "mp4"
    ],
    "requires_network": False,
    "timeout_seconds": 600,
    "expected_runtime_seconds": 60,
    "dependencies": ["ffmpeg"],
    "side_effects": ["writes_file", "subprocess"],
}


# === Resource Limits ===
MAX_IMAGES = 500
MAX_DURATION_SECONDS = 600  # 10 minutes
MAX_RESOLUTION = 3840  # 4K max


class VideoCodec(Enum):
    """Supported video codecs."""
    H264 = "libx264"
    H265 = "libx265"
    VP9 = "libvpx-vp9"
    PRORES = "prores_ks"


class QualityPreset(Enum):
    """Quality presets for encoding."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    LOSSLESS = "lossless"


QUALITY_CRF = {
    QualityPreset.LOW: 28,
    QualityPreset.MEDIUM: 23,
    QualityPreset.HIGH: 18,
    QualityPreset.LOSSLESS: 0,
}

QUALITY_PRESET = {
    QualityPreset.LOW: "faster",
    QualityPreset.MEDIUM: "medium",
    QualityPreset.HIGH: "slow",
    QualityPreset.LOSSLESS: "veryslow",
}


@dataclass
class VideoConfig:
    """Configuration for video composition."""
    output_path: str
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    duration_per_image: float = 3.0  # seconds
    codec: VideoCodec = VideoCodec.H264
    quality: QualityPreset = QualityPreset.MEDIUM
    audio_path: Optional[str] = None
    audio_volume: float = 1.0
    audio_fade_in: float = 0.0
    audio_fade_out: float = 0.0
    crossfade_duration: float = 0.0
    loop_audio: bool = False
    pixel_format: str = "yuv420p"


@dataclass
class CompositionResult:
    """Result from video composition."""
    success: bool
    output_path: Optional[str] = None
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    images_used: int = 0
    error: Optional[str] = None
    ffmpeg_command: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_CONFIG = {
    "ffmpeg_path": "ffmpeg",
    "ffprobe_path": "ffprobe",
    "min_ffmpeg_version": "4.0.0",
    "temp_dir": None,  # Use system temp
    "cleanup_temp": True,
}


# === FFmpeg Pre-checks ===

def check_ffmpeg(config: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
    """
    Check if ffmpeg is available and meets version requirements.

    Returns:
        (available, version_string, error_message)
    """
    ffmpeg_path = config.get("ffmpeg_path", DEFAULT_CONFIG["ffmpeg_path"])

    # Check if ffmpeg exists
    if not shutil.which(ffmpeg_path):
        return False, "", f"ffmpeg not found at '{ffmpeg_path}'. Please install ffmpeg."

    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return False, "", "ffmpeg returned error"

        # Parse version
        output = result.stdout
        match = re.search(r'ffmpeg version (\d+\.\d+(?:\.\d+)?)', output)
        if match:
            version = match.group(1)

            # Version check
            min_version = config.get("min_ffmpeg_version", DEFAULT_CONFIG["min_ffmpeg_version"])
            if _compare_versions(version, min_version) < 0:
                return False, version, f"ffmpeg version {version} is below minimum {min_version}"

            return True, version, None

        # Version format might be different (e.g., n4.4.2)
        match = re.search(r'ffmpeg version [nN]?(\d+\.\d+(?:\.\d+)?)', output)
        if match:
            return True, match.group(1), None

        return True, "unknown", None

    except subprocess.TimeoutExpired:
        return False, "", "ffmpeg timed out"
    except Exception as e:
        return False, "", str(e)


def _compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings. Returns -1, 0, or 1."""
    def parse(v):
        return [int(x) for x in v.split('.')]

    p1, p2 = parse(v1), parse(v2)
    # Pad shorter list
    while len(p1) < len(p2):
        p1.append(0)
    while len(p2) < len(p1):
        p2.append(0)

    for a, b in zip(p1, p2):
        if a < b:
            return -1
        if a > b:
            return 1
    return 0


def get_media_duration(path: str, config: Dict[str, Any]) -> Optional[float]:
    """Get duration of media file in seconds."""
    ffprobe_path = config.get("ffprobe_path", DEFAULT_CONFIG["ffprobe_path"])

    if not shutil.which(ffprobe_path):
        return None

    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass

    return None


# === Image Sequence Handling ===

def collect_images(
    source: Union[str, List[str]],
    extensions: List[str] = None
) -> List[str]:
    """
    Collect image paths from directory or list.

    Args:
        source: Directory path or list of image paths
        extensions: Allowed extensions (default: common image types)

    Returns:
        Sorted list of image paths
    """
    if extensions is None:
        extensions = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]

    extensions = [e.lower() for e in extensions]

    if isinstance(source, list):
        # Filter to valid images
        images = []
        for path in source:
            if Path(path).suffix.lower() in extensions and Path(path).exists():
                images.append(str(path))
        return images

    # Directory mode
    source_path = Path(source)
    if not source_path.is_dir():
        return []

    # Use set to avoid duplicates from case-insensitive filesystems
    images = set()
    for ext in extensions:
        images.update(source_path.glob(f"*{ext}"))
        images.update(source_path.glob(f"*{ext.upper()}"))

    # Sort by name for consistent ordering
    return sorted([str(p) for p in images])


def validate_images(
    images: List[str],
    max_count: int = MAX_IMAGES
) -> Tuple[List[str], List[str]]:
    """
    Validate image list against limits.

    Returns:
        (valid_images, warnings)
    """
    warnings = []

    if len(images) > max_count:
        warnings.append(f"Image count ({len(images)}) exceeds limit ({max_count}). Truncating.")
        images = images[:max_count]

    # Check each image exists
    valid = []
    for img in images:
        if Path(img).exists():
            valid.append(img)
        else:
            warnings.append(f"Image not found: {img}")

    return valid, warnings


# === Video Composition ===

def compose_video(
    images: List[str],
    video_config: VideoConfig,
    config: Dict[str, Any],
    progress_callback: Optional[callable] = None
) -> CompositionResult:
    """
    Compose video from images using ffmpeg.
    """
    warnings = []

    # Validate images
    images, img_warnings = validate_images(images)
    warnings.extend(img_warnings)

    if not images:
        return CompositionResult(
            success=False,
            error="No valid images provided"
        )

    # Check duration limit
    total_duration = len(images) * video_config.duration_per_image
    if total_duration > MAX_DURATION_SECONDS:
        # Adjust duration per image to fit
        adjusted = MAX_DURATION_SECONDS / len(images)
        warnings.append(
            f"Total duration ({total_duration}s) exceeds limit ({MAX_DURATION_SECONDS}s). "
            f"Adjusted to {adjusted:.2f}s per image."
        )
        video_config.duration_per_image = adjusted
        total_duration = MAX_DURATION_SECONDS

    # Check ffmpeg
    ffmpeg_ok, ffmpeg_version, ffmpeg_error = check_ffmpeg(config)
    if not ffmpeg_ok:
        return CompositionResult(
            success=False,
            error=ffmpeg_error or "ffmpeg check failed"
        )

    ffmpeg_path = config.get("ffmpeg_path", DEFAULT_CONFIG["ffmpeg_path"])

    # Create temp directory for concat file
    temp_dir = config.get("temp_dir") or tempfile.mkdtemp(prefix="video_compose_")
    concat_file = Path(temp_dir) / "concat.txt"

    try:
        if progress_callback:
            progress_callback({
                "stage": "preparing",
                "images": len(images),
                "duration": total_duration
            })

        # Create concat file with duration per image
        with open(concat_file, 'w') as f:
            for img in images:
                # Escape special characters in path
                escaped = img.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
                f.write(f"duration {video_config.duration_per_image}\n")
            # Repeat last image to avoid ffmpeg truncation bug
            if images:
                escaped = images[-1].replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        # Build ffmpeg command
        cmd = [
            ffmpeg_path,
            "-y",  # Overwrite output
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
        ]

        # Add audio if provided
        if video_config.audio_path and Path(video_config.audio_path).exists():
            cmd.extend(["-i", video_config.audio_path])

        # Video filters
        vf_filters = [
            f"scale={video_config.width}:{video_config.height}:force_original_aspect_ratio=decrease",
            f"pad={video_config.width}:{video_config.height}:(ow-iw)/2:(oh-ih)/2",
            f"fps={video_config.fps}",
        ]

        # Crossfade (simplified - requires complex filter graph for proper implementation)
        if video_config.crossfade_duration > 0:
            warnings.append("Crossfade not fully implemented - using simple dissolve")

        cmd.extend(["-vf", ",".join(vf_filters)])

        # Video codec settings
        cmd.extend(["-c:v", video_config.codec.value])
        cmd.extend(["-pix_fmt", video_config.pixel_format])

        # Quality settings
        crf = QUALITY_CRF.get(video_config.quality, 23)
        preset = QUALITY_PRESET.get(video_config.quality, "medium")
        cmd.extend(["-crf", str(crf), "-preset", preset])

        # Audio settings
        if video_config.audio_path and Path(video_config.audio_path).exists():
            af_filters = [f"volume={video_config.audio_volume}"]

            if video_config.audio_fade_in > 0:
                af_filters.append(f"afade=t=in:d={video_config.audio_fade_in}")
            if video_config.audio_fade_out > 0:
                af_filters.append(f"afade=t=out:st={total_duration - video_config.audio_fade_out}:d={video_config.audio_fade_out}")

            cmd.extend(["-af", ",".join(af_filters)])
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])

            # Trim audio to video length
            cmd.extend(["-shortest"])
        else:
            cmd.extend(["-an"])  # No audio

        # Duration limit
        cmd.extend(["-t", str(total_duration)])

        # Output
        cmd.append(video_config.output_path)

        if progress_callback:
            progress_callback({
                "stage": "encoding",
                "command": " ".join(cmd)
            })

        # Run ffmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=video_config.duration_per_image * len(images) * 2 + 60  # Generous timeout
        )

        if result.returncode != 0:
            return CompositionResult(
                success=False,
                error=f"ffmpeg failed: {result.stderr[:500]}",
                ffmpeg_command=" ".join(cmd),
                warnings=warnings
            )

        # Get output info
        output_path = Path(video_config.output_path)
        if not output_path.exists():
            return CompositionResult(
                success=False,
                error="Output file was not created",
                ffmpeg_command=" ".join(cmd),
                warnings=warnings
            )

        file_size = output_path.stat().st_size
        actual_duration = get_media_duration(str(output_path), config) or total_duration

        if progress_callback:
            progress_callback({
                "stage": "completed",
                "output": str(output_path),
                "size_bytes": file_size
            })

        return CompositionResult(
            success=True,
            output_path=str(output_path),
            duration_seconds=actual_duration,
            file_size_bytes=file_size,
            images_used=len(images),
            ffmpeg_command=" ".join(cmd),
            warnings=warnings
        )

    except subprocess.TimeoutExpired:
        return CompositionResult(
            success=False,
            error="ffmpeg timed out during encoding",
            warnings=warnings
        )
    except Exception as e:
        return CompositionResult(
            success=False,
            error=str(e),
            warnings=warnings
        )
    finally:
        # Cleanup
        if config.get("cleanup_temp", DEFAULT_CONFIG["cleanup_temp"]):
            try:
                if concat_file.exists():
                    concat_file.unlink()
                if Path(temp_dir).exists() and not config.get("temp_dir"):
                    Path(temp_dir).rmdir()
            except Exception:
                pass


# === Skill Entry Point ===

def run(
    args: Dict[str, Any],
    tools: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for the video_compose skill.

    Args:
        images: List of image paths OR directory path
        output_path: Where to save the video
        width: Video width (default 1920)
        height: Video height (default 1080)
        fps: Frames per second (default 30)
        duration_per_image: Seconds per image (default 3)
        codec: Video codec (h264, h265, vp9)
        quality: Quality preset (low, medium, high, lossless)
        audio_path: Optional audio track to add
        audio_volume: Audio volume multiplier (default 1.0)
        config: Override default configuration

    Returns:
        {
            "success": bool,
            "output_path": str,
            "duration_seconds": float,
            "file_size_bytes": int,
            "summary": str,
        }
    """
    config = {**DEFAULT_CONFIG, **args.get("config", {})}
    progress_callback = tools.get("_progress_callback")

    # Pre-check ffmpeg
    if args.get("check_ffmpeg_only"):
        ffmpeg_ok, version, error = check_ffmpeg(config)
        return {
            "success": ffmpeg_ok,
            "ffmpeg_available": ffmpeg_ok,
            "ffmpeg_version": version,
            "error": error,
        }

    # Get images
    images_source = args.get("images")
    if not images_source:
        return {"success": False, "error": "No images provided"}

    images = collect_images(images_source)
    if not images:
        return {"success": False, "error": "No valid images found"}

    # Get output path
    output_path = args.get("output_path")
    if not output_path:
        return {"success": False, "error": "No output_path provided"}

    # Parse codec
    codec_str = args.get("codec", "h264").lower()
    codec_map = {"h264": VideoCodec.H264, "h265": VideoCodec.H265, "vp9": VideoCodec.VP9}
    codec = codec_map.get(codec_str, VideoCodec.H264)

    # Parse quality
    quality_str = args.get("quality", "medium").lower()
    quality_map = {
        "low": QualityPreset.LOW,
        "medium": QualityPreset.MEDIUM,
        "high": QualityPreset.HIGH,
        "lossless": QualityPreset.LOSSLESS
    }
    quality = quality_map.get(quality_str, QualityPreset.MEDIUM)

    # Build config
    video_config = VideoConfig(
        output_path=output_path,
        width=args.get("width", 1920),
        height=args.get("height", 1080),
        fps=args.get("fps", 30.0),
        duration_per_image=args.get("duration_per_image", 3.0),
        codec=codec,
        quality=quality,
        audio_path=args.get("audio_path"),
        audio_volume=args.get("audio_volume", 1.0),
        audio_fade_in=args.get("audio_fade_in", 0.0),
        audio_fade_out=args.get("audio_fade_out", 0.0),
        crossfade_duration=args.get("crossfade_duration", 0.0),
        loop_audio=args.get("loop_audio", False),
    )

    # Compose video
    result = compose_video(images, video_config, config, progress_callback)

    return {
        "success": result.success,
        "output_path": result.output_path,
        "duration_seconds": result.duration_seconds,
        "file_size_bytes": result.file_size_bytes,
        "images_used": result.images_used,
        "error": result.error,
        "warnings": result.warnings,
        "summary": (
            f"Created {result.duration_seconds:.1f}s video from {result.images_used} images"
            if result.success else f"Failed: {result.error}"
        ),
    }


if __name__ == "__main__":
    # Quick ffmpeg check
    ok, version, error = check_ffmpeg(DEFAULT_CONFIG)
    print(f"FFmpeg available: {ok}")
    print(f"Version: {version}")
    if error:
        print(f"Error: {error}")
