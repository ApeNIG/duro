"""
Skill: episode_produce
Description: Full episode production pipeline: script -> audio -> images -> video
Tier: tested
Phase: 3.4

Composes:
- audio/generate_tts.py
- image/image_generate.py
- video/video_compose.py
- video/video_subtitle.py

This is the main multi-modal composition skill that orchestrates all media
production skills to create a complete video episode from a script.
"""

import os
import sys
import re
import json
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Callable
from enum import Enum

# Add sibling skills to path
SKILLS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILLS_DIR / "audio"))
sys.path.insert(0, str(SKILLS_DIR / "image"))
sys.path.insert(0, str(SKILLS_DIR / "video"))


# === Skill Metadata ===

SKILL_META = {
    "name": "episode_produce",
    "description": "Full episode production: script -> audio -> images -> video",
    "tier": "tested",
    "version": "1.0.0",
    "phase": "3.4",
    "composes": [
        "audio/generate_tts.py",
        "image/image_generate.py",
        "video/video_compose.py",
        "video/video_subtitle.py"
    ],
    "keywords": [
        "episode", "video", "production", "script", "audio",
        "images", "compose", "pipeline", "multimodal"
    ]
}

DEFAULT_CONFIG = {
    "max_images": 500,
    "max_duration_seconds": 600,
    "continue_on_error": True,
    "cleanup_on_failure": True,
    "generate_subtitles": True,
    "video_width": 1920,
    "video_height": 1080,
    "video_fps": 30,
    "duration_per_scene": 5.0,
    "image_style": "cinematic",
    "subtitle_style": {
        "font_size": 24,
        "font_color": "white",
        "outline_color": "black",
        "outline_width": 2,
        "position": "bottom"
    }
}


# === Data Classes ===

class ProductionStage(Enum):
    """Stages of episode production."""
    INIT = "init"
    PARSE_SCRIPT = "parse_script"
    GENERATE_AUDIO = "generate_audio"
    GENERATE_IMAGES = "generate_images"
    COMPOSE_VIDEO = "compose_video"
    ADD_SUBTITLES = "add_subtitles"
    FINALIZE = "finalize"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class SceneInfo:
    """Information about a scene in the script."""
    scene_number: int
    title: str
    description: str
    dialogue: List[Dict[str, str]] = field(default_factory=list)
    image_prompt: str = ""
    duration_seconds: float = 5.0


@dataclass
class DialogueLine:
    """A single dialogue line."""
    character: str
    text: str
    scene_number: int
    line_number: int
    line_type: str = "dialogue"  # dialogue, voiceover, narration
    audio_path: Optional[str] = None


@dataclass
class ProductionAsset:
    """A produced asset (audio, image, video)."""
    asset_type: str  # audio, image, video
    path: str
    scene_number: Optional[int] = None
    character: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    """Result of a production stage."""
    stage: ProductionStage
    success: bool
    assets: List[ProductionAsset] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class ProductionResult:
    """Final result of episode production."""
    success: bool
    output_path: Optional[str] = None
    stages: List[StageResult] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    scenes_count: int = 0
    audio_files: int = 0
    image_files: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    assets: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output_path": self.output_path,
            "stages": [
                {
                    "stage": s.stage.value,
                    "success": s.success,
                    "assets_count": len(s.assets),
                    "errors": s.errors,
                    "warnings": s.warnings,
                    "duration_seconds": s.duration_seconds
                }
                for s in self.stages
            ],
            "total_duration_seconds": self.total_duration_seconds,
            "scenes_count": self.scenes_count,
            "audio_files": self.audio_files,
            "image_files": self.image_files,
            "errors": self.errors,
            "warnings": self.warnings,
            "assets": self.assets
        }


# === Script Parsing ===

