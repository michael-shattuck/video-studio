import asyncio
import aiohttp
import random
from pathlib import Path
from dataclasses import dataclass

from .config import config


@dataclass
class MusicTrack:
    id: str
    url: str
    title: str
    duration: int
    local_path: str = ""


MUSIC_MOODS = {
    "educational": ["ambient", "corporate", "inspirational"],
    "motivational": ["uplifting", "epic", "motivational"],
    "documentary": ["cinematic", "ambient", "atmospheric"],
    "storytelling": ["emotional", "dramatic", "suspense"],
    "relaxing": ["relaxing", "calm", "meditation"],
    "energetic": ["upbeat", "electronic", "energetic"],
    "turboencabulator": ["dramatic", "tension", "suspense", "dark ambient"],
    "philofabulator": ["dramatic", "tension", "suspense", "dark ambient"],
    "comedic": ["quirky", "funny", "playful", "comedy"],
}


class MusicFetcher:
    def __init__(self):
        self.api_key = config.pixabay_api_key
        self.base_url = "https://pixabay.com/api"
        self.cache_dir = Path(config.cache_dir) / "music"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.local_music_dir = Path(config.cache_dir).parent / "music_library"

    async def search(self, query: str, per_page: int = 10) -> list[MusicTrack]:
        if not self.api_key:
            return []

        params = {
            "key": self.api_key,
            "q": query,
            "per_page": min(per_page, 200),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/music/", params=params) as resp:
                    if resp.status != 200:
                        return []
                    content_type = resp.headers.get("content-type", "")
                    if "application/json" not in content_type:
                        return []
                    data = await resp.json()
        except Exception:
            return []

        tracks = []
        for hit in data.get("hits", []):
            audio_url = hit.get("audio", "")
            if audio_url:
                tracks.append(MusicTrack(
                    id=str(hit["id"]),
                    url=audio_url,
                    title=hit.get("title", "music"),
                    duration=hit.get("duration", 60),
                ))

        return tracks

    def get_local_music(self, style: str = "educational") -> str:
        if not self.local_music_dir.exists():
            self.local_music_dir.mkdir(parents=True, exist_ok=True)
            return ""

        style_dir = self.local_music_dir / style
        if style_dir.exists():
            tracks = list(style_dir.glob("*.mp3")) + list(style_dir.glob("*.wav"))
            if tracks:
                return str(random.choice(tracks))

        all_tracks = list(self.local_music_dir.glob("*.mp3")) + list(self.local_music_dir.glob("*.wav"))
        if all_tracks:
            return str(random.choice(all_tracks))

        return ""

    async def get_music_for_style(self, style: str = "educational", min_duration: int = 60) -> str:
        # 1. Try local music library first
        local = self.get_local_music(style)
        if local:
            print(f"      Using local music: {Path(local).name}")
            return local

        # 2. Try MusicGen if endpoint configured
        musicgen = MusicGenClient()
        if musicgen.available:
            print(f"      Generating music with MusicGen...")
            generated = await musicgen.generate(style, duration=min_duration)
            if generated:
                return generated

        # 3. Pixabay Music API (currently broken - 404)
        # moods = MUSIC_MOODS.get(style, MUSIC_MOODS["educational"])
        # for mood in moods:
        #     tracks = await self.search(f"{mood} background music", per_page=5)
        #     suitable = [t for t in tracks if t.duration >= min_duration]
        #     if suitable:
        #         track = random.choice(suitable)
        #         return await self.download(track)

        return ""

    async def download(self, track: MusicTrack) -> str:
        if not track.url:
            return ""

        output_path = self.cache_dir / f"{track.id}.mp3"

        if output_path.exists():
            track.local_path = str(output_path)
            return str(output_path)

        async with aiohttp.ClientSession() as session:
            async with session.get(track.url) as resp:
                if resp.status != 200:
                    return ""
                content = await resp.read()

        with open(output_path, "wb") as f:
            f.write(content)

        track.local_path = str(output_path)
        return str(output_path)


class AudioMixer:
    def __init__(self):
        pass

    def mix_voice_and_music(
        self,
        voice_path: str,
        music_path: str,
        output_path: str,
        music_volume: float = 0.15,
    ) -> str:
        from moviepy import AudioFileClip, CompositeAudioClip

        voice = AudioFileClip(voice_path)
        music = AudioFileClip(music_path)

        if music.duration < voice.duration:
            loops_needed = int(voice.duration / music.duration) + 1
            from moviepy import concatenate_audioclips
            music_clips = [music] * loops_needed
            music = concatenate_audioclips(music_clips)

        music = music.subclipped(0, voice.duration)
        music = music.with_volume_scaled(music_volume)

        mixed = CompositeAudioClip([voice, music])
        mixed.write_audiofile(output_path, fps=44100)

        voice.close()
        music.close()
        mixed.close()

        return output_path


# MusicGen prompts for different styles
MUSICGEN_PROMPTS = {
    "turboencabulator": "dramatic orchestral tension building, cinematic dark ambient, suspenseful underscore, minor key",
    "philofabulator": "dramatic orchestral tension building, cinematic dark ambient, suspenseful underscore, minor key",
    "educational": "inspiring corporate ambient, uplifting background music, motivational",
    "documentary": "cinematic atmospheric, emotional underscore, ambient textures",
    "comedic": "quirky playful music, lighthearted comedy, whimsical",
    "default": "ambient background music, subtle underscore",
}


class MusicGenClient:
    """Client for MusicGen RunPod endpoint."""

    def __init__(self, endpoint_id: str = None):
        import os
        self.api_key = os.getenv("RUNPOD_API_KEY", "")
        self.endpoint_id = endpoint_id or os.getenv("RUNPOD_MUSICGEN_ENDPOINT", "")
        self.base_url = f"https://api.runpod.ai/v2/{self.endpoint_id}" if self.endpoint_id else ""
        self.cache_dir = Path(config.cache_dir) / "musicgen"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.endpoint_id)

    async def generate(self, style: str = "default", duration: int = 30) -> str:
        """Generate music for a style. Returns path to audio file."""
        if not self.available:
            return ""

        import aiohttp
        import hashlib

        prompt = MUSICGEN_PROMPTS.get(style, MUSICGEN_PROMPTS["default"])

        # Check cache
        cache_key = hashlib.md5(f"{prompt}_{duration}".encode()).hexdigest()[:12]
        cache_path = self.cache_dir / f"{cache_key}.wav"
        if cache_path.exists():
            return str(cache_path)

        # Submit job
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/run",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": {"prompt": prompt, "duration": duration}}
            ) as resp:
                if resp.status != 200:
                    print(f"      MusicGen submit failed: {resp.status}")
                    return ""
                data = await resp.json()
                job_id = data.get("id")

        if not job_id:
            return ""

        # Poll for result
        import asyncio
        for _ in range(60):  # 5 minute timeout
            await asyncio.sleep(5)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/status/{job_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    status = data.get("status")

                    if status == "COMPLETED":
                        audio_b64 = data.get("output", {}).get("audio", "")
                        if audio_b64.startswith("data:audio/wav;base64,"):
                            audio_b64 = audio_b64[len("data:audio/wav;base64,"):]

                        import base64
                        with open(cache_path, "wb") as f:
                            f.write(base64.b64decode(audio_b64))

                        print(f"      MusicGen: Generated {duration}s track")
                        return str(cache_path)

                    elif status == "FAILED":
                        print(f"      MusicGen failed: {data.get('error')}")
                        return ""

        print("      MusicGen timed out")
        return ""
