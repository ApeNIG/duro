"""
Skill: generate_episode_audio
Description: Generate all dialogue audio for an episode from a script file
Dependencies: edge-tts, generate_tts skill

Usage:
    python generate_episode_audio.py --script "path/to/script.md" --output-dir "path/to/output"
"""

import os
import sys
import re
import argparse
import json
from datetime import datetime

# Add sibling skill to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "audio"))
from generate_tts import generate_speech, VOICE_PRESETS


def parse_script_for_dialogue(script_path: str) -> list:
    """
    Parse a script.md file and extract dialogue lines.

    Expected format in script:
        **CHARACTER:**
        "Dialogue text here"

        Or:
        **CHARACTER (voiceover):**
        "Dialogue text"

    Returns list of dicts: {character, line, type, suggested_filename}
    """
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()

    dialogues = []

    # Pattern: **CHARACTER:** or **CHARACTER (context):**
    # Followed by quoted text or text on next line
    pattern = r'\*\*([A-Z]+)(?:\s*\(([^)]+)\))?\s*:\*\*\s*\n?"([^"]+)"'

    matches = re.findall(pattern, content, re.MULTILINE)

    for i, (character, context, line) in enumerate(matches):
        char_lower = character.lower()
        line_type = "voiceover" if context and "voiceover" in context.lower() else "dialogue"

        # Generate filename
        scene_num = i // 2 + 1  # Rough scene estimate
        filename = f"{char_lower}_sc{scene_num}"
        if line_type == "voiceover":
            filename += "_voiceover"
        filename += ".mp3"

        dialogues.append({
            "character": char_lower,
            "line": line.strip(),
            "type": line_type,
            "context": context,
            "suggested_filename": filename
        })

    return dialogues


def generate_episode_audio(script_path: str, output_dir: str, dry_run: bool = False) -> dict:
    """
    Generate all audio files for an episode.

    Args:
        script_path: Path to the script.md file
        output_dir: Directory to save audio files
        dry_run: If True, parse only, don't generate audio

    Returns:
        dict with keys: success, files_generated, files_failed, errors, dialogues
    """
    results = {
        "success": True,
        "files_generated": [],
        "files_failed": [],
        "errors": [],
        "dialogues": [],
        "start_time": datetime.now().isoformat(),
        "end_time": None
    }

    # Parse script
    try:
        dialogues = parse_script_for_dialogue(script_path)
        results["dialogues"] = dialogues
    except Exception as e:
        results["success"] = False
        results["errors"].append(f"Failed to parse script: {e}")
        return results

    if len(dialogues) == 0:
        results["errors"].append("No dialogue found in script")
        results["success"] = False
        return results

    if dry_run:
        results["end_time"] = datetime.now().isoformat()
        return results

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Generate audio for each dialogue
    for dialogue in dialogues:
        character = dialogue["character"]
        text = dialogue["line"]
        filename = dialogue["suggested_filename"]
        output_path = os.path.join(output_dir, filename)

        # Get voice for character
        voice = VOICE_PRESETS.get(character, "en-GB-SoniaNeural")

        print(f"Generating {filename}...")
        result = generate_speech(text, voice, output_path)

        if result["success"]:
            results["files_generated"].append({
                "filename": filename,
                "character": character,
                "size": result["file_size"]
            })
        else:
            results["files_failed"].append({
                "filename": filename,
                "character": character,
                "error": result["error"]
            })
            results["errors"].append(f"{filename}: {result['error']}")

    results["end_time"] = datetime.now().isoformat()
    results["success"] = len(results["files_failed"]) == 0

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate episode audio from script")
    parser.add_argument("--script", required=True, help="Path to script.md file")
    parser.add_argument("--output-dir", required=True, help="Output directory for audio files")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't generate")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    results = generate_episode_audio(args.script, args.output_dir, args.dry_run)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\nResults:")
        print(f"  Success: {results['success']}")
        print(f"  Files generated: {len(results['files_generated'])}")
        print(f"  Files failed: {len(results['files_failed'])}")

        if results['files_generated']:
            print("\nGenerated:")
            for f in results['files_generated']:
                print(f"  - {f['filename']} ({f['size']} bytes)")

        if results['errors']:
            print("\nErrors:")
            for e in results['errors']:
                print(f"  - {e}")

    sys.exit(0 if results['success'] else 1)
