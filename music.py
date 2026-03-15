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
        local = self.get_local_music(style)
        if local:
            return local

        moods = MUSIC_MOODS.get(style, MUSIC_MOODS["educational"])

        for mood in moods:
            tracks = await self.search(f"{mood} background music", per_page=5)
            suitable = [t for t in tracks if t.duration >= min_duration]
            if suitable:
                track = random.choice(suitable)
                return await self.download(track)

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
