"""
Tests for video_subtitle skill.

Tests cover:
- SRT parsing
- VTT parsing
- Subtitle generation from text
- Format detection
- Subtitle writing
- FFmpeg integration (mocked)
- Style building
- Edge cases
"""

import pytest
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add skills to path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "video"))

from video_subtitle import (
    run,
    parse_srt,
    parse_vtt,
    parse_srt_time,
    parse_subtitles,
    detect_format,
    generate_subtitles_from_text,
    write_srt,
    write_vtt,
    build_subtitle_filter,
    add_subtitles,
    check_ffmpeg,
    SubtitleEntry,
    SubtitleFormat,
    SubtitleMode,
    SubtitlePosition,
    SubtitleStyle,
    SubtitleResult,
    DEFAULT_CONFIG,
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
        assert SKILL_META["name"] == "video_subtitle"

    def test_has_ffmpeg_dependency(self):
        assert "ffmpeg" in SKILL_META["dependencies"]


class TestSRTTimeParsing:
    """Test SRT time format parsing."""

    def test_parse_basic_time(self):
        time = parse_srt_time("00:00:05,000")
        assert time == 5.0

    def test_parse_with_hours(self):
        time = parse_srt_time("01:30:45,500")
        assert time == 5445.5

    def test_parse_with_milliseconds(self):
        time = parse_srt_time("00:00:01,234")
        assert abs(time - 1.234) < 0.001

    def test_parse_vtt_format(self):
        # VTT uses period instead of comma
        time = parse_srt_time("00:00:05.000")
        assert time == 5.0

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_srt_time("invalid")


class TestSRTParsing:
    """Test SRT subtitle parsing."""

    def test_parse_basic_srt(self):
        srt = """1
00:00:00,000 --> 00:00:03,000
Hello World

2
00:00:03,500 --> 00:00:06,000
This is a test"""

        entries = parse_srt(srt)
        assert len(entries) == 2
        assert entries[0].text == "Hello World"
        assert entries[1].start_time == 3.5

    def test_parse_multiline_text(self):
        srt = """1
00:00:00,000 --> 00:00:05,000
Line one
Line two"""

        entries = parse_srt(srt)
        assert len(entries) == 1
        assert "Line one\nLine two" == entries[0].text

    def test_parse_empty(self):
        entries = parse_srt("")
        assert len(entries) == 0

    def test_parse_malformed(self):
        srt = """not valid
something else"""
        entries = parse_srt(srt)
        assert len(entries) == 0


class TestVTTParsing:
    """Test VTT subtitle parsing."""

    def test_parse_basic_vtt(self):
        vtt = """WEBVTT

00:00:00.000 --> 00:00:03.000
Hello World

00:00:03.500 --> 00:00:06.000
This is a test"""

        entries = parse_vtt(vtt)
        assert len(entries) == 2
        assert entries[0].text == "Hello World"

    def test_parse_vtt_with_header_metadata(self):
        vtt = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:03.000
Hello"""

        entries = parse_vtt(vtt)
        assert len(entries) == 1

    def test_parse_vtt_with_cue_ids(self):
        vtt = """WEBVTT

cue-1
00:00:00.000 --> 00:00:03.000
Hello"""

        entries = parse_vtt(vtt)
        assert len(entries) == 1


class TestFormatDetection:
    """Test subtitle format detection."""

    def test_detect_srt_by_extension(self):
        fmt = detect_format("subtitles.srt", "")
        assert fmt == SubtitleFormat.SRT

    def test_detect_vtt_by_extension(self):
        fmt = detect_format("subtitles.vtt", "")
        assert fmt == SubtitleFormat.VTT

    def test_detect_vtt_by_content(self):
        fmt = detect_format("subtitles.txt", "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello")
        assert fmt == SubtitleFormat.VTT

    def test_default_to_srt(self):
        fmt = detect_format("subtitles.txt", "1\n00:00:00,000 --> 00:00:01,000\nHello")
        assert fmt == SubtitleFormat.SRT


class TestSubtitleEntry:
    """Test SubtitleEntry dataclass."""

    def test_to_srt_time(self):
        entry = SubtitleEntry(index=1, start_time=0, end_time=5.5, text="Test")
        time_str = entry.to_srt_time(65.123)
        assert time_str == "00:01:05,123"

    def test_to_vtt_time(self):
        entry = SubtitleEntry(index=1, start_time=0, end_time=5.5, text="Test")
        time_str = entry.to_vtt_time(65.123)
        assert time_str == "00:01:05.123"

    def test_to_srt(self):
        entry = SubtitleEntry(index=1, start_time=0, end_time=3, text="Hello")
        srt = entry.to_srt()
        assert "1\n" in srt
        assert "00:00:00,000 --> 00:00:03,000" in srt
        assert "Hello" in srt

    def test_to_vtt(self):
        entry = SubtitleEntry(index=1, start_time=0, end_time=3, text="Hello")
        vtt = entry.to_vtt()
        assert "00:00:00.000 --> 00:00:03.000" in vtt
        assert "Hello" in vtt


class TestSubtitleGeneration:
    """Test subtitle generation from text."""

    def test_generate_basic(self):
        texts = ["First", "Second", "Third"]
        entries = generate_subtitles_from_text(texts)

        assert len(entries) == 3
        assert entries[0].text == "First"
        assert entries[0].start_time == 0.0
        assert entries[0].end_time == 4.0  # default duration

    def test_generate_with_custom_timing(self):
        texts = ["A", "B"]
        entries = generate_subtitles_from_text(
            texts,
            start_time=10.0,
            duration_per_subtitle=2.0,
            gap=1.0
        )

        assert entries[0].start_time == 10.0
        assert entries[0].end_time == 12.0
        assert entries[1].start_time == 13.0  # 12 + 1 gap
        assert entries[1].end_time == 15.0

    def test_generate_sequential_indices(self):
        texts = ["A", "B", "C"]
        entries = generate_subtitles_from_text(texts)
        assert [e.index for e in entries] == [1, 2, 3]


class TestSubtitleWriting:
    """Test writing subtitle files."""

    def test_write_srt(self):
        entries = [
            SubtitleEntry(index=1, start_time=0, end_time=3, text="Hello"),
            SubtitleEntry(index=2, start_time=4, end_time=7, text="World"),
        ]

        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w") as f:
            path = f.name

        write_srt(entries, path)
        content = Path(path).read_text()

        assert "1\n" in content
        assert "00:00:00,000 --> 00:00:03,000" in content
        assert "Hello" in content
        Path(path).unlink()

    def test_write_vtt(self):
        entries = [
            SubtitleEntry(index=1, start_time=0, end_time=3, text="Hello"),
        ]

        with tempfile.NamedTemporaryFile(suffix=".vtt", delete=False, mode="w") as f:
            path = f.name

        write_vtt(entries, path)
        content = Path(path).read_text()

        assert "WEBVTT" in content
        assert "00:00:00.000 --> 00:00:03.000" in content
        Path(path).unlink()


class TestSubtitleStyle:
    """Test SubtitleStyle dataclass."""

    def test_default_style(self):
        style = SubtitleStyle()
        assert style.font_name == "Arial"
        assert style.font_size == 24
        assert style.primary_color == "white"
        assert style.position == SubtitlePosition.BOTTOM

    def test_custom_style(self):
        style = SubtitleStyle(
            font_name="Helvetica",
            font_size=32,
            primary_color="yellow",
            position=SubtitlePosition.TOP,
            bold=True
        )
        assert style.font_name == "Helvetica"
        assert style.bold is True


class TestSubtitleFilter:
    """Test ffmpeg subtitle filter building."""

    def test_build_basic_filter(self):
        style = SubtitleStyle()
        filter_str = build_subtitle_filter(style, "/path/to/subs.srt")

        assert "subtitles=" in filter_str
        assert "FontName=Arial" in filter_str
        assert "FontSize=24" in filter_str

    def test_build_filter_with_colors(self):
        style = SubtitleStyle(primary_color="yellow", outline_color="black")
        filter_str = build_subtitle_filter(style, "subs.srt")

        assert "PrimaryColour" in filter_str
        assert "OutlineColour" in filter_str

    def test_build_filter_with_bold(self):
        style = SubtitleStyle(bold=True, italic=True)
        filter_str = build_subtitle_filter(style, "subs.srt")

        assert "Bold=1" in filter_str
        assert "Italic=1" in filter_str


class TestFFmpegCheck:
    """Test ffmpeg availability check."""

    @patch('shutil.which')
    def test_ffmpeg_not_found(self, mock_which):
        mock_which.return_value = None
        ok, error = check_ffmpeg(DEFAULT_CONFIG)
        assert ok is False
        assert "not found" in error.lower()

    @patch('shutil.which')
    def test_ffmpeg_found(self, mock_which):
        mock_which.return_value = "/usr/bin/ffmpeg"
        ok, error = check_ffmpeg(DEFAULT_CONFIG)
        assert ok is True
        assert error == ""


class TestAddSubtitles:
    """Test adding subtitles to video."""

    def test_video_not_found(self):
        result = add_subtitles(
            "/nonexistent/video.mp4",
            "/nonexistent/subs.srt",
            "/output.mp4",
            SubtitleMode.BURN_IN,
            SubtitleStyle(),
            DEFAULT_CONFIG
        )
        assert result.success is False
        assert "not found" in result.error.lower()

    @patch('video_subtitle.check_ffmpeg')
    def test_ffmpeg_not_available(self, mock_check):
        mock_check.return_value = (False, "ffmpeg not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            video = Path(tmpdir) / "video.mp4"
            video.write_bytes(b"fake video")
            subs = Path(tmpdir) / "subs.srt"
            subs.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello")

            result = add_subtitles(
                str(video), str(subs), str(Path(tmpdir) / "out.mp4"),
                SubtitleMode.BURN_IN, SubtitleStyle(), DEFAULT_CONFIG
            )
            assert result.success is False
            assert "ffmpeg" in result.error.lower()

    @patch('video_subtitle.check_ffmpeg')
    @patch('subprocess.run')
    def test_burn_in_success(self, mock_run, mock_check):
        mock_check.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmpdir:
            video = Path(tmpdir) / "video.mp4"
            video.write_bytes(b"fake video")
            subs = Path(tmpdir) / "subs.srt"
            subs.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello")
            output = Path(tmpdir) / "out.mp4"

            def side_effect(*args, **kwargs):
                output.write_bytes(b"fake output")
                return MagicMock(returncode=0, stderr="")

            mock_run.side_effect = side_effect

            result = add_subtitles(
                str(video), str(subs), str(output),
                SubtitleMode.BURN_IN, SubtitleStyle(), DEFAULT_CONFIG
            )
            assert result.success is True
            assert result.subtitle_count == 1


class TestRunFunction:
    """Test the main run() function."""

    def test_missing_video_path(self):
        result = run({"output_path": "out.mp4"}, {}, {})
        assert result["success"] is False
        assert "video_path" in result["error"].lower()

    def test_missing_output_path(self):
        result = run({"video_path": "in.mp4"}, {}, {})
        assert result["success"] is False
        assert "output_path" in result["error"].lower()

    def test_missing_subtitle_source(self):
        result = run({
            "video_path": "in.mp4",
            "output_path": "out.mp4"
        }, {}, {})
        assert result["success"] is False
        assert "subtitle" in result["error"].lower() or "texts" in result["error"].lower()

    @patch('video_subtitle.check_ffmpeg')
    @patch('subprocess.run')
    def test_run_with_subtitle_file(self, mock_run, mock_check):
        mock_check.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmpdir:
            video = Path(tmpdir) / "video.mp4"
            video.write_bytes(b"fake video")
            subs = Path(tmpdir) / "subs.srt"
            subs.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello")
            output = Path(tmpdir) / "out.mp4"

            def side_effect(*args, **kwargs):
                output.write_bytes(b"fake output")
                return MagicMock(returncode=0, stderr="")

            mock_run.side_effect = side_effect

            result = run({
                "video_path": str(video),
                "subtitle_path": str(subs),
                "output_path": str(output),
            }, {}, {})

            assert result["success"] is True

    @patch('video_subtitle.check_ffmpeg')
    @patch('subprocess.run')
    def test_run_with_texts(self, mock_run, mock_check):
        mock_check.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmpdir:
            video = Path(tmpdir) / "video.mp4"
            video.write_bytes(b"fake video")
            output = Path(tmpdir) / "out.mp4"

            def side_effect(*args, **kwargs):
                output.write_bytes(b"fake output")
                return MagicMock(returncode=0, stderr="")

            mock_run.side_effect = side_effect

            result = run({
                "video_path": str(video),
                "output_path": str(output),
                "texts": ["Hello", "World"],
            }, {}, {})

            assert result["success"] is True
            assert result["subtitle_count"] == 2


class TestSubtitleResult:
    """Test SubtitleResult dataclass."""

    def test_success_result(self):
        result = SubtitleResult(
            success=True,
            output_path="/path/to/video.mp4",
            subtitle_count=10
        )
        assert result.success is True
        assert result.subtitle_count == 10

    def test_to_dict(self):
        result = SubtitleResult(success=True, subtitle_count=5)
        d = result.to_dict()
        assert d["success"] is True
        assert d["subtitle_count"] == 5


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_texts_list(self):
        result = run({
            "video_path": "in.mp4",
            "output_path": "out.mp4",
            "texts": []
        }, {}, {})
        assert result["success"] is False

    def test_parse_subtitles_srt(self):
        entries = parse_subtitles(
            "1\n00:00:00,000 --> 00:00:01,000\nHello",
            SubtitleFormat.SRT
        )
        assert len(entries) == 1

    def test_parse_subtitles_vtt(self):
        entries = parse_subtitles(
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello",
            SubtitleFormat.VTT
        )
        assert len(entries) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
