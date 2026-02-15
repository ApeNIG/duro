"""
Video Subtitle Skill - Add subtitles/captions to videos.

Capabilities:
- SRT and VTT format support
- Burn-in (hardcode) subtitles via ffmpeg
- Soft subtitles (embedded track)
- Style customization (font, size, color, position)
- Subtitle generation from text with timing

Phase 3.2.3
"""

import os
import re
import json
import subprocess
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum


SKILL_META = {
    "name": "video_subtitle",
    "description": "Add subtitles/captions to videos using SRT/VTT",
    "tier": "tested",
    "version": "1.0.0",
    "phase": "3.2",
    "keywords": [
        "subtitle", "caption", "srt", "vtt", "video",
        "text", "overlay", "accessibility", "cc"
    ],
    "requires_network": False,
    "timeout_seconds": 300,
    "expected_runtime_seconds": 30,
    "dependencies": ["ffmpeg"],
    "side_effects": ["writes_file", "subprocess"],
}


class SubtitleFormat(Enum):
    """Supported subtitle formats."""
    SRT = "srt"
    VTT = "vtt"


class SubtitleMode(Enum):
    """How to add subtitles to video."""
    BURN_IN = "burn_in"      # Hardcode into video
    SOFT = "soft"             # Embed as separate track


class SubtitlePosition(Enum):
    """Subtitle position on screen."""
    BOTTOM = "bottom"
    TOP = "top"
    MIDDLE = "middle"


@dataclass
class SubtitleStyle:
    """Styling options for burned-in subtitles."""
    font_name: str = "Arial"
    font_size: int = 24
    primary_color: str = "white"
    outline_color: str = "black"
    outline_width: int = 2
    shadow_offset: int = 1
    position: SubtitlePosition = SubtitlePosition.BOTTOM
    margin_vertical: int = 20
    bold: bool = False
    italic: bool = False


@dataclass
class SubtitleEntry:
    """A single subtitle entry."""
    index: int
    start_time: float  # seconds
    end_time: float    # seconds
    text: str

    def to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def to_vtt_time(self, seconds: float) -> str:
        """Convert seconds to VTT time format (HH:MM:SS.mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def to_srt(self) -> str:
        """Convert to SRT format."""
        return (
            f"{self.index}\n"
            f"{self.to_srt_time(self.start_time)} --> {self.to_srt_time(self.end_time)}\n"
            f"{self.text}\n"
        )

    def to_vtt(self) -> str:
        """Convert to VTT format."""
        return (
            f"{self.to_vtt_time(self.start_time)} --> {self.to_vtt_time(self.end_time)}\n"
            f"{self.text}\n"
        )


@dataclass
class SubtitleResult:
    """Result from subtitle operation."""
    success: bool
    output_path: Optional[str] = None
    subtitle_count: int = 0
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_CONFIG = {
    "ffmpeg_path": "ffmpeg",
    "default_style": SubtitleStyle(),
    "max_subtitle_length": 200,  # chars per subtitle
    "default_duration": 4.0,     # seconds per subtitle if auto-timing
}


# === Subtitle Parsing ===

def parse_srt_time(time_str: str) -> float:
    """Parse SRT time format to seconds."""
    # Format: HH:MM:SS,mmm
    match = re.match(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})', time_str.strip())
    if not match:
        raise ValueError(f"Invalid SRT time format: {time_str}")

    hours, minutes, seconds, millis = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def parse_srt(content: str) -> List[SubtitleEntry]:
    """Parse SRT subtitle content."""
    entries = []
    blocks = re.split(r'\n\n+', content.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        try:
            index = int(lines[0])
            time_parts = lines[1].split(' --> ')
            start_time = parse_srt_time(time_parts[0])
            end_time = parse_srt_time(time_parts[1])
            text = '\n'.join(lines[2:])

            entries.append(SubtitleEntry(
                index=index,
                start_time=start_time,
                end_time=end_time,
                text=text
            ))
        except (ValueError, IndexError):
            continue

    return entries


def parse_vtt(content: str) -> List[SubtitleEntry]:
    """Parse VTT subtitle content."""
    entries = []

    # Remove WEBVTT header
    content = re.sub(r'^WEBVTT.*?\n\n', '', content, flags=re.MULTILINE)
    blocks = re.split(r'\n\n+', content.strip())

    index = 1
    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue

        # Find timing line
        timing_line = None
        text_start = 0
        for i, line in enumerate(lines):
            if ' --> ' in line:
                timing_line = line
                text_start = i + 1
                break

        if not timing_line:
            continue

        try:
            time_parts = timing_line.split(' --> ')
            start_time = parse_srt_time(time_parts[0])  # Same format works
            end_time = parse_srt_time(time_parts[1].split()[0])  # May have styling
            text = '\n'.join(lines[text_start:])

            entries.append(SubtitleEntry(
                index=index,
                start_time=start_time,
                end_time=end_time,
                text=text
            ))
            index += 1
        except (ValueError, IndexError):
            continue

    return entries


def parse_subtitles(content: str, format: SubtitleFormat) -> List[SubtitleEntry]:
    """Parse subtitles from content."""
    if format == SubtitleFormat.SRT:
        return parse_srt(content)
    elif format == SubtitleFormat.VTT:
        return parse_vtt(content)
    else:
        raise ValueError(f"Unsupported format: {format}")


def detect_format(path: str, content: str) -> SubtitleFormat:
    """Detect subtitle format from path or content."""
    if path.lower().endswith('.vtt'):
        return SubtitleFormat.VTT
    if path.lower().endswith('.srt'):
        return SubtitleFormat.SRT

    # Check content
    if content.strip().startswith('WEBVTT'):
        return SubtitleFormat.VTT

    return SubtitleFormat.SRT


# === Subtitle Generation ===

def generate_subtitles_from_text(
    texts: List[str],
    start_time: float = 0.0,
    duration_per_subtitle: float = 4.0,
    gap: float = 0.5
) -> List[SubtitleEntry]:
    """
    Generate subtitle entries from text list.

    Args:
        texts: List of subtitle text strings
        start_time: Start time for first subtitle
        duration_per_subtitle: Duration of each subtitle
        gap: Gap between subtitles
    """
    entries = []
    current_time = start_time

    for i, text in enumerate(texts, 1):
        end_time = current_time + duration_per_subtitle
        entries.append(SubtitleEntry(
            index=i,
            start_time=current_time,
            end_time=end_time,
            text=text
        ))
        current_time = end_time + gap

    return entries


def write_srt(entries: List[SubtitleEntry], path: str) -> None:
    """Write subtitles to SRT file."""
    content = '\n'.join(entry.to_srt() for entry in entries)
    Path(path).write_text(content, encoding='utf-8')


def write_vtt(entries: List[SubtitleEntry], path: str) -> None:
    """Write subtitles to VTT file."""
    content = "WEBVTT\n\n" + '\n'.join(entry.to_vtt() for entry in entries)
    Path(path).write_text(content, encoding='utf-8')


# === FFmpeg Integration ===

def check_ffmpeg(config: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if ffmpeg is available."""
    ffmpeg_path = config.get("ffmpeg_path", DEFAULT_CONFIG["ffmpeg_path"])

    if not shutil.which(ffmpeg_path):
        return False, f"ffmpeg not found at '{ffmpeg_path}'"

    return True, ""