def parse_script(script_content: str) -> Tuple[List[SceneInfo], List[DialogueLine]]:
    """
    Parse a script file into scenes and dialogue.

    Supported formats:
    - Markdown with ## Scene headers
    - **CHARACTER:** "Dialogue" format
    - [Description] for scene descriptions
    - (action) for stage directions

    Returns:
        Tuple of (scenes, dialogue_lines)
    """
    scenes = []
    dialogue_lines = []
    current_scene = None
    scene_number = 0
    line_number = 0

    # Track pending character for multiline dialogue
    pending_character = None
    pending_context = None

    lines = script_content.split('\n')

    for line in lines:
        stripped = line.strip()

        # Scene header: ## Scene 1: Title or ## SCENE 1
        scene_match = re.match(r'^##\s*(?:Scene\s*)?(\d+)(?::\s*(.+))?$', stripped, re.IGNORECASE)
        if scene_match:
            scene_number = int(scene_match.group(1))
            title = scene_match.group(2) or f"Scene {scene_number}"
            current_scene = SceneInfo(
                scene_number=scene_number,
                title=title.strip(),
                description=""
            )
            scenes.append(current_scene)
            pending_character = None
            continue

        # Scene description: [Description text]
        desc_match = re.match(r'^\[(.+)\]$', stripped)
        if desc_match and current_scene:
            desc = desc_match.group(1).strip()
            if current_scene.description:
                current_scene.description += " " + desc
            else:
                current_scene.description = desc
            # Use description as image prompt if not set
            if not current_scene.image_prompt:
                current_scene.image_prompt = desc
            continue

        # Check for quoted text following a pending character
        if pending_character and stripped.startswith('"') and stripped.endswith('"'):
            text = stripped[1:-1].strip()
            line_type = "dialogue"
            if pending_context and "voiceover" in pending_context.lower():
                line_type = "voiceover"
            elif pending_context and "narrat" in pending_context.lower():
                line_type = "narration"

            line_number += 1
            scene_num = scene_number if scene_number > 0 else 1

            dialogue_line = DialogueLine(
                character=pending_character,
                text=text,
                scene_number=scene_num,
                line_number=line_number,
                line_type=line_type
            )
            dialogue_lines.append(dialogue_line)

            if current_scene:
                current_scene.dialogue.append({
                    "character": pending_character,
                    "text": text,
                    "type": line_type
                })

            pending_character = None
            pending_context = None
            continue

        # Character line only: **CHARACTER:** or **CHARACTER (context):**
        char_only_match = re.match(
            r'\*\*([A-Z][A-Za-z0-9_]+)(?:\s*\(([^)]+)\))?\s*:\*\*\s*$',
            stripped
        )
        if char_only_match:
            pending_character = char_only_match.group(1).lower()
            pending_context = char_only_match.group(2) or ""
            continue

        # Dialogue: **CHARACTER:** "Text" or **CHARACTER (context):** "Text" (single line)
        dialogue_match = re.match(
            r'\*\*([A-Z][A-Za-z0-9_]+)(?:\s*\(([^)]+)\))?\s*:\*\*\s*"([^"]+)"',
            stripped
        )
        if dialogue_match:
            character = dialogue_match.group(1).lower()
            context = dialogue_match.group(2) or ""
            text = dialogue_match.group(3).strip()

            line_type = "dialogue"
            if "voiceover" in context.lower():
                line_type = "voiceover"
            elif "narrat" in context.lower():
                line_type = "narration"

            line_number += 1
            scene_num = scene_number if scene_number > 0 else 1

            dialogue_line = DialogueLine(
                character=character,
                text=text,
                scene_number=scene_num,
                line_number=line_number,
                line_type=line_type
            )
            dialogue_lines.append(dialogue_line)

            if current_scene:
                current_scene.dialogue.append({
                    "character": character,
                    "text": text,
                    "type": line_type
                })
            continue

        # Also try multiline dialogue format
        # **CHARACTER:**
        # "Dialogue text"
        char_only_match = re.match(r'\*\*([A-Z][A-Za-z0-9_]+)(?:\s*\(([^)]+)\))?\s*:\*\*\s*$', stripped)
        if char_only_match:
            # Store character for next line
            _pending_char = char_only_match.group(1).lower()
            _pending_context = char_only_match.group(2) or ""
            continue

    # If no scenes were found, create a default scene
    if not scenes and dialogue_lines:
        default_scene = SceneInfo(
            scene_number=1,
            title="Scene 1",
            description="Episode scene",
            image_prompt="cinematic scene"
        )
        default_scene.dialogue = [
            {"character": d.character, "text": d.text, "type": d.line_type}
            for d in dialogue_lines
        ]
        scenes.append(default_scene)

    return scenes, dialogue_lines


