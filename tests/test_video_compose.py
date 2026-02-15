"""
Tests for video_compose skill.

Tests cover:
- FFmpeg pre-checks
- Image collection and validation
- Resource limit enforcement
- Video composition (mocked ffmpeg)
- Audio integration
- Progress callbacks
- Edge cases
"""

import pytest
import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add skills to path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "video"))

from video_compose import (
    run,
    check_ffmpeg,
    collect_images,
    validate_images,
    compose_video,
    get_media_duration,
    _compare_versions,
    VideoConfig,
    VideoCodec,
    QualityPreset,
    CompositionResult,
    DEFAULT_CONFIG,
    MAX_IMAGES,
    MAX_DURATION_SECONDS,
    SKILL_META,
)


class TestSkillMetadata:
    """Test skill metadata is properly defined."""

    def test_has_required_fields(self):
        assert "name" in SKILL_META
        assert "description" in SKILL_META
        assert "tier" in SKILL_META
        assert "version" in SKILL_META

    def test_name_matches(self):
        assert SKILL_META["name"] == "video_compose"

    def test_has_ffmpeg_dependency(self):
        assert "ffmpeg" in SKILL_META["dependencies"]


class TestVersionComparison:
    """Test version comparison utility."""

    def test_equal_versions(self):
        assert _compare_versions("4.0.0", "4.0.0") == 0
        assert _compare_versions("4.4", "4.4") == 0

    def test_greater_version(self):
        assert _compare_versions("5.0.0", "4.0.0") == 1
        assert _compare_versions("4.1.0", "4.0.0") == 1
        assert _compare_versions("4.0.1", "4.0.0") == 1

    def test_lesser_version(self):
        assert _compare_versions("3.0.0", "4.0.0") == -1
        assert _compare_versions("4.0.0", "4.1.0") == -1

    def test_different_lengths(self):
        assert _compare_versions("4.0", "4.0.0") == 0
        assert _compare_versions("4.1", "4.0.0") == 1


class TestFFmpegCheck:
    """Test ffmpeg availability checks."""

    @patch('shutil.which')
    def test_ffmpeg_not_found(self, mock_which):
        mock_which.return_value = None
        ok, version, error = check_ffmpeg(DEFAULT_CONFIG)
        assert ok is False
        assert "not found" in error.lower()

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_ffmpeg_found(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ffmpeg version 4.4.2 Copyright (c) 2000-2021"
        )

        ok, version, error = check_ffmpeg(DEFAULT_CONFIG)
        assert ok is True
        assert version == "4.4.2"
        assert error is None

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_ffmpeg_version_too_old(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ffmpeg version 3.0.0 Copyright (c) 2000-2016"
        )

        config = {**DEFAULT_CONFIG, "min_ffmpeg_version": "4.0.0"}
        ok, version, error = check_ffmpeg(config)
        assert ok is False
        assert "below minimum" in error.lower()

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_ffmpeg_n_version_format(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ffmpeg version n4.4.2 Copyright (c) 2000-2021"
        )

        ok, version, error = check_ffmpeg(DEFAULT_CONFIG)
        assert ok is True
        assert version == "4.4.2"


class TestImageCollection:
    """Test image collection functionality."""

    def test_collect_from_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake images
            paths = []
            for i in range(5):
                path = Path(tmpdir) / f"img_{i}.png"
                path.write_bytes(b"fake")
                paths.append(str(path))

            collected = collect_images(paths)
            assert len(collected) == 5

    def test_collect_from_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake images
            for i in range(3):
                (Path(tmpdir) / f"img_{i}.png").write_bytes(b"fake")
                (Path(tmpdir) / f"img_{i}.jpg").write_bytes(b"fake")

            collected = collect_images(tmpdir)
            assert len(collected) == 6

    def test_collect_filters_non_images(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "img.png").write_bytes(b"fake")
            (Path(tmpdir) / "doc.txt").write_bytes(b"text")
            (Path(tmpdir) / "data.json").write_bytes(b"{}")

            collected = collect_images(tmpdir)
            assert len(collected) == 1
            assert "img.png" in collected[0]

    def test_collect_nonexistent_directory(self):
        collected = collect_images("/nonexistent/path")
        assert collected == []

    def test_collect_with_custom_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "img.png").write_bytes(b"fake")
            (Path(tmpdir) / "img.webp").write_bytes(b"fake")

            collected = collect_images(tmpdir, extensions=[".png"])
            assert len(collected) == 1