def build_subtitle_filter(style: SubtitleStyle, subtitle_path: str) -> str:
    """Build ffmpeg subtitle filter string."""
    # Color format for ASS: &HBBGGRR (BGR, not RGB)
    color_map = {
        "white": "&HFFFFFF",
        "black": "&H000000",
        "yellow": "&H00FFFF",
        "red": "&H0000FF",
        "blue": "&HFF0000",
        "green": "&H00FF00",
    }

    primary = color_map.get(style.primary_color.lower(), "&HFFFFFF")
    outline = color_map.get(style.outline_color.lower(), "&H000000")

    # Position alignment (ASS style)
    alignment_map = {
        SubtitlePosition.BOTTOM: 2,   # Bottom center
        SubtitlePosition.TOP: 8,      # Top center
        SubtitlePosition.MIDDLE: 5,   # Middle center
    }
    alignment = alignment_map.get(style.position, 2)

    # Escape path for filter
    escaped_path = subtitle_path.replace('\\', '/').replace(':', '\\:')

    # Build force_style string
    force_style = (
        f"FontName={style.font_name},"
        f"FontSize={style.font_size},"
        f"PrimaryColour={primary},"
        f"OutlineColour={outline},"
        f"Outline={style.outline_width},"
        f"Shadow={style.shadow_offset},"
        f"Alignment={alignment},"
        f"MarginV={style.margin_vertical}"
    )

    if style.bold:
        force_style += ",Bold=1"
    if style.italic:
        force_style += ",Italic=1"

    return f"subtitles='{escaped_path}':force_style='{force_style}'"


