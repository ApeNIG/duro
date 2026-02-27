"""
Skill: generate_tts
Description: Generate speech audio from text using edge-tts
Dependencies: edge-tts (pip install edge-tts)

Usage:
    python generate_tts.py --text "Hello world" --voice "en-GB-SoniaNeural" --output "output.mp3"

    Or import and use:
    from generate_tts import generate_speech
    generate_speech("Hello world", "en-GB-SoniaNeural", "output.mp3")
"""

import subprocess
import sys
import os
import argparse


# Voice presets for common characters
VOICE_PRESETS = {
    "tunde": "en-NG-AbeoNeural",      # Nigerian male
    "rachel": "en-GB-SoniaNeural",     # British female
    "maya": "en-GB-LibbyNeural",       # British young female
    "tayo": "en-US-AnaNeural",         # Young-sounding
    "chloe": "en-GB-MaisieNeural",     # British young female (friend)
}


def generate_speech(text: str, voice: str, output_path: str, rate: str = "+0%") -> dict:
    """
    Generate speech audio from text.

    Args:
        text: The text to convert to speech
        voice: Voice ID (e.g., "en-GB-SoniaNeural") or preset name (e.g., "rachel")
        output_path: Path to save the MP3 file
        rate: Speech rate adjustment (e.g., "+10%", "-5%")

    Returns:
        dict with keys: success, file_path, file_size, error
    """
    # Resolve voice preset if provided
    actual_voice = VOICE_PRESETS.get(voice.lower(), voice)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        cmd = [
            sys.executable, "-m", "edge_tts",
            "--voice", actual_voice,
            "--text", text,
            "--write-media", output_path
        ]

        if rate != "+0%":
            cmd.extend(["--rate", rate])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return {
                "success": False,
                "file_path": None,
                "file_size": 0,
                "error": result.stderr or "Unknown error"
            }

        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            return {
                "success": True,
                "file_path": output_path,
                "file_size": file_size,
                "error": None
            }
        else:
            return {
                "success": False,
                "file_path": None,
                "file_size": 0,
                "error": "File not created"
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "file_path": None,
            "file_size": 0,
            "error": "Timeout - check internet connection"
        }
    except Exception as e:
        return {
            "success": False,
            "file_path": None,
            "file_size": 0,
            "error": str(e)
        }


def list_voices(language_filter: str = None) -> list:
    """List available voices, optionally filtered by language code."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "edge_tts", "--list-voices"],
            capture_output=True,
            text=True,
            timeout=30
        )
        voices = result.stdout.strip().split("\n")

        if language_filter:
            voices = [v for v in voices if language_filter in v]

        return voices
    except Exception as e:
        return [f"Error: {e}"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate TTS audio")
    parser.add_argument("--text", required=True, help="Text to convert")
    parser.add_argument("--voice", required=True, help="Voice ID or preset name")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--rate", default="+0%", help="Speech rate adjustment")
    parser.add_argument("--list-voices", action="store_true", help="List available voices")
    parser.add_argument("--filter", default=None, help="Filter voices by language code")

    args = parser.parse_args()

    if args.list_voices:
        voices = list_voices(args.filter)
        for v in voices:
            print(v)
    else:
        result = generate_speech(args.text, args.voice, args.output, args.rate)
        if result["success"]:
            print(f"Success: {result['file_path']} ({result['file_size']} bytes)")
        else:
            print(f"Error: {result['error']}")
            sys.exit(1)