def generate_image_prompts(scenes: List[SceneInfo], style: str = "cinematic") -> List[SceneInfo]:
    """
    Generate or enhance image prompts for scenes.

    Args:
        scenes: List of scene info
        style: Visual style to apply

    Returns:
        Updated scenes with image prompts
    """
    style_modifiers = {
        "cinematic": "cinematic lighting, dramatic composition, film quality",
        "anime": "anime style, vibrant colors, detailed illustration",
        "photorealistic": "photorealistic, high detail, natural lighting",
        "cartoon": "cartoon style, bold colors, clean lines",
        "noir": "film noir style, high contrast, black and white tones",
        "fantasy": "fantasy art style, magical atmosphere, ethereal lighting"
    }

    modifier = style_modifiers.get(style, style_modifiers["cinematic"])

    for scene in scenes:
        if not scene.image_prompt:
            # Generate from title and description
            if scene.description:
                scene.image_prompt = scene.description
            else:
                scene.image_prompt = f"Scene depicting {scene.title}"

        # Add style modifier
        scene.image_prompt = f"{scene.image_prompt}, {modifier}"

    return scenes


# === Audio Generation ===

def generate_audio_assets(
    dialogue_lines: List[DialogueLine],
    output_dir: Path,
    config: Dict[str, Any],
    progress_callback: Optional[Callable] = None
) -> StageResult:
    """
    Generate audio for all dialogue lines.

    Args:
        dialogue_lines: List of dialogue to generate
        output_dir: Directory for audio files
        config: Configuration options
        progress_callback: Optional progress callback

    Returns:
        StageResult with audio assets
    """
    from generate_tts import generate_speech, VOICE_PRESETS

    start_time = datetime.now()
    result = StageResult(
        stage=ProductionStage.GENERATE_AUDIO,
        success=True
    )

    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    total = len(dialogue_lines)
    continue_on_error = config.get("continue_on_error", True)

    for i, line in enumerate(dialogue_lines):
        if progress_callback:
            progress_callback({
                "stage": "generate_audio",
                "step": i + 1,
                "total": total,
                "message": f"Generating audio for {line.character} line {line.line_number}"
            })

        # Generate filename
        filename = f"{line.character}_scene{line.scene_number}_line{line.line_number}.mp3"
        output_path = audio_dir / filename

        # Get voice for character
        voice = VOICE_PRESETS.get(line.character, "en-GB-SoniaNeural")

        try:
            tts_result = generate_speech(line.text, voice, str(output_path))

            if tts_result.get("success"):
                line.audio_path = str(output_path)
                result.assets.append(ProductionAsset(
                    asset_type="audio",
                    path=str(output_path),
                    scene_number=line.scene_number,
                    character=line.character,
                    success=True,
                    metadata={
                        "line_number": line.line_number,
                        "duration": tts_result.get("duration", 0),
                        "file_size": tts_result.get("file_size", 0)
                    }
                ))
            else:
                error_msg = tts_result.get("error", "Unknown TTS error")
                result.errors.append(f"Audio for {line.character} line {line.line_number}: {error_msg}")
                result.assets.append(ProductionAsset(
                    asset_type="audio",
                    path=str(output_path),
                    scene_number=line.scene_number,
                    character=line.character,
                    success=False,
                    error=error_msg
                ))
                if not continue_on_error:
                    result.success = False
                    break

        except Exception as e:
            error_msg = str(e)
            result.errors.append(f"Audio for {line.character} line {line.line_number}: {error_msg}")
            if not continue_on_error:
                result.success = False
                break

    # Check if we have enough successful audio
    successful_audio = [a for a in result.assets if a.success]
    if len(successful_audio) == 0 and len(dialogue_lines) > 0:
        result.success = False
        result.errors.append("No audio files were generated successfully")

    result.duration_seconds = (datetime.now() - start_time).total_seconds()
    return result


