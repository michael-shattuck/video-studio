#!/usr/bin/env python3
"""Preview and map voices to characters."""

import subprocess
import sys
from pathlib import Path

VOICES_DIR = Path.home() / ".cache" / "video_studio" / "xtts_voices" / "samples"
MAPPINGS_FILE = Path.home() / ".cache" / "video_studio" / "xtts_voices" / "voice_mappings.json"


def play_voice(voice_path: Path):
    """Play a voice sample using afplay (macOS)."""
    subprocess.run(["afplay", str(voice_path)])


def list_voices():
    """List all available voices."""
    if not VOICES_DIR.exists():
        print("No voices found. Run: python download_voices.py")
        return []

    voices = sorted(VOICES_DIR.glob("*.wav"))
    print(f"\nAvailable voices ({len(voices)}):\n")

    for i, v in enumerate(voices):
        size_kb = v.stat().st_size / 1024
        print(f"  {i+1:2}. {v.stem:<20} ({size_kb:.0f} KB)")

    return voices


def preview_all():
    """Preview all voices one by one."""
    voices = list_voices()
    if not voices:
        return

    print("\nPreviewing voices (press Ctrl+C to skip)...\n")

    for v in voices:
        print(f"Playing: {v.stem}")
        try:
            play_voice(v)
        except KeyboardInterrupt:
            print("  (skipped)")
            continue


def preview_one(name: str):
    """Preview a specific voice."""
    voice_path = VOICES_DIR / f"{name}.wav"
    if not voice_path.exists():
        print(f"Voice not found: {name}")
        print("Available:", [f.stem for f in VOICES_DIR.glob("*.wav")][:10])
        return

    print(f"Playing: {name}")
    play_voice(voice_path)


def map_voice(speaker_type: str, voice_name: str):
    """Map a speaker type to a voice."""
    import json

    voice_path = VOICES_DIR / f"{voice_name}.wav"
    if not voice_path.exists():
        print(f"Voice not found: {voice_name}")
        return

    mappings = {}
    if MAPPINGS_FILE.exists():
        with open(MAPPINGS_FILE) as f:
            mappings = json.load(f)

    mappings[speaker_type.upper()] = voice_name

    MAPPINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MAPPINGS_FILE, "w") as f:
        json.dump(mappings, f, indent=2)

    print(f"Mapped {speaker_type.upper()} -> {voice_name}")
    print(f"Current mappings: {mappings}")


def show_mappings():
    """Show current voice mappings."""
    import json

    if not MAPPINGS_FILE.exists():
        print("No mappings configured yet.")
        print("\nTo map a voice: python preview_voices.py map HOST libri_1246")
        return

    with open(MAPPINGS_FILE) as f:
        mappings = json.load(f)

    print("\nCurrent voice mappings:")
    for speaker, voice in mappings.items():
        print(f"  {speaker:<15} -> {voice}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Preview and map XTTS voices")
    parser.add_argument("action", nargs="?", default="list",
                       choices=["list", "preview", "play", "map", "mappings"],
                       help="Action to perform")
    parser.add_argument("args", nargs="*", help="Additional arguments")

    args = parser.parse_args()

    if args.action == "list":
        list_voices()
        print("\nTo preview a voice: python preview_voices.py play libri_1246")
        print("To map a voice:     python preview_voices.py map HOST libri_1246")

    elif args.action == "preview":
        preview_all()

    elif args.action == "play":
        if args.args:
            preview_one(args.args[0])
        else:
            print("Usage: python preview_voices.py play <voice_name>")

    elif args.action == "map":
        if len(args.args) >= 2:
            map_voice(args.args[0], args.args[1])
        else:
            print("Usage: python preview_voices.py map <SPEAKER_TYPE> <voice_name>")
            print("Speaker types: HOST, SIDE_A, SIDE_B, EXPERT, MODERATOR, etc.")

    elif args.action == "mappings":
        show_mappings()