class TestImageValidation:
    """Test image validation."""

    def test_validate_within_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = []
            for i in range(10):
                path = Path(tmpdir) / f"img_{i}.png"
                path.write_bytes(b"fake")
                paths.append(str(path))

            valid, warnings = validate_images(paths, max_count=100)
            assert len(valid) == 10
            assert len(warnings) == 0

    def test_validate_exceeds_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = []
            for i in range(20):
                path = Path(tmpdir) / f"img_{i}.png"
                path.write_bytes(b"fake")
                paths.append(str(path))

            valid, warnings = validate_images(paths, max_count=10)
            assert len(valid) == 10
            assert any("truncating" in w.lower() for w in warnings)

    def test_validate_missing_files(self):
        paths = ["/nonexistent/img1.png", "/nonexistent/img2.png"]
        valid, warnings = validate_images(paths)
        assert len(valid) == 0
        assert len(warnings) == 2


class TestVideoConfig:
    """Test VideoConfig dataclass."""

    def test_default_values(self):
        config = VideoConfig(output_path="out.mp4")
        assert config.width == 1920
        assert config.height == 1080
        assert config.fps == 30.0
        assert config.codec == VideoCodec.H264
        assert config.quality == QualityPreset.MEDIUM

    def test_custom_values(self):
        config = VideoConfig(
            output_path="out.mp4",
            width=1280,
            height=720,
            fps=24.0,
            codec=VideoCodec.VP9,
            quality=QualityPreset.HIGH
        )
        assert config.width == 1280
        assert config.codec == VideoCodec.VP9