# === Image Generation ===

def generate_image_assets(
    scenes: List[SceneInfo],
    output_dir: Path,
    config: Dict[str, Any],
    progress_callback: Optional[Callable] = None
) -> StageResult:
    """
    Generate images for all scenes.

    Args:
        scenes: List of scenes
        output_dir: Directory for images
        config: Configuration options
        progress_callback: Optional progress callback

    Returns:
        StageResult with image assets
    """
    # Import image generation
    try:
        from image_generate import generate_image, ImageConfig
    except ImportError:
        # Fallback: return placeholder result
        return StageResult(
            stage=ProductionStage.GENERATE_IMAGES,
            success=False,
            errors=["image_generate skill not available"]
        )

    start_time = datetime.now()
    result = StageResult(
        stage=ProductionStage.GENERATE_IMAGES,
        success=True
    )

    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    # Check resource limits
    max_images = config.get("max_images", 500)
    if len(scenes) > max_images:
        result.warnings.append(f"Limiting to {max_images} images (requested {len(scenes)})")
        scenes = scenes[:max_images]

    total = len(scenes)
    continue_on_error = config.get("continue_on_error", True)
    width = config.get("video_width", 1920)
    height = config.get("video_height", 1080)
    style = config.get("image_style", "cinematic")

    for i, scene in enumerate(scenes):
        if progress_callback:
            progress_callback({
                "stage": "generate_images",
                "step": i + 1,
                "total": total,
                "message": f"Generating image for scene {scene.scene_number}"
            })

        filename = f"scene_{scene.scene_number:03d}.png"
        output_path = image_dir / filename

        try:
            img_config = ImageConfig(
                width=width,
                height=height,
                style=style
            )

            img_result = generate_image(
                prompt=scene.image_prompt,
                output_path=str(output_path),
                config=img_config
            )

            if img_result.success:
                result.assets.append(ProductionAsset(
                    asset_type="image",
                    path=str(output_path),
                    scene_number=scene.scene_number,
                    success=True,
                    metadata={
                        "prompt": scene.image_prompt,
                        "backend": img_result.backend_used
                    }
                ))
            else:
                error_msg = img_result.error or "Unknown image generation error"
                result.errors.append(f"Image for scene {scene.scene_number}: {error_msg}")
                result.assets.append(ProductionAsset(
                    asset_type="image",
                    path=str(output_path),
                    scene_number=scene.scene_number,
                    success=False,
                    error=error_msg
                ))
                if not continue_on_error:
                    result.success = False
                    break

        except Exception as e:
            error_msg = str(e)
            result.errors.append(f"Image for scene {scene.scene_number}: {error_msg}")
            if not continue_on_error:
                result.success = False
                break

    # Check if we have enough successful images
    successful_images = [a for a in result.assets if a.success]
    if len(successful_images) == 0 and len(scenes) > 0:
        result.success = False
        result.errors.append("No images were generated successfully")

    result.duration_seconds = (datetime.now() - start_time).total_seconds()
    return result


# === Video Composition ===

