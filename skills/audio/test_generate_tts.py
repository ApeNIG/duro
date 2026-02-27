"""
Test: generate_tts skill
Run: python test_generate_tts.py
"""

import os
import sys
import tempfile

# Add parent to path for import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_tts import generate_speech, list_voices, VOICE_PRESETS


def test_basic_generation():
    """Test basic TTS generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test.mp3")
        result = generate_speech(
            text="Hello, this is a test.",
            voice="en-GB-SoniaNeural",
            output_path=output
        )

        assert result["success"], f"Generation failed: {result['error']}"
        assert os.path.exists(output), "Output file not created"
        assert result["file_size"] > 1000, "File too small"
        print("PASS: test_basic_generation")


def test_voice_preset():
    """Test voice preset resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_preset.mp3")
        result = generate_speech(
            text="This uses a preset voice.",
            voice="rachel",  # Preset name, not voice ID
            output_path=output
        )

        assert result["success"], f"Preset failed: {result['error']}"
        print("PASS: test_voice_preset")


def test_all_presets():
    """Test all character presets work."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for name, voice_id in VOICE_PRESETS.items():
            output = os.path.join(tmpdir, f"test_{name}.mp3")
            result = generate_speech(
                text=f"This is {name} speaking.",
                voice=name,
                output_path=output
            )
            assert result["success"], f"Preset {name} failed: {result['error']}"
            print(f"PASS: preset {name} ({voice_id})")


def test_list_voices():
    """Test voice listing."""
    voices = list_voices("en-GB")
    assert len(voices) > 0, "No voices returned"
    assert any("en-GB" in v for v in voices), "No en-GB voices found"
    print(f"PASS: test_list_voices ({len(voices)} en-GB voices)")


if __name__ == "__main__":
    print("Testing generate_tts skill...")
    print("-" * 40)

    try:
        test_basic_generation()
        test_voice_preset()
        test_all_presets()
        test_list_voices()
        print("-" * 40)
        print("ALL TESTS PASSED")
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