class TestCompositionResult:
    """Test CompositionResult dataclass."""

    def test_success_result(self):
        result = CompositionResult(
            success=True,
            output_path="/path/to/video.mp4",
            duration_seconds=30.0,
            file_size_bytes=1024000,
            images_used=10
        )
        assert result.success is True
        assert result.images_used == 10

    def test_to_dict(self):
        result = CompositionResult(
            success=True,
            output_path="/path/to/video.mp4",
            duration_seconds=30.0,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["output_path"] == "/path/to/video.mp4"


class TestComposeVideo:
    """Test video composition with mocked ffmpeg."""

    @patch('video_compose.check_ffmpeg')
    @patch('subprocess.run')
    def test_compose_success(self, mock_run, mock_check):
        mock_check.return_value = (True, "4.4.2", None)
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create images
            images = []
            for i in range(3):
                path = Path(tmpdir) / f"img_{i}.png"
                path.write_bytes(b"fake image")
                images.append(str(path))

            # Create output path and fake it exists after ffmpeg
            output = Path(tmpdir) / "output.mp4"

            # Mock output file creation
            def side_effect(*args, **kwargs):
                output.write_bytes(b"fake video data")
                return MagicMock(returncode=0, stderr="")

            mock_run.side_effect = side_effect

            config = VideoConfig(output_path=str(output))
            result = compose_video(images, config, DEFAULT_CONFIG)

            assert result.success is True
            assert result.images_used == 3

    @patch('video_compose.check_ffmpeg')
    def test_compose_ffmpeg_not_available(self, mock_check):
        mock_check.return_value = (False, "", "ffmpeg not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a real image so we pass the image validation
            path = Path(tmpdir) / "img.png"
            path.write_bytes(b"fake")

            config = VideoConfig(output_path=str(Path(tmpdir) / "output.mp4"))
            result = compose_video([str(path)], config, DEFAULT_CONFIG)

            assert result.success is False
            assert "ffmpeg" in result.error.lower()

    def test_compose_no_images(self):
        config = VideoConfig(output_path="/fake/output.mp4")
        result = compose_video([], config, DEFAULT_CONFIG)

        assert result.success is False
        assert "no valid images" in result.error.lower()

    @patch('video_compose.check_ffmpeg')
    @patch('subprocess.run')
    def test_compose_duration_limit(self, mock_run, mock_check):
        mock_check.return_value = (True, "4.4.2", None)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many images that would exceed duration
            images = []
            for i in range(100):
                path = Path(tmpdir) / f"img_{i}.png"
                path.write_bytes(b"fake")
                images.append(str(path))

            output = Path(tmpdir) / "output.mp4"

            def side_effect(*args, **kwargs):
                output.write_bytes(b"fake video")
                return MagicMock(returncode=0, stderr="")

            mock_run.side_effect = side_effect

            # 100 images * 10s = 1000s > 600s limit
            config = VideoConfig(
                output_path=str(output),
                duration_per_image=10.0
            )
            result = compose_video(images, config, DEFAULT_CONFIG)

            # Should succeed but with adjusted duration
            assert result.success is True
            assert any("adjusted" in w.lower() for w in result.warnings)


class TestRunFunction:
    """Test the main run() function."""

    @patch('video_compose.check_ffmpeg')
    def test_run_check_ffmpeg_only(self, mock_check):
        mock_check.return_value = (True, "4.4.2", None)

        result = run({"check_ffmpeg_only": True}, {}, {})
        assert result["ffmpeg_available"] is True
        assert result["ffmpeg_version"] == "4.4.2"

    def test_run_missing_images(self):
        result = run({"output_path": "out.mp4"}, {}, {})
        assert result["success"] is False
        assert "images" in result["error"].lower()

    def test_run_missing_output_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a real image
            path = Path(tmpdir) / "img.png"
            path.write_bytes(b"fake")

            result = run({"images": [str(path)]}, {}, {})
            assert result["success"] is False
            assert "output_path" in result["error"].lower()

    @patch('video_compose.check_ffmpeg')
    @patch('subprocess.run')
    def test_run_full_composition(self, mock_run, mock_check):
        mock_check.return_value = (True, "4.4.2", None)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create images
            images = []
            for i in range(3):
                path = Path(tmpdir) / f"img_{i}.png"
                path.write_bytes(b"fake")
                images.append(str(path))

            output = Path(tmpdir) / "output.mp4"

            def side_effect(*args, **kwargs):
                output.write_bytes(b"fake video")
                return MagicMock(returncode=0, stderr="")

            mock_run.side_effect = side_effect

            result = run(
                {
                    "images": images,
                    "output_path": str(output),
                    "width": 1280,
                    "height": 720,
                    "codec": "h264",
                    "quality": "medium",
                },
                {},
                {}
            )

            assert result["success"] is True
            assert result["images_used"] == 3

    @patch('video_compose.check_ffmpeg')
    @patch('subprocess.run')
    def test_run_with_audio(self, mock_run, mock_check):
        mock_check.return_value = (True, "4.4.2", None)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create images
            images = []
            for i in range(2):
                path = Path(tmpdir) / f"img_{i}.png"
                path.write_bytes(b"fake")
                images.append(str(path))

            # Create fake audio
            audio = Path(tmpdir) / "audio.mp3"
            audio.write_bytes(b"fake audio")

            output = Path(tmpdir) / "output.mp4"

            def side_effect(*args, **kwargs):
                output.write_bytes(b"fake video")
                return MagicMock(returncode=0, stderr="")

            mock_run.side_effect = side_effect

            result = run(
                {
                    "images": images,
                    "output_path": str(output),
                    "audio_path": str(audio),
                    "audio_volume": 0.8,
                },
                {},
                {}
            )

            assert result["success"] is True


class TestCodecAndQuality:
    """Test codec and quality enums."""

    def test_all_codecs(self):
        assert VideoCodec.H264.value == "libx264"
        assert VideoCodec.H265.value == "libx265"
        assert VideoCodec.VP9.value == "libvpx-vp9"

    def test_all_quality_presets(self):
        assert QualityPreset.LOW.value == "low"
        assert QualityPreset.MEDIUM.value == "medium"
        assert QualityPreset.HIGH.value == "high"
        assert QualityPreset.LOSSLESS.value == "lossless"


class TestResourceLimits:
    """Test resource limit constants."""

    def test_max_images(self):
        assert MAX_IMAGES == 500

    def test_max_duration(self):
        assert MAX_DURATION_SECONDS == 600  # 10 minutes


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_image_list(self):
        collected = collect_images([])
        assert collected == []

    @patch('video_compose.check_ffmpeg')
    @patch('subprocess.run')
    def test_ffmpeg_timeout(self, mock_run, mock_check):
        import subprocess
        mock_check.return_value = (True, "4.4.2", None)
        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 60)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "img.png"
            path.write_bytes(b"fake")

            config = VideoConfig(output_path=str(Path(tmpdir) / "out.mp4"))
            result = compose_video([str(path)], config, DEFAULT_CONFIG)

            assert result.success is False
            assert "timed out" in result.error.lower()

    @patch('video_compose.check_ffmpeg')
    @patch('subprocess.run')
    def test_progress_callback(self, mock_run, mock_check):
        mock_check.return_value = (True, "4.4.2", None)
        callbacks = []

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "img.png"
            path.write_bytes(b"fake")

            output = Path(tmpdir) / "output.mp4"

            def side_effect(*args, **kwargs):
                output.write_bytes(b"fake")
                return MagicMock(returncode=0, stderr="")

            mock_run.side_effect = side_effect

            config = VideoConfig(output_path=str(output))
            compose_video([str(path)], config, DEFAULT_CONFIG, callbacks.append)

            assert len(callbacks) >= 2  # preparing + encoding/completed
            assert callbacks[0]["stage"] == "preparing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