def compose_video_assets(
    image_assets: List[ProductionAsset],
    audio_assets: List[ProductionAsset],
    output_dir: Path,
    config: Dict[str, Any],
    progress_callback: Optional[Callable] = None
) -> StageResult:
    """
    Compose video from images and audio.

    Args:
        image_assets: List of image assets
        audio_assets: List of audio assets
        output_dir: Directory for output
        config: Configuration options
        progress_callback: Optional progress callback

    Returns:
        StageResult with video asset
    """
    try:
        from video_compose import compose_video, VideoConfig
    except ImportError:
        return StageResult(
            stage=ProductionStage.COMPOSE_VIDEO,
            success=False,
            errors=["video_compose skill not available"]
        )

    start_time = datetime.now()
    result = StageResult(
        stage=ProductionStage.COMPOSE_VIDEO,
        success=True
    )

    if progress_callback:
        progress_callback({
            "stage": "compose_video",
            "step": 1,
            "total": 1,
            "message": "Composing video from assets"
        })

    # Get successful images sorted by scene number
    images = sorted(
        [a for a in image_assets if a.success],
        key=lambda a: a.scene_number or 0
    )

    if not images:
        result.success = False
        result.errors.append("No images available for video composition")
        return result

    # Get audio file paths
    audio_files = [a.path for a in audio_assets if a.success]

    # Calculate duration
    max_duration = config.get("max_duration_seconds", 600)
    duration_per_scene = config.get("duration_per_scene", 5.0)
    total_duration = min(len(images) * duration_per_scene, max_duration)

    if len(images) * duration_per_scene > max_duration:
        result.warnings.append(
            f"Video duration limited to {max_duration}s (would be {len(images) * duration_per_scene}s)"
        )

    output_path = output_dir / "episode_raw.mp4"

    try:
        video_config = VideoConfig(
            width=config.get("video_width", 1920),
            height=config.get("video_height", 1080),
            fps=config.get("video_fps", 30),
            duration_per_image=duration_per_scene,
            codec="h264"
        )

        # If we have audio, use the first one as background
        # (In a real implementation, we'd stitch all audio together)
        audio_path = audio_files[0] if audio_files else None

        video_result = compose_video(
            images=[a.path for a in images],
            video_config=video_config,
            config={"audio_path": audio_path} if audio_path else {},
            progress_callback=progress_callback
        )

        if video_result.success:
            # Move output to our path
            if video_result.output_path and Path(video_result.output_path).exists():
                shutil.move(video_result.output_path, str(output_path))

            result.assets.append(ProductionAsset(
                asset_type="video",
                path=str(output_path),
                success=True,
                metadata={
                    "duration": total_duration,
                    "images_used": len(images),
                    "audio_used": len(audio_files)
                }
            ))
        else:
            error_msg = video_result.error or "Video composition failed"
            result.success = False
            result.errors.append(error_msg)

    except Exception as e:
        result.success = False
        result.errors.append(f"Video composition error: {str(e)}")

    result.duration_seconds = (datetime.now() - start_time).total_seconds()
    return result


# === Subtitle Addition ===

