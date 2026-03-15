#!/usr/bin/env python3
"""Clone a voice from YouTube or audio file for XTTS."""

import subprocess
import sys
from pathlib import Path

VOICES_DIR = Path.home() / ".cache" / "video_studio" / "xtts_voices" / "samples"


def download_youtube_audio(url: str, name: str, start: int = 0, duration: int = 30):
    """Download audio from YouTube and extract a voice sample."""
    try:
        import yt_dlp
    except ImportError:
        print("Installing yt-dlp...")
        subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp"], check=True)
        import yt_dlp

    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = VOICES_DIR / f"{name}.wav"

    if output_path.exists():
        print(f"Voice already exists: {name}")
        return str(output_path)

    temp_path = VOICES_DIR / f"{name}_temp.%(ext)s"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(temp_path),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
    }

    print(f"Downloading: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    temp_wav = VOICES_DIR / f"{name}_temp.wav"

    print(f"Extracting {duration}s clip starting at {start}s...")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(temp_wav),
        "-ss", str(start),
        "-t", str(duration),
        "-ar", "22050",
        "-ac", "1",
        str(output_path)
    ], capture_output=True)

    temp_wav.unlink()

    print(f"Saved voice sample: {output_path}")
    return str(output_path)


def extract_from_file(input_path: str, name: str, start: int = 0, duration: int = 30):
    """Extract a voice sample from an audio/video file."""
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = VOICES_DIR / f"{name}.wav"

    if output_path.exists():
        print(f"Voice already exists: {name}")
        return str(output_path)

    print(f"Extracting {duration}s clip from {input_path}...")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", input_path,
        "-ss", str(start),
        "-t", str(duration),
        "-ar", "22050",
        "-ac", "1",
        str(output_path)
    ], capture_output=True)

    print(f"Saved voice sample: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clone a voice from YouTube or audio file")
    parser.add_argument("source", help="YouTube URL or path to audio/video file")
    parser.add_argument("name", help="Name for the voice (e.g., 'rachel', 'host_female')")
    parser.add_argument("--start", type=int, default=0, help="Start time in seconds")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")

    args = parser.parse_args()

    if args.source.startswith("http"):
        download_youtube_audio(args.source, args.name, args.start, args.duration)
    else:
        extract_from_file(args.source, args.name, args.start, args.duration)

    print("\nTo preview: python preview_voices.py play", args.name)
    print("To map as host: python preview_voices.py map HOST", args.name)
