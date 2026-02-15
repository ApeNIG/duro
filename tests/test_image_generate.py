"""
Tests for image_generate skill.

Tests cover:
- Face detection logic
- Prompt enhancement
- Caching mechanism
- Backend selection and fallback
- Batch generation
- Configuration handling
- Edge cases
"""

import pytest
import sys
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add skills to path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "image"))

from image_generate import (
    run,
    detect_face_prompt,
    enhance_prompt,
    get_cache_key,
    get_cached_image,
    save_to_cache,
    generate_image,
    generate_batch,
    Backend,
    ImageFormat,
    ImageRequest,
    GenerationResult,
    DEFAULT_CONFIG,
    STYLE_MODIFIERS,
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
        assert SKILL_META["name"] == "image_generate"

    def test_requires_network(self):
        assert SKILL_META["requires_network"] is True


class TestFaceDetection:
    """Test face detection logic."""

    def test_detects_portrait(self):
        is_face, confidence = detect_face_prompt("A portrait of a woman", DEFAULT_CONFIG)
        assert is_face is True
        assert confidence >= 0.7

    def test_detects_headshot(self):
        is_face, confidence = detect_face_prompt("Professional headshot photo", DEFAULT_CONFIG)
        assert is_face is True

    def test_detects_person(self):
        is_face, confidence = detect_face_prompt("A person walking in the park", DEFAULT_CONFIG)
        assert is_face is True

    def test_no_face_landscape(self):
        is_face, confidence = detect_face_prompt("Mountain landscape at sunset", DEFAULT_CONFIG)
        assert is_face is False
        assert confidence < 0.7

    def test_no_face_abstract(self):
        is_face, confidence = detect_face_prompt("Abstract geometric patterns", DEFAULT_CONFIG)
        assert is_face is False

    def test_multiple_keywords_higher_confidence(self):
        _, conf1 = detect_face_prompt("A face", DEFAULT_CONFIG)
        _, conf2 = detect_face_prompt("A portrait face photo of a person", DEFAULT_CONFIG)
        assert conf2 > conf1

    def test_custom_threshold(self):
        config = {**DEFAULT_CONFIG, "face_confidence_threshold": 0.9}
        is_face, _ = detect_face_prompt("A person", config)
        # Single keyword might not reach 0.9
        assert is_face is False


class TestPromptEnhancement:
    """Test prompt enhancement logic."""

    def test_adds_quality_terms(self):
        enhanced = enhance_prompt("A cat")
        assert "high quality" in enhanced.lower() or "detailed" in enhanced.lower()

    def test_preserves_original_prompt(self):
        enhanced = enhance_prompt("A beautiful sunset")
        assert "beautiful sunset" in enhanced

    def test_applies_style_modifier(self):
        enhanced = enhance_prompt("A landscape", style="photorealistic")
        assert "photorealistic" in enhanced.lower()

    def test_applies_anime_style(self):
        enhanced = enhance_prompt("A warrior", style="anime")
        assert "anime" in enhanced.lower()

    def test_unknown_style_ignored(self):
        enhanced = enhance_prompt("A cat", style="unknown_style_xyz")
        assert "unknown_style_xyz" not in enhanced

    def test_no_duplicate_quality(self):
        enhanced = enhance_prompt("A high quality detailed photo")
        # Should not add redundant quality terms
        assert enhanced.count("high quality") <= 1


class TestCaching:
    """Test caching mechanism."""

    def test_cache_key_deterministic(self):
        req1 = ImageRequest(prompt="test", output_path="out.png", width=1024, height=1024)
        req2 = ImageRequest(prompt="test", output_path="out.png", width=1024, height=1024)
        assert get_cache_key(req1) == get_cache_key(req2)

    def test_cache_key_varies_by_prompt(self):
        req1 = ImageRequest(prompt="cat", output_path="out.png")
        req2 = ImageRequest(prompt="dog", output_path="out.png")
        assert get_cache_key(req1) != get_cache_key(req2)

    def test_cache_key_varies_by_size(self):
        req1 = ImageRequest(prompt="test", output_path="out.png", width=512)
        req2 = ImageRequest(prompt="test", output_path="out.png", width=1024)
        assert get_cache_key(req1) != get_cache_key(req2)

    def test_get_cached_image_not_found(self):
        req = ImageRequest(prompt="nonexistent", output_path="out.png")
        result = get_cached_image(req, DEFAULT_CONFIG)
        assert result is None

    def test_cache_disabled(self):
        req = ImageRequest(prompt="test", output_path="out.png")
        config = {**DEFAULT_CONFIG, "cache_enabled": False}
        result = get_cached_image(req, config)
        assert result is None

    def test_skip_cache_flag(self):
        req = ImageRequest(prompt="test", output_path="out.png", skip_cache=True)
        result = get_cached_image(req, DEFAULT_CONFIG)
        assert result is None

    def test_save_and_retrieve_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {**DEFAULT_CONFIG, "cache_dir": tmpdir}

            # Create a fake image file
            img_path = Path(tmpdir) / "test_image.png"
            img_path.write_bytes(b"fake image data")

            req = ImageRequest(prompt="cached test", output_path=str(img_path))
            save_to_cache(req, str(img_path), config)

            # Should retrieve it
            cached = get_cached_image(req, config)
            assert cached == str(img_path)


class TestBackendEnum:
    """Test Backend enum."""

    def test_all_backends(self):
        assert Backend.POLLINATIONS.value == "pollinations"
        assert Backend.DALLE.value == "dalle"
        assert Backend.STOCK.value == "stock"


class TestImageRequest:
    """Test ImageRequest dataclass."""

    def test_default_values(self):
        req = ImageRequest(prompt="test", output_path="out.png")
        assert req.width == 1024
        assert req.height == 1024
        assert req.format == ImageFormat.PNG
        assert req.enhance_prompt is True

    def test_custom_values(self):
        req = ImageRequest(
            prompt="test",
            output_path="out.jpg",
            width=512,
            height=768,
            style="anime"
        )
        assert req.width == 512
        assert req.height == 768
        assert req.style == "anime"


class TestGenerationResult:
    """Test GenerationResult dataclass."""

    def test_success_result(self):
        result = GenerationResult(
            success=True,
            path="/path/to/image.png",
            backend_used=Backend.POLLINATIONS,
            prompt="test",
        )
        assert result.success is True
        assert result.cached is False

    def test_to_dict(self):
        result = GenerationResult(
            success=True,
            path="/path/to/image.png",
            backend_used=Backend.POLLINATIONS,
            prompt="test",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["backend_used"] == "pollinations"

    def test_failed_result(self):
        result = GenerationResult(
            success=False,
            error="Network timeout",
            prompt="test",
        )
        assert result.success is False
        assert "timeout" in result.error.lower()


class TestGenerateImage:
    """Test main generation function with mocked backends."""

    def test_uses_pollinations_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.png")

            # Mock the handler to write the file and return success
            def mock_handler(prompt, width, height, out_path, config):
                Path(out_path).write_bytes(b"fake image data")
                return (True, None)

            with patch.dict('image_generate.BACKEND_HANDLERS', {Backend.POLLINATIONS: mock_handler}):
                req = ImageRequest(
                    prompt="A cat",
                    output_path=output_path,
                    backends=[Backend.POLLINATIONS]
                )
                result = generate_image(req, DEFAULT_CONFIG)

                assert result.success is True
                assert result.backend_used == Backend.POLLINATIONS

    def test_fallback_on_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.png")

            def mock_poll_fail(prompt, width, height, out_path, config):
                return (False, "Service unavailable")

            def mock_dalle_success(prompt, width, height, out_path, config):
                Path(out_path).write_bytes(b"fake image data")
                return (True, None)

            handlers = {
                Backend.POLLINATIONS: mock_poll_fail,
                Backend.DALLE: mock_dalle_success,
            }

            with patch.dict('image_generate.BACKEND_HANDLERS', handlers):
                req = ImageRequest(
                    prompt="A cat",
                    output_path=output_path,
                    backends=[Backend.POLLINATIONS, Backend.DALLE]
                )
                config = {**DEFAULT_CONFIG, "max_retries": 0}
                result = generate_image(req, config)

                assert result.success is True
                assert result.backend_used == Backend.DALLE

    def test_all_backends_fail(self):
        def mock_fail(prompt, width, height, out_path, config):
            return (False, "Failed")

        with patch.dict('image_generate.BACKEND_HANDLERS', {Backend.POLLINATIONS: mock_fail}):
            req = ImageRequest(
                prompt="A cat",
                output_path="/tmp/test.png",
                backends=[Backend.POLLINATIONS]
            )
            config = {**DEFAULT_CONFIG, "max_retries": 0}
            result = generate_image(req, config)

            assert result.success is False
            assert "failed" in result.error.lower()

    def test_progress_callback_called(self):
        callbacks = []

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.png")

            def mock_handler(prompt, width, height, out_path, config):
                Path(out_path).write_bytes(b"fake")
                return (True, None)

            with patch.dict('image_generate.BACKEND_HANDLERS', {Backend.POLLINATIONS: mock_handler}):
                req = ImageRequest(
                    prompt="A cat",
                    output_path=output_path,
                    backends=[Backend.POLLINATIONS]
                )
                generate_image(req, DEFAULT_CONFIG, progress_callback=callbacks.append)

                assert len(callbacks) >= 1
                assert callbacks[0]["backend"] == "pollinations"


class TestBatchGeneration:
    """Test batch generation."""

    def test_batch_multiple_images(self):
        callbacks = []

        with tempfile.TemporaryDirectory() as tmpdir:
            def mock_handler(prompt, width, height, out_path, config):
                Path(out_path).write_bytes(b"fake image")
                return (True, None)

            with patch.dict('image_generate.BACKEND_HANDLERS', {Backend.POLLINATIONS: mock_handler}):
                requests = []
                for i in range(3):
                    path = str(Path(tmpdir) / f"test_{i}.png")
                    requests.append(ImageRequest(
                        prompt=f"Image {i}",
                        output_path=path,
                        backends=[Backend.POLLINATIONS]
                    ))

                results = generate_batch(requests, DEFAULT_CONFIG, callbacks.append)

                assert len(results) == 3
                assert all(r.success for r in results)

    def test_batch_partial_failure(self):
        call_count = [0]

        def mock_handler(prompt, width, height, out_path, config):
            call_count[0] += 1
            if call_count[0] == 2:  # Second call fails
                return (False, "Error")
            Path(out_path).write_bytes(b"fake image")
            return (True, None)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict('image_generate.BACKEND_HANDLERS', {Backend.POLLINATIONS: mock_handler}):
                requests = []
                for i in range(3):
                    path = str(Path(tmpdir) / f"test_{i}.png")
                    requests.append(ImageRequest(
                        prompt=f"Image {i}",
                        output_path=path,
                        backends=[Backend.POLLINATIONS]
                    ))

                config = {**DEFAULT_CONFIG, "max_retries": 0}
                results = generate_batch(requests, config)

                success_count = sum(1 for r in results if r.success)
                assert success_count == 2


class TestRunFunction:
    """Test the main run() function."""

    def test_run_single_image(self):
        def mock_handler(prompt, width, height, out_path, config):
            Path(out_path).write_bytes(b"fake image")
            return (True, None)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.png")

            with patch.dict('image_generate.BACKEND_HANDLERS', {Backend.POLLINATIONS: mock_handler}):
                result = run(
                    {
                        "prompt": "A beautiful sunset",
                        "output_path": output_path,
                        "backends": ["pollinations"],
                    },
                    {},
                    {}
                )

                assert result["success"] is True
                assert "result" in result

    def test_run_missing_prompt(self):
        result = run({"output_path": "test.png"}, {}, {})
        assert result["success"] is False
        assert "prompt" in result["error"].lower()

    def test_run_missing_output_path(self):
        result = run({"prompt": "A cat"}, {}, {})
        assert result["success"] is False
        assert "output_path" in result["error"].lower()

    def test_run_batch_mode(self):
        def mock_handler(prompt, width, height, out_path, config):
            Path(out_path).write_bytes(b"fake image")
            return (True, None)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict('image_generate.BACKEND_HANDLERS', {Backend.POLLINATIONS: mock_handler}):
                batch = []
                for i in range(2):
                    path = str(Path(tmpdir) / f"img_{i}.png")
                    batch.append({
                        "prompt": f"Image {i}",
                        "output_path": path
                    })

                result = run(
                    {"batch": batch, "backends": ["pollinations"]},
                    {},
                    {}
                )

                assert result["success"] is True
                assert len(result["results"]) == 2

    def test_run_with_style(self):
        def mock_handler(prompt, width, height, out_path, config):
            Path(out_path).write_bytes(b"fake image")
            return (True, None)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.png")

            with patch.dict('image_generate.BACKEND_HANDLERS', {Backend.POLLINATIONS: mock_handler}):
                result = run(
                    {
                        "prompt": "A warrior",
                        "output_path": output_path,
                        "style": "anime",
                        "backends": ["pollinations"],
                    },
                    {},
                    {}
                )

                assert result["success"] is True


class TestStyleModifiers:
    """Test style modifiers."""

    def test_all_styles_defined(self):
        expected_styles = [
            "photorealistic", "illustration", "anime", "sketch",
            "watercolor", "3d", "cinematic", "minimalist"
        ]
        for style in expected_styles:
            assert style in STYLE_MODIFIERS

    def test_style_modifier_content(self):
        for style, modifier in STYLE_MODIFIERS.items():
            assert len(modifier) > 10  # Reasonable length
            assert style.lower() in modifier.lower() or len(modifier.split(",")) >= 2


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_prompt(self):
        result = run({"prompt": "", "output_path": "test.png"}, {}, {})
        assert result["success"] is False

    def test_invalid_backend(self):
        # Should gracefully ignore invalid backends
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run(
                {
                    "prompt": "test",
                    "output_path": str(Path(tmpdir) / "test.png"),
                    "backends": ["invalid_backend"],
                },
                {},
                {}
            )
            # Will fail because no valid backends, but shouldn't crash
            assert "success" in result

    def test_cache_expiry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                **DEFAULT_CONFIG,
                "cache_dir": tmpdir,
                "cache_expiry_hours": 0  # Immediate expiry
            }

            img_path = Path(tmpdir) / "test.png"
            img_path.write_bytes(b"fake")

            req = ImageRequest(prompt="test", output_path=str(img_path))
            save_to_cache(req, str(img_path), config)

            # Should be expired immediately
            time.sleep(0.1)
            cached = get_cached_image(req, config)
            assert cached is None

    def test_face_override_true(self):
        def mock_handler(prompt, width, height, out_path, config):
            Path(out_path).write_bytes(b"fake image")
            return (True, None)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.png")

            with patch.dict('image_generate.BACKEND_HANDLERS', {Backend.POLLINATIONS: mock_handler}):
                req = ImageRequest(
                    prompt="A landscape",  # Not a face prompt
                    output_path=output_path,
                    face_override=True,
                    backends=[Backend.POLLINATIONS]
                )
                result = generate_image(req, DEFAULT_CONFIG)

                assert result.success is True
                assert result.metadata.get("is_face_content") is True

    def test_face_override_false(self):
        def mock_handler(prompt, width, height, out_path, config):
            Path(out_path).write_bytes(b"fake image")
            return (True, None)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.png")

            with patch.dict('image_generate.BACKEND_HANDLERS', {Backend.POLLINATIONS: mock_handler}):
                req = ImageRequest(
                    prompt="A portrait of a woman",  # Face prompt
                    output_path=output_path,
                    face_override=False,
                    backends=[Backend.POLLINATIONS]
                )
                result = generate_image(req, DEFAULT_CONFIG)

                assert result.success is True
                assert result.metadata.get("is_face_content") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