def add_subtitles(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    mode: SubtitleMode,
    style: SubtitleStyle,
    config: Dict[str, Any],
    progress_callback: Optional[callable] = None
) -> SubtitleResult:
    """
    Add subtitles to video.
    """
    # Check inputs
    if not Path(video_path).exists():
        return SubtitleResult(success=False, error=f"Video not found: {video_path}")
    if not Path(subtitle_path).exists():
        return SubtitleResult(success=False, error=f"Subtitle not found: {subtitle_path}")

    # Check ffmpeg
    ffmpeg_ok, ffmpeg_error = check_ffmpeg(config)
    if not ffmpeg_ok:
        return SubtitleResult(success=False, error=ffmpeg_error)

    ffmpeg_path = config.get("ffmpeg_path", DEFAULT_CONFIG["ffmpeg_path"])

    # Parse subtitles to get count
    try:
        content = Path(subtitle_path).read_text(encoding='utf-8')
        format = detect_format(subtitle_path, content)
        entries = parse_subtitles(content, format)
        subtitle_count = len(entries)
    except Exception as e:
        return SubtitleResult(success=False, error=f"Failed to parse subtitles: {e}")

    if progress_callback:
        progress_callback({
            "stage": "encoding",
            "mode": mode.value,
            "subtitle_count": subtitle_count
        })

    try:
        if mode == SubtitleMode.BURN_IN:
            # Burn subtitles into video
            subtitle_filter = build_subtitle_filter(style, subtitle_path)

            cmd = [
                ffmpeg_path,
                "-y",
                "-i", video_path,
                "-vf", subtitle_filter,
                "-c:a", "copy",
                output_path
            ]
        else:
            # Soft subtitles (embed as track)
            cmd = [
                ffmpeg_path,
                "-y",
                "-i", video_path,
                "-i", subtitle_path,
                "-c:v", "copy",
                "-c:a", "copy",
                "-c:s", "mov_text",  # For MP4
                "-metadata:s:s:0", "language=eng",
                output_path
            ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            return SubtitleResult(
                success=False,
                error=f"ffmpeg failed: {result.stderr[:500]}"
            )

        # Get output info
        output_file = Path(output_path)
        if not output_file.exists():
            return SubtitleResult(success=False, error="Output file not created")

        file_size = output_file.stat().st_size

        if progress_callback:
            progress_callback({
                "stage": "completed",
                "output": output_path
            })

        return SubtitleResult(
            success=True,
            output_path=output_path,
            subtitle_count=subtitle_count,
            file_size_bytes=file_size
        )

    except subprocess.TimeoutExpired:
        return SubtitleResult(success=False, error="ffmpeg timed out")
    except Exception as e:
        return SubtitleResult(success=False, error=str(e))


# === Skill Entry Point ===

def run(
    args: Dict[str, Any],
    tools: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for the video_subtitle skill.

    Args:
        video_path: Input video path
        subtitle_path: Path to SRT/VTT file (or use 'texts' to generate)
        output_path: Output video path
        mode: "burn_in" or "soft" (default: burn_in)
        texts: List of subtitle texts (auto-generate SRT)
        style: Subtitle style options
        config: Override default configuration

    Returns:
        {
            "success": bool,
            "output_path": str,
            "subtitle_count": int,
            "summary": str,
        }
    """
    config = {**DEFAULT_CONFIG, **args.get("config", {})}
    progress_callback = tools.get("_progress_callback")

    video_path = args.get("video_path")
    output_path = args.get("output_path")
    subtitle_path = args.get("subtitle_path")

    if not video_path:
        return {"success": False, "error": "No video_path provided"}
    if not output_path:
        return {"success": False, "error": "No output_path provided"}

    # Generate subtitles from text if provided
    if "texts" in args and not subtitle_path:
        texts = args["texts"]
        if not texts:
            return {"success": False, "error": "Empty texts list"}

        # Generate SRT
        entries = generate_subtitles_from_text(
            texts,
            start_time=args.get("start_time", 0.0),
            duration_per_subtitle=args.get("duration_per_subtitle", config["default_duration"]),
            gap=args.get("gap", 0.5)
        )

        # Write to temp file
        import tempfile
        fd, subtitle_path = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        write_srt(entries, subtitle_path)

    if not subtitle_path:
        return {"success": False, "error": "No subtitle_path or texts provided"}

    # Parse mode
    mode_str = args.get("mode", "burn_in").lower()
    mode_map = {"burn_in": SubtitleMode.BURN_IN, "soft": SubtitleMode.SOFT}
    mode = mode_map.get(mode_str, SubtitleMode.BURN_IN)

    # Build style
    style_args = args.get("style", {})
    style = SubtitleStyle(
        font_name=style_args.get("font_name", "Arial"),
        font_size=style_args.get("font_size", 24),
        primary_color=style_args.get("primary_color", "white"),
        outline_color=style_args.get("outline_color", "black"),
        outline_width=style_args.get("outline_width", 2),
        position=SubtitlePosition(style_args.get("position", "bottom")),
        margin_vertical=style_args.get("margin_vertical", 20),
        bold=style_args.get("bold", False),
        italic=style_args.get("italic", False),
    )

    result = add_subtitles(
        video_path, subtitle_path, output_path,
        mode, style, config, progress_callback
    )

    return {
        "success": result.success,
        "output_path": result.output_path,
        "subtitle_count": result.subtitle_count,
        "file_size_bytes": result.file_size_bytes,
        "error": result.error,
        "warnings": result.warnings,
        "summary": (
            f"Added {result.subtitle_count} subtitles to video ({mode.value})"
            if result.success else f"Failed: {result.error}"
        ),
    }


if __name__ == "__main__":
    # Quick test: parse SRT
    test_srt = """1
00:00:00,000 --> 00:00:03,000
Hello World

2
00:00:03,500 --> 00:00:06,000
This is a test"""

    entries = parse_srt(test_srt)
    print(f"Parsed {len(entries)} entries")
    for e in entries:
        print(f"  {e.index}: {e.start_time}s - {e.end_time}s: {e.text}")