def add_subtitles(
    video_path: Path,
    dialogue_lines: List[DialogueLine],
    output_path: Path,
    config: Dict[str, Any],
    progress_callback: Optional[Callable] = None
) -> StageResult:
    """
    Add subtitles to video.

    Args:
        video_path: Path to input video
        dialogue_lines: Dialogue to use for subtitles
        output_path: Path for output video
        config: Configuration options
        progress_callback: Optional progress callback

    Returns:
        StageResult with subtitled video
    """
    try:
        from video_subtitle import add_subtitles_to_video, SubtitleStyle
    except ImportError:
        return StageResult(
            stage=ProductionStage.ADD_SUBTITLES,
            success=False,
            errors=["video_subtitle skill not available"]
        )

    start_time = datetime.now()
    result = StageResult(
        stage=ProductionStage.ADD_SUBTITLES,
        success=True
    )

    if progress_callback:
        progress_callback({
            "stage": "add_subtitles",
            "step": 1,
            "total": 1,
            "message": "Adding subtitles to video"
        })

    if not video_path.exists():
        result.success = False
        result.errors.append("Input video not found")
        return result

    # Generate subtitle texts from dialogue
    subtitle_texts = []
    for line in dialogue_lines:
        # Format: CHARACTER: Text
        formatted = f"{line.character.upper()}: {line.text}"
        subtitle_texts.append(formatted)

    if not subtitle_texts:
        result.warnings.append("No dialogue for subtitles, skipping")
        # Just copy the video
        shutil.copy(str(video_path), str(output_path))
        result.assets.append(ProductionAsset(
            asset_type="video",
            path=str(output_path),
            success=True
        ))
        return result

    try:
        style_config = config.get("subtitle_style", {})
        style = SubtitleStyle(
            font_size=style_config.get("font_size", 24),
            font_color=style_config.get("font_color", "white"),
            outline_color=style_config.get("outline_color", "black"),
            outline_width=style_config.get("outline_width", 2),
            position=style_config.get("position", "bottom")
        )

        sub_result = add_subtitles_to_video(
            video_path=str(video_path),
            texts=subtitle_texts,
            output_path=str(output_path),
            style=style,
            mode="burn_in"
        )

        if sub_result.success:
            result.assets.append(ProductionAsset(
                asset_type="video",
                path=str(output_path),
                success=True,
                metadata={"subtitle_count": len(subtitle_texts)}
            ))
        else:
            error_msg = sub_result.error or "Subtitle addition failed"
            result.success = False
            result.errors.append(error_msg)

    except Exception as e:
        result.success = False
        result.errors.append(f"Subtitle error: {str(e)}")

    result.duration_seconds = (datetime.now() - start_time).total_seconds()
    return result


# === Main Production Pipeline ===

def produce_episode(
    script_path: Optional[str] = None,
    script_content: Optional[str] = None,
    output_path: str = None,
    config: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable] = None
) -> ProductionResult:
    """
    Produce a full episode from a script.

    Args:
        script_path: Path to script file
        script_content: Script content (alternative to path)
        output_path: Path for final video
        config: Production configuration
        progress_callback: Progress callback function

    Returns:
        ProductionResult with all stage results
    """
    config = {**DEFAULT_CONFIG, **(config or {})}
    result = ProductionResult(success=True)

    # Create temp directory for intermediate files
    temp_dir = Path(tempfile.mkdtemp(prefix="episode_"))
    cleanup_on_failure = config.get("cleanup_on_failure", True)

    try:
        # Stage 1: Parse script
        if progress_callback:
            progress_callback({
                "stage": "parse_script",
                "step": 1,
                "total": 1,
                "message": "Parsing script"
            })

        if script_path:
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()

        if not script_content:
            result.success = False
            result.errors.append("No script content provided")
            return result

        scenes, dialogue_lines = parse_script(script_content)
        scenes = generate_image_prompts(scenes, config.get("image_style", "cinematic"))

        result.scenes_count = len(scenes)
        result.stages.append(StageResult(
            stage=ProductionStage.PARSE_SCRIPT,
            success=True,
            warnings=[f"Parsed {len(scenes)} scenes, {len(dialogue_lines)} dialogue lines"]
        ))

        if not scenes and not dialogue_lines:
            result.success = False
            result.errors.append("No scenes or dialogue found in script")
            return result

        # Stage 2: Generate audio
        audio_result = generate_audio_assets(
            dialogue_lines, temp_dir, config, progress_callback
        )
        result.stages.append(audio_result)
        result.audio_files = len([a for a in audio_result.assets if a.success])
        result.errors.extend(audio_result.errors)
        result.warnings.extend(audio_result.warnings)

        if not audio_result.success and not config.get("continue_on_error"):
            result.success = False
            return result

        # Stage 3: Generate images
        image_result = generate_image_assets(
            scenes, temp_dir, config, progress_callback
        )
        result.stages.append(image_result)
        result.image_files = len([a for a in image_result.assets if a.success])
        result.errors.extend(image_result.errors)
        result.warnings.extend(image_result.warnings)

        if not image_result.success and not config.get("continue_on_error"):
            result.success = False
            return result

        # Stage 4: Compose video
        video_result = compose_video_assets(
            image_result.assets, audio_result.assets,
            temp_dir, config, progress_callback
        )
        result.stages.append(video_result)
        result.errors.extend(video_result.errors)
        result.warnings.extend(video_result.warnings)

        if not video_result.success:
            result.success = False
            return result

        raw_video_path = temp_dir / "episode_raw.mp4"

        # Stage 5: Add subtitles (if enabled)
        if config.get("generate_subtitles", True) and raw_video_path.exists():
            final_video_path = temp_dir / "episode_final.mp4"

            subtitle_result = add_subtitles(
                raw_video_path, dialogue_lines, final_video_path,
                config, progress_callback
            )
            result.stages.append(subtitle_result)
            result.errors.extend(subtitle_result.errors)
            result.warnings.extend(subtitle_result.warnings)

            if subtitle_result.success:
                raw_video_path = final_video_path

        # Stage 6: Finalize - move to output
        if output_path and raw_video_path.exists():
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(raw_video_path), output_path)
            result.output_path = output_path
        elif raw_video_path.exists():
            result.output_path = str(raw_video_path)

        # Collect all asset paths
        result.assets = {
            "audio": [a.path for a in audio_result.assets if a.success],
            "images": [a.path for a in image_result.assets if a.success],
            "video": [result.output_path] if result.output_path else []
        }

        # Calculate total duration
        for stage in result.stages:
            result.total_duration_seconds += stage.duration_seconds

        result.success = result.output_path is not None

    except Exception as e:
        result.success = False
        result.errors.append(f"Production error: {str(e)}")

        if cleanup_on_failure and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    return result


