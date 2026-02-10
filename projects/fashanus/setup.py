"""
The Fashanus - Production Tools Setup (Safe Version)

Only installs vetted, safe tools from established sources:
- edge-tts: Microsoft's public TTS service (open source wrapper)
- Pillow: Python Imaging Library (industry standard)

Usage:
    python setup.py install    # Install dependencies
    python setup.py voices     # List available TTS voices
    python setup.py test       # Generate test voice files for all characters
"""

import subprocess
import sys
import os

# Safe packages only - from established, trusted sources
SAFE_PACKAGES = [
    ("edge-tts", "Microsoft Edge TTS - open source, 10M+ downloads"),
    ("Pillow", "Python Imaging Library - industry standard, 500M+ downloads"),
]

# Voice assignments for The Fashanus
CHARACTERS = {
    "tunde": {
        "voice": "en-GB-RyanNeural",
        "alt_voice": "en-NG-AbeoNeural",  # Nigerian English option
        "description": "Dad, 35, Nigerian-British",
        "test_line": "Maya, we need to talk about your future. This is important."
    },
    "rachel": {
        "voice": "en-GB-SoniaNeural",
        "description": "Mum, 37, British",
        "test_line": "Tunde, she's eleven. Let her be a child for now."
    },
    "maya": {
        "voice": "en-GB-MaisieNeural",
        "description": "Daughter, 11",
        "test_line": "Why does he always do this? He doesn't understand me at all."
    },
    "tayo": {
        "voice": "en-GB-ThomasNeural",
        "description": "Son, 8",
        "test_line": "Mum, why is Dad upset? Did Maya do something wrong?"
    }
}


def install_dependencies():
    """Install safe, vetted Python packages."""
    print("=" * 50)
    print("THE FASHANUS - SAFE TOOLS INSTALLATION")
    print("=" * 50)
    print()
    print("Installing only vetted, safe packages:")
    print()

    for package, description in SAFE_PACKAGES:
        print(f"  {package}")
        print(f"    {description}")

    print()
    confirm = input("Proceed with installation? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Installation cancelled.")
        return

    print()
    for package, _ in SAFE_PACKAGES:
        print(f"Installing {package}...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"  Done.")
        except subprocess.CalledProcessError:
            print(f"  Failed! Try manually: pip install {package}")

    print()
    print("Installation complete!")
    print()
    print("Next steps:")
    print("  python setup.py voices  - See available voices")
    print("  python setup.py test    - Generate test audio for all characters")


def list_voices():
    """List available edge-tts voices for British and Nigerian English."""
    print("=" * 50)
    print("AVAILABLE VOICES FOR THE FASHANUS")
    print("=" * 50)
    print()

    try:
        result = subprocess.run(
            ["edge-tts", "--list-voices"],
            capture_output=True,
            text=True,
            timeout=30
        )
    except FileNotFoundError:
        print("edge-tts not found. Run 'python setup.py install' first.")
        return
    except subprocess.TimeoutExpired:
        print("Timeout fetching voices. Check your internet connection.")
        return

    voices = result.stdout.strip().split("\n")

    print("BRITISH ENGLISH VOICES:")
    print("-" * 40)
    for voice in voices:
        if "en-GB" in voice:
            print(f"  {voice}")

    print()
    print("NIGERIAN ENGLISH VOICES:")
    print("-" * 40)
    for voice in voices:
        if "en-NG" in voice:
            print(f"  {voice}")

    print()
    print("RECOMMENDED ASSIGNMENTS:")
    print("-" * 40)
    for name, info in CHARACTERS.items():
        print(f"  {name.capitalize():8} -> {info['voice']}")
        if 'alt_voice' in info:
            print(f"           (alt: {info['alt_voice']})")


def generate_test_voices():
    """Generate test voice files for all characters."""
    print("=" * 50)
    print("GENERATING TEST VOICE FILES")
    print("=" * 50)
    print()

    # Create output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "test_voices")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Output directory: {output_dir}")
    print()

    for name, info in CHARACTERS.items():
        print(f"Generating {name.capitalize()}'s voice...")
        print(f"  Voice: {info['voice']}")
        print(f"  Line: \"{info['test_line'][:50]}...\"")

        output_file = os.path.join(output_dir, f"{name}.mp3")

        try:
            result = subprocess.run(
                [
                    "edge-tts",
                    "--voice", info['voice'],
                    "--text", info['test_line'],
                    "--write-media", output_file
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if os.path.exists(output_file):
                size = os.path.getsize(output_file)
                print(f"  Saved: {output_file} ({size} bytes)")
            else:
                print(f"  Failed: File not created")
                if result.stderr:
                    print(f"  Error: {result.stderr[:100]}")

        except FileNotFoundError:
            print("  edge-tts not found. Run 'python setup.py install' first.")
            return
        except subprocess.TimeoutExpired:
            print("  Timeout. Check your internet connection.")

        print()

    print("=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)
    print()
    print(f"Voice files saved to: {output_dir}")
    print()
    print("Listen to these files and evaluate:")
    print("  - Does Tunde sound authoritative but warm?")
    print("  - Does Rachel sound nurturing?")
    print("  - Does Maya sound like a pre-teen?")
    print("  - Does Tayo sound like a young child?")
    print()
    print("If voices don't fit, run 'python setup.py voices' to see alternatives.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()

    if command == "install":
        install_dependencies()
    elif command == "voices":
        list_voices()
    elif command == "test":
        generate_test_voices()
    else:
        print(f"Unknown command: {command}")
        print()
        print(__doc__)


if __name__ == "__main__":
    main()
