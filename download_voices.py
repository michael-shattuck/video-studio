#!/usr/bin/env python3
"""Download diverse voice samples for XTTS voice cloning."""

import subprocess
import sys
from pathlib import Path

VOICES_DIR = Path.home() / ".cache" / "video_studio" / "xtts_voices" / "samples"


def download_vctk_voices(count: int = 20):
    """Download voices from VCTK dataset (British accents, male/female)."""
    print(f"Downloading {count} VCTK voices...")

    try:
        from datasets import load_dataset
        import soundfile as sf
    except ImportError:
        print("Installing required packages...")
        subprocess.run([sys.executable, "-m", "pip", "install", "datasets", "soundfile"], check=True)
        from datasets import load_dataset
        import soundfile as sf

    VOICES_DIR.mkdir(parents=True, exist_ok=True)

    ds = load_dataset("VCTK", split="train", streaming=True, trust_remote_code=True)

    speakers_seen = set()
    downloaded = 0

    for sample in ds:
        speaker_id = sample.get("speaker_id", sample.get("speaker", f"unknown_{downloaded}"))

        if speaker_id in speakers_seen:
            continue

        speakers_seen.add(speaker_id)

        audio = sample["audio"]
        filename = VOICES_DIR / f"vctk_{speaker_id}.wav"

        if not filename.exists():
            sf.write(str(filename), audio["array"], audio["sampling_rate"])
            print(f"  Downloaded: vctk_{speaker_id}.wav")
        else:
            print(f"  Exists: vctk_{speaker_id}.wav")

        downloaded += 1
        if downloaded >= count:
            break

    print(f"Downloaded {downloaded} VCTK voices to {VOICES_DIR}")
    return downloaded


def download_librispeech_voices(count: int = 10):
    """Download voices from LibriSpeech dataset (American accents)."""
    print(f"Downloading {count} LibriSpeech voices...")

    try:
        from datasets import load_dataset
        import soundfile as sf
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "datasets", "soundfile"], check=True)
        from datasets import load_dataset
        import soundfile as sf

    VOICES_DIR.mkdir(parents=True, exist_ok=True)

    ds = load_dataset("librispeech_asr", "clean", split="train.100", streaming=True)

    speakers_seen = set()
    downloaded = 0

    for sample in ds:
        speaker_id = sample.get("speaker_id", str(downloaded))

        if speaker_id in speakers_seen:
            continue

        speakers_seen.add(speaker_id)

        audio = sample["audio"]
        filename = VOICES_DIR / f"libri_{speaker_id}.wav"

        if not filename.exists():
            sf.write(str(filename), audio["array"], audio["sampling_rate"])
            print(f"  Downloaded: libri_{speaker_id}.wav")
        else:
            print(f"  Exists: libri_{speaker_id}.wav")

        downloaded += 1
        if downloaded >= count:
            break

    print(f"Downloaded {downloaded} LibriSpeech voices to {VOICES_DIR}")
    return downloaded


def download_common_voice(count: int = 10, language: str = "en"):
    """Download voices from Mozilla Common Voice."""
    print(f"Downloading {count} Common Voice samples...")

    try:
        from datasets import load_dataset
        import soundfile as sf
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "datasets", "soundfile"], check=True)
        from datasets import load_dataset
        import soundfile as sf

    VOICES_DIR.mkdir(parents=True, exist_ok=True)

    ds = load_dataset("mozilla-foundation/common_voice_11_0", language, split="train", streaming=True, trust_remote_code=True)

    speakers_seen = set()
    downloaded = 0

    for sample in ds:
        client_id = sample.get("client_id", str(downloaded))[:8]

        if client_id in speakers_seen:
            continue

        speakers_seen.add(client_id)

        audio = sample["audio"]
        filename = VOICES_DIR / f"cv_{client_id}.wav"

        if not filename.exists():
            sf.write(str(filename), audio["array"], audio["sampling_rate"])
            print(f"  Downloaded: cv_{client_id}.wav")
        else:
            print(f"  Exists: cv_{client_id}.wav")

        downloaded += 1
        if downloaded >= count:
            break

    print(f"Downloaded {downloaded} Common Voice samples to {VOICES_DIR}")
    return downloaded


def list_voices():
    """List all downloaded voices."""
    if not VOICES_DIR.exists():
        print("No voices downloaded yet.")
        return []

    voices = list(VOICES_DIR.glob("*.wav"))
    print(f"\nDownloaded voices ({len(voices)} total):")
    print(f"Location: {VOICES_DIR}\n")

    for v in sorted(voices):
        size_kb = v.stat().st_size / 1024
        print(f"  {v.name} ({size_kb:.1f} KB)")

    return voices


def download_female_narrators(count: int = 5):
    """Download high-quality female narrator voices from various sources."""
    import requests

    print(f"Downloading {count} female narrator voices...")
    VOICES_DIR.mkdir(parents=True, exist_ok=True)

    FEMALE_VOICE_URLS = {
        "female_narrator_1": "https://www2.cs.uic.edu/~i101/SoundFiles/StarWars3.wav",
        "female_host_warm": "https://github.com/coqui-ai/TTS/raw/dev/tests/inputs/ljspeech/wavs/LJ001-0001.wav",
    }

    downloaded = 0
    for name, url in list(FEMALE_VOICE_URLS.items())[:count]:
        dest = VOICES_DIR / f"{name}.wav"
        if dest.exists():
            print(f"  Exists: {name}.wav")
            downloaded += 1
            continue

        try:
            print(f"  Downloading {name}...")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            downloaded += 1
        except Exception as e:
            print(f"  Failed: {name} - {e}")

    return downloaded


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download voice samples for XTTS")
    parser.add_argument("--vctk", type=int, default=0, help="Number of VCTK voices to download")
    parser.add_argument("--libri", type=int, default=0, help="Number of LibriSpeech voices to download")
    parser.add_argument("--cv", type=int, default=0, help="Number of Common Voice samples to download")
    parser.add_argument("--female", type=int, default=0, help="Download female narrator voices")
    parser.add_argument("--all", type=int, default=0, help="Download this many from each source")
    parser.add_argument("--list", action="store_true", help="List downloaded voices")

    args = parser.parse_args()

    if args.list:
        list_voices()
        sys.exit(0)

    if args.all:
        args.vctk = args.all
        args.libri = args.all

    if not any([args.vctk, args.libri, args.cv]):
        print("Downloading default set (10 VCTK + 10 LibriSpeech)...")
        args.vctk = 10
        args.libri = 10

    total = 0

    if args.vctk:
        total += download_vctk_voices(args.vctk)

    if args.libri:
        total += download_librispeech_voices(args.libri)

    if args.cv:
        total += download_common_voice(args.cv)

    print(f"\nTotal: {total} voices downloaded")
    print(f"Location: {VOICES_DIR}")
    print("\nTo use with XTTS, set tts_engine to 'xtts' in the dashboard.")