# === Main Entry Point ===

def run(
    args: Dict[str, Any],
    tools: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for the episode_produce skill.

    Args:
        script_path: Path to script file
        script_content: Script content (alternative to path)
        output_path: Where to save the final video
        config: Override default configuration

    Returns:
        {
            "success": bool,
            "output_path": str,
            "stages": List of stage results,
            "scenes_count": int,
            "audio_files": int,
            "image_files": int,
            "errors": List[str],
            "warnings": List[str]
        }
    """
    script_path = args.get("script_path")
    script_content = args.get("script_content")
    output_path = args.get("output_path")
    config = args.get("config", {})

    # Validation
    if not script_path and not script_content:
        return {
            "success": False,
            "error": "Either script_path or script_content is required"
        }

    if script_path and not Path(script_path).exists():
        return {
            "success": False,
            "error": f"Script file not found: {script_path}"
        }

    # Progress callback
    def progress_callback(update):
        if "progress_callback" in context:
            context["progress_callback"](update)

    # Run production
    result = produce_episode(
        script_path=script_path,
        script_content=script_content,
        output_path=output_path,
        config=config,
        progress_callback=progress_callback
    )

    return result.to_dict()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Produce episode from script")
    parser.add_argument("--script", required=True, help="Path to script file")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--style", default="cinematic", help="Visual style")
    parser.add_argument("--no-subtitles", action="store_true", help="Skip subtitles")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    config = {
        "image_style": args.style,
        "generate_subtitles": not args.no_subtitles
    }

    result = produce_episode(
        script_path=args.script,
        output_path=args.output,
        config=config,
        progress_callback=lambda u: print(f"  {u.get('stage')}: {u.get('message')}")
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\nProduction Complete:")
        print(f"  Success: {result.success}")
        print(f"  Output: {result.output_path}")
        print(f"  Scenes: {result.scenes_count}")
        print(f"  Audio files: {result.audio_files}")
        print(f"  Image files: {result.image_files}")
        print(f"  Duration: {result.total_duration_seconds:.1f}s")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for e in result.errors[:5]:
                print(f"  - {e}")

        if result.warnings:
            print(f"\nWarnings ({len(result.warnings)}):")
            for w in result.warnings[:5]:
                print(f"  - {w}")

    sys.exit(0 if result.success else 1)
