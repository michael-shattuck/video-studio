import asyncio
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

from .config import config
from .script_generator import ScriptGenerator, VideoScript, ScriptSegment
from .voice_generator import VoiceGenerator, OpenAIVoiceGenerator, ElevenLabsVoiceGenerator, BarkVoiceGenerator, FishSpeechVoiceGenerator, AzureTTSVoiceGenerator, AzureOpenAIAudioGenerator
from .stock_footage import StockFootageManager
from .video_assembler import VideoAssembler, AssemblyConfig
from .music import MusicFetcher, AudioMixer
from .talking_head import TalkingHeadManager


@dataclass
class VideoProject:
    topic: str
    script: VideoScript = None
    audio_path: str = ""
    footage_paths: list[str] = None
    video_path: str = ""
    thumbnail_path: str = ""
    created_at: str = ""

    def __post_init__(self):
        if self.footage_paths is None:
            self.footage_paths = []
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class VideoPipeline:
    def __init__(self, voice: str = None, voice_style: str = "documentary", is_short: bool = False, video_style: str = None, tts_engine: str = "auto", elevenlabs_voice_id: str = None, voice_speed: float = 1.15, talking_head: str = None, avatar_image: str = None, avatar_voice: str = "jane", avatar_character: str = "anika", avatar_style: str = "", use_photo_avatar: bool = True):
        self.script_gen = ScriptGenerator()
        self.voice = voice or "female_narrator"
        self.default_voice_style = voice_style
        self.video_style = video_style
        self.tts_engine = tts_engine
        self.elevenlabs_voice_id = elevenlabs_voice_id
        self.voice_speed = voice_speed
        self.talking_head_backend = talking_head
        self.avatar_image = avatar_image
        self.avatar_voice = avatar_voice
        self.avatar_character = avatar_character
        self.avatar_style = avatar_style
        self.use_photo_avatar = use_photo_avatar
        self.talking_head_mgr = TalkingHeadManager(
            backend=talking_head or "auto",
            avatar_voice=avatar_voice,
            avatar_character=avatar_character,
            avatar_style=avatar_style,
            use_photo_avatar=use_photo_avatar,
        ) if talking_head else None

        effective_voice_style = "turboencabulator" if video_style == "turboencabulator" else voice_style
        self.voice_gen = VoiceGenerator(self.voice, style=effective_voice_style)

        self.turbo_voice_gen = None
        if video_style == "turboencabulator":
            if tts_engine == "azure-openai" or (tts_engine == "auto" and config.azure_openai_key):
                self.turbo_voice_gen = AzureOpenAIAudioGenerator()
                self.tts_engine = "azure-openai"
            elif tts_engine == "edge":
                self.turbo_voice_gen = VoiceGenerator(avatar_voice, style="turboencabulator")
                self.tts_engine = "edge"
            elif tts_engine == "azure" or (tts_engine == "auto" and config.azure_speech_key):
                self.turbo_voice_gen = AzureTTSVoiceGenerator(voice=avatar_voice)
                self.tts_engine = "azure"
            elif tts_engine == "fish":
                self.turbo_voice_gen = FishSpeechVoiceGenerator()
                self.tts_engine = "fish"
            elif tts_engine == "bark":
                self.turbo_voice_gen = BarkVoiceGenerator()
                self.tts_engine = "bark"
            elif tts_engine == "elevenlabs" or (tts_engine == "auto" and config.elevenlabs_api_key):
                self.turbo_voice_gen = ElevenLabsVoiceGenerator(voice_id=elevenlabs_voice_id)
                self.tts_engine = "elevenlabs"
            elif tts_engine == "openai" or (tts_engine == "auto" and config.openai_api_key):
                self.turbo_voice_gen = OpenAIVoiceGenerator(voice=self.voice, style="turboencabulator")
                self.tts_engine = "openai"
            elif tts_engine == "auto":
                self.turbo_voice_gen = VoiceGenerator(avatar_voice, style="turboencabulator")
                self.tts_engine = "edge"

        self.footage_mgr = StockFootageManager(vertical=is_short)
        self.is_short = is_short
        assembly_config = AssemblyConfig.for_short() if is_short else AssemblyConfig()
        self.assembler = VideoAssembler(assembly_config)
        self.music_fetcher = MusicFetcher()
        self.audio_mixer = AudioMixer()

    def _concatenate_audio(self, audio_paths: list[str], output_path: str) -> str:
        from moviepy import AudioFileClip, concatenate_audioclips

        clips = [AudioFileClip(path) for path in audio_paths]
        combined = concatenate_audioclips(clips)
        combined.write_audiofile(output_path, fps=44100)

        for clip in clips:
            clip.close()
        combined.close()

        return output_path

    def _extract_audio_from_video(self, video_path: str, audio_path: str) -> str:
        from moviepy import VideoFileClip

        video = VideoFileClip(video_path)
        video.audio.write_audiofile(audio_path, fps=44100)
        video.close()

        return audio_path

    def _load_script(self, script_path: str) -> VideoScript:
        with open(script_path) as f:
            data = json.load(f)

        segments = [
            ScriptSegment(
                text=seg["text"],
                visual_cue=seg.get("visual_cue", ""),
            )
            for seg in data.get("segments", [])
        ]

        return VideoScript(
            title=data.get("title", ""),
            hook=data.get("hook", ""),
            segments=segments,
            outro=data.get("outro", ""),
            thumbnail_text=data.get("thumbnail_text", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            key_phrases=data.get("key_phrases", []),
        )

    async def create_video(
        self,
        topic: str,
        style: str = "educational",
        duration_minutes: int = 8,
        skip_footage: bool = False,
        add_music: bool = True,
        music_volume: float = 0.12,
        voice_only: bool = False,
        script_only: bool = False,
        approve_script: bool = False,
        script_file: str = None,
        script_format: str = "monologue",
        use_talking_head: bool = False,
        avatar_image: str = None,
    ) -> VideoProject:
        self.footage_mgr.used_assets = []
        project = VideoProject(topic=topic)
        safe_topic = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = Path(config.output_dir) / f"{timestamp}_{safe_topic.replace(' ', '_')}"
        project_dir.mkdir(parents=True, exist_ok=True)

        if script_file:
            print(f"[1/6] Loading script from: {script_file}")
            project.script = self._load_script(script_file)
        else:
            print(f"[1/6] Generating script for: {topic}")
            project.script = self.script_gen.generate(topic, style, duration_minutes, script_format)

        print(f"      Title: {project.script.title}")
        print(f"      Words: {project.script.word_count} (~{project.script.estimated_duration}s)")

        script_path = project_dir / "script.json"
        with open(script_path, "w") as f:
            json.dump({
                "title": project.script.title,
                "hook": project.script.hook,
                "segments": [{"text": s.text, "visual_cue": s.visual_cue} for s in project.script.segments],
                "outro": project.script.outro,
                "description": project.script.description,
                "tags": project.script.tags,
            }, f, indent=2)

        if script_only:
            print(f"\nScript-only complete: {script_path}")
            return project

        if approve_script:
            print(f"\n{'='*60}")
            print("SCRIPT PREVIEW")
            print(f"{'='*60}")
            print(f"\nTitle: {project.script.title}\n")
            print(f"Hook: {project.script.hook}\n")
            for i, seg in enumerate(project.script.segments, 1):
                print(f"[{i}] {seg.text[:200]}{'...' if len(seg.text) > 200 else ''}\n")
            print(f"Outro: {project.script.outro}\n")
            print(f"{'='*60}")
            print(f"Script saved to: {script_path}")
            print(f"{'='*60}")

            response = input("\nApprove script? [y]es / [n]o / [e]dit file path: ").strip().lower()
            if response == 'n' or response == 'no':
                print("Script rejected. Exiting.")
                return project
            elif response.startswith('e') or response not in ['y', 'yes', '']:
                edit_path = response[1:].strip() if response.startswith('e') else response
                if edit_path:
                    print(f"Reloading script from: {edit_path}")
                    project.script = self._load_script(edit_path)

        voice_path = str(project_dir / "voice.mp3")
        use_azure_avatar = (
            use_talking_head and
            self.talking_head_mgr and
            self.talking_head_mgr.get_backend() == "azure"
        )

        if use_azure_avatar:
            print(f"[2/6] Skipping TTS (Azure Avatar handles voice + video together)")
        else:
            print(f"[2/6] Generating voiceover...")

            if Path(voice_path).exists():
                Path(voice_path).unlink()

        if not use_azure_avatar and self.turbo_voice_gen and self.video_style == "turboencabulator":
            engine_name = self.tts_engine.upper()
            print(f"      Using {engine_name} TTS with emotional progression...")
            segments = [{"text": project.script.hook}]
            for seg in project.script.segments:
                segments.append({"text": seg.text})
            segments.append({"text": project.script.outro})

            segment_dir = project_dir / "voice_segments"

            if self.tts_engine == "elevenlabs":
                segment_paths = self.turbo_voice_gen.generate_turboencabulator(
                    segments, str(segment_dir), voice_id=self.elevenlabs_voice_id, base_speed=self.voice_speed
                )
            else:
                segment_paths = self.turbo_voice_gen.generate_turboencabulator(segments, str(segment_dir))

            self._concatenate_audio(segment_paths, voice_path)
            print(f"      Voice saved with emotional progression: {voice_path}")
        elif not use_azure_avatar:
            narration = project.script.full_narration
            await self.voice_gen.generate(narration, voice_path)
            print(f"      Voice saved: {voice_path}")

        project.audio_path = voice_path

        if voice_only:
            if use_azure_avatar:
                print(f"\nVoice-only not compatible with Azure Avatar (generates video too)")
            print(f"\nVoice-only complete: {voice_path}")
            return project

        if not use_azure_avatar and add_music and config.pixabay_api_key:
            print(f"[3/6] Adding background music...")
            music_path = await self.music_fetcher.get_music_for_style(style)
            if music_path:
                project.audio_path = str(project_dir / "narration.mp3")
                self.audio_mixer.mix_voice_and_music(
                    voice_path, music_path, project.audio_path, music_volume
                )
                print(f"      Mixed audio saved")
            else:
                project.audio_path = voice_path
                print(f"      No music found, using voice only")
        elif use_azure_avatar:
            print(f"[3/6] Skipping music (Azure Avatar generates audio)")
        else:
            project.audio_path = voice_path
            print(f"[3/6] Skipping music (no API key or disabled)")

        talking_head_video = None
        avatar_path = avatar_image or self.avatar_image
        if use_talking_head and self.talking_head_mgr:
            if self.talking_head_mgr.available:
                print(f"[4/7] Generating talking head video...")
                talking_head_video = str(project_dir / "talking_head.mp4")
                backend = self.talking_head_mgr.get_backend()
                print(f"      Using backend: {backend}")

                if backend == "azure":
                    print(f"      Avatar: {self.avatar_character} ({self.avatar_style})")
                    print(f"      Voice: {self.avatar_voice}")
                    self.talking_head_mgr.generate_from_script(project.script, talking_head_video)
                    self._extract_audio_from_video(talking_head_video, voice_path)
                    project.audio_path = voice_path
                elif avatar_path:
                    print(f"      Avatar image: {avatar_path}")
                    self.talking_head_mgr.generate(
                        avatar_path,
                        project.audio_path,
                        talking_head_video,
                    )
                else:
                    print(f"      No avatar image provided for {backend} backend")
                    use_talking_head = False

                if use_talking_head:
                    project.footage_paths = [talking_head_video]
                    print(f"      Talking head generated: {talking_head_video}")
            else:
                print(f"[4/7] Talking head requested but no backend available")
                print(f"      Options:")
                print(f"      - Azure Avatar: Set AZURE_SPEECH_KEY (no GPU needed)")
                print(f"      - MEMO: https://github.com/memoavatar/memo (requires GPU)")
                print(f"      - Hallo3: https://github.com/fudan-generative-vision/hallo3 (requires GPU)")
                use_talking_head = False

        if not use_talking_head and not skip_footage:
            visual_cues = [seg.visual_cue for seg in project.script.segments if seg.visual_cue]

            if config.pixabay_api_key or config.pexels_api_key:
                print(f"[4/6] Fetching stock footage...")
                footage_map = await self.footage_mgr.get_footage_for_cues(visual_cues)
                downloaded = await self.footage_mgr.download_all(footage_map)
                for paths in downloaded.values():
                    project.footage_paths.extend(paths)
                print(f"      Downloaded {len(project.footage_paths)} video clips")
            else:
                print(f"[4/6] Fetching stock images (no video API key)...")
                images_map = await self.footage_mgr.get_images_for_cues(visual_cues)
                for paths in images_map.values():
                    project.footage_paths.extend(paths)
                print(f"      Downloaded {len(project.footage_paths)} images")
        elif not use_talking_head:
            print(f"[4/6] Skipping visuals (skip_footage=True)")

        print(f"[5/6] Assembling video...")
        video_path = str(project_dir / "video.mp4")

        key_phrase_timings = []
        if project.script.key_phrases:
            from moviepy import AudioFileClip
            audio_clip = AudioFileClip(project.audio_path)
            audio_duration = audio_clip.duration
            audio_clip.close()

            phrases = project.script.key_phrases[:8]
            interval = audio_duration / (len(phrases) + 1)

            for i, phrase in enumerate(phrases):
                start_time = interval * (i + 1) - 1.0
                key_phrase_timings.append({
                    "text": phrase,
                    "start": max(0, start_time),
                    "duration": 2.5,
                })

        project.video_path = self.assembler.assemble(
            project.audio_path,
            project.footage_paths,
            video_path,
            key_phrases=key_phrase_timings,
        )
        print(f"      Video saved: {project.video_path}")

        print(f"[6/6] Creating thumbnail...")
        thumbnail_path = str(project_dir / "thumbnail.png")
        bg_path = project.footage_paths[0] if project.footage_paths else None
        project.thumbnail_path = self.assembler.create_thumbnail(
            project.script.thumbnail_text or topic,
            bg_path,
            thumbnail_path
        )
        print(f"      Thumbnail saved: {project.thumbnail_path}")

        attribution = self.footage_mgr.get_attribution_text()
        attribution_links = self.footage_mgr.get_attribution_links()

        full_description = project.script.description
        if attribution:
            full_description += f"\n\n---\n{attribution}"

        manifest_path = project_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump({
                "topic": project.topic,
                "title": project.script.title,
                "description": full_description,
                "tags": project.script.tags,
                "video_path": project.video_path,
                "thumbnail_path": project.thumbnail_path,
                "audio_path": project.audio_path,
                "created_at": project.created_at,
                "attribution": {
                    "text": attribution,
                    "links": attribution_links,
                },
            }, f, indent=2)

        print(f"\nVideo complete: {project.video_path}")
        if attribution:
            print(f"Attribution: {attribution}")
        return project

    async def batch_create(
        self,
        topics: list[str],
        style: str = "educational",
        duration_minutes: int = 8
    ) -> list[VideoProject]:
        projects = []
        for i, topic in enumerate(topics, 1):
            print(f"\n{'='*60}")
            print(f"Creating video {i}/{len(topics)}: {topic}")
            print(f"{'='*60}")

            project = await self.create_video(topic, style, duration_minutes)
            projects.append(project)

            await asyncio.sleep(1)

        return projects
