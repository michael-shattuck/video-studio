import asyncio
import json
import random
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

from .config import config

# Rachel outfit variants - cycle through these for variety
RACHEL_OUTFITS = [
    "rachel_avatar.png",  # Original
    "rachel_red.png",
    "rachel_blue.png",
    "rachel_burgandy.png",
    "rachel_purple.png",
]

def get_random_outfit() -> str:
    """Pick a random Rachel outfit"""
    outfit = random.choice(RACHEL_OUTFITS)
    return str(Path(config.assets_dir) / outfit)

def get_outfit_by_index(index: int) -> str:
    """Get outfit by index (cycles through list)"""
    outfit = RACHEL_OUTFITS[index % len(RACHEL_OUTFITS)]
    return str(Path(config.assets_dir) / outfit)
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
    voice_segments: list[str] = None
    segment_emotions: list[str] = None
    video_path: str = ""
    thumbnail_path: str = ""
    created_at: str = ""

    def __post_init__(self):
        if self.footage_paths is None:
            self.footage_paths = []
        if self.voice_segments is None:
            self.voice_segments = []
        if self.segment_emotions is None:
            self.segment_emotions = []
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class Manifest:
    def __init__(self, project_dir: Path):
        self.path = project_dir / "manifest.json"
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            with open(self.path) as f:
                return json.load(f)
        return {
            "status": "started",
            "steps": {},
            "files": {},
        }

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def step_done(self, step: str) -> bool:
        return self.data["steps"].get(step) == "done"

    def mark_step(self, step: str, status: str = "done"):
        self.data["steps"][step] = status
        self.save()

    def add_file(self, category: str, path: str):
        if category not in self.data["files"]:
            self.data["files"][category] = []
        if path not in self.data["files"][category]:
            self.data["files"][category].append(path)
        self.save()

    def get_files(self, category: str) -> list[str]:
        return self.data["files"].get(category, [])

    def set_status(self, status: str):
        self.data["status"] = status
        self.save()


class VideoPipeline:
    def __init__(self, voice: str = None, voice_style: str = "documentary", is_short: bool = False, video_style: str = None, tts_engine: str = "auto", elevenlabs_voice_id: str = None, voice_speed: float = 1.15, talking_head: str = None, avatar_image: str = None, avatar_voice: str = "jane", avatar_character: str = "anika", avatar_style: str = "", use_photo_avatar: bool = True, overlay_style: str = "pip"):
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
        self.overlay_style = overlay_style
        is_philofab_style = video_style in ("turboencabulator", "philofabulator")
        use_talking_head_default = talking_head is not None or is_philofab_style
        self.talking_head_mgr = TalkingHeadManager(
            backend=talking_head or "infinitetalk",
            avatar_voice=avatar_voice,
            avatar_character=avatar_character,
            avatar_style=avatar_style,
            use_photo_avatar=use_photo_avatar,
        ) if use_talking_head_default else None
        self.auto_talking_head = is_philofab_style

        effective_voice_style = "turboencabulator" if is_philofab_style else voice_style
        self.voice_gen = VoiceGenerator(self.voice, style=effective_voice_style)

        self.turbo_voice_gen = None
        if is_philofab_style:
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

    def _calculate_emotion_times(self, voice_segments: list[str], segment_emotions: list[str]) -> list[dict]:
        """Calculate timestamps where emotional transitions occur."""
        from moviepy import AudioFileClip

        emotion_times = []
        cumulative_time = 0.0

        for i, seg_path in enumerate(voice_segments):
            if not Path(seg_path).exists():
                continue

            emotion = segment_emotions[i] if i < len(segment_emotions) else "default"

            # Trigger zoom at the START of high-energy emotions
            if emotion in {"excited", "passionate", "shouting", "frustrated"}:
                emotion_times.append({
                    "time": cumulative_time,
                    "emotion": emotion,
                })

            # Get duration for next segment's start time
            clip = AudioFileClip(seg_path)
            cumulative_time += clip.duration
            clip.close()

        return emotion_times

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
        resume_dir: str = None,
    ) -> VideoProject:
        if self.auto_talking_head and not use_talking_head:
            use_talking_head = True
        self.footage_mgr.used_assets = []
        project = VideoProject(topic=topic)

        if resume_dir:
            project_dir = Path(resume_dir)
            if not project_dir.exists():
                raise ValueError(f"Resume directory does not exist: {resume_dir}")
            print(f"Resuming from: {project_dir}")
        else:
            safe_topic = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)[:50]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_dir = Path(config.output_dir) / f"{timestamp}_{safe_topic.replace(' ', '_')}"
            project_dir.mkdir(parents=True, exist_ok=True)

        self.footage_mgr.set_output_dir(str(project_dir))
        manifest = Manifest(project_dir)

        script_path = project_dir / "script.json"
        if script_file:
            print(f"[1/6] Loading script from: {script_file}")
            project.script = self._load_script(script_file)
        elif manifest.step_done("script") and script_path.exists():
            print(f"[1/6] Script already exists, loading...")
            project.script = self._load_script(str(script_path))
        else:
            print(f"[1/6] Generating script for: {topic}")
            project.script = self.script_gen.generate(topic, style, duration_minutes, script_format, is_short=self.is_short)
            manifest.mark_step("script")

        print(f"      Title: {project.script.title}")
        print(f"      Words: {project.script.word_count} (~{project.script.estimated_duration}s)")

        if not script_path.exists():
            with open(script_path, "w") as f:
                json.dump({
                    "title": project.script.title,
                    "hook": project.script.hook,
                    "segments": [{"text": s.text, "visual_cue": s.visual_cue} for s in project.script.segments],
                    "outro": project.script.outro,
                    "description": project.script.description,
                    "tags": project.script.tags,
                }, f, indent=2)
        manifest.add_file("script", str(script_path))

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

        if manifest.step_done("voice") and Path(voice_path).exists():
            print(f"[2/6] Voice already exists, loading...")
            project.audio_path = voice_path
            segment_dir = project_dir / "voice_segments"
            if segment_dir.exists():
                project.voice_segments = sorted([str(p) for p in segment_dir.glob("*.mp3")])
            if manifest.data.get("segment_emotions"):
                project.segment_emotions = manifest.data["segment_emotions"]
        elif use_azure_avatar:
            print(f"[2/6] Skipping TTS (Azure Avatar handles voice + video together)")
        else:
            print(f"[2/6] Generating voiceover...")

        is_philofab = self.video_style in ("turboencabulator", "philofabulator")
        if not manifest.step_done("voice") and not use_azure_avatar and self.turbo_voice_gen and is_philofab:
            import re
            engine_name = self.tts_engine.upper()
            print(f"      Using {engine_name} TTS with emotional progression...")
            segments = []
            # For shorts: hook is subtitle-only, skip it. For long-form: include hook if non-empty
            if not self.is_short and project.script.hook:
                segments.append({"text": project.script.hook})
            for seg in project.script.segments:
                segments.append({"text": seg.text})
            # Only include outro if non-empty
            if project.script.outro:
                segments.append({"text": project.script.outro})

            emotions = []
            for seg in segments:
                text = seg["text"]
                match = re.match(r'^\[(\w+)\]\s*', text)
                emotions.append(match.group(1).lower() if match else "default")
            project.segment_emotions = emotions

            segment_dir = project_dir / "voice_segments"

            if self.tts_engine == "elevenlabs":
                segment_paths = self.turbo_voice_gen.generate_turboencabulator(
                    segments, str(segment_dir), voice_id=self.elevenlabs_voice_id, base_speed=self.voice_speed
                )
            else:
                segment_paths = self.turbo_voice_gen.generate_turboencabulator(segments, str(segment_dir))

            project.voice_segments = segment_paths
            self._concatenate_audio(segment_paths, voice_path)
            print(f"      Voice saved with emotional progression: {voice_path}")
            manifest.mark_step("voice")
            for seg_path in segment_paths:
                manifest.add_file("voice_segments", seg_path)
            manifest.data["segment_emotions"] = emotions
        elif not manifest.step_done("voice") and not use_azure_avatar:
            narration = project.script.full_narration
            await self.voice_gen.generate(narration, voice_path)
            print(f"      Voice saved: {voice_path}")
            manifest.mark_step("voice")

        project.audio_path = voice_path
        manifest.add_file("voice", voice_path)

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

        talking_head_video = str(project_dir / "talking_head.mp4")
        avatar_path = avatar_image or self.avatar_image
        if not avatar_path:
            # Cycle through Rachel outfits for variety
            avatar_path = get_random_outfit()
            print(f"[outfit] Using: {Path(avatar_path).name}")

        talking_head_loaded = False
        if Path(talking_head_video).exists():
            print(f"[4/7] Talking head already exists, loading...")
            project.footage_paths = [talking_head_video]
            project.video_path = talking_head_video
            manifest.mark_step("talking_head")
            talking_head_loaded = True
        elif use_talking_head and self.talking_head_mgr:
            if self.talking_head_mgr.available:
                print(f"[4/7] Generating talking head video...")
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
                    try:
                        self.talking_head_mgr.generate(
                            avatar_path,
                            project.audio_path,
                            talking_head_video,
                            voice_segments=project.voice_segments if project.voice_segments else None,
                            segment_emotions=project.segment_emotions if project.segment_emotions else None,
                        )
                        if not Path(talking_head_video).exists():
                            print(f"      Talking head generation failed - file not created")
                            use_talking_head = False
                    except Exception as e:
                        print(f"      Talking head generation failed: {e}")
                        use_talking_head = False
                else:
                    print(f"      No avatar image provided for {backend} backend")
                    use_talking_head = False

                if use_talking_head and talking_head_video and Path(talking_head_video).exists():
                    project.footage_paths = [talking_head_video]
                    project.video_path = talking_head_video
                    manifest.mark_step("talking_head")
                    print(f"      Talking head generated: {talking_head_video}")
            else:
                print(f"[4/7] Talking head requested but no backend available")
                print(f"      Options:")
                print(f"      - Azure Avatar: Set AZURE_SPEECH_KEY (no GPU needed)")
                print(f"      - MEMO: https://github.com/memoavatar/memo (requires GPU)")
                print(f"      - Hallo3: https://github.com/fudan-generative-vision/hallo3 (requires GPU)")
                use_talking_head = False

        if (talking_head_loaded or use_talking_head) and Path(talking_head_video).exists() and self.footage_mgr.use_dalle:
            composite_path = str(project_dir / "video.mp4")
            if Path(composite_path).exists():
                print(f"[5/7] Composite video already exists, loading...")
                project.video_path = composite_path
                project.footage_paths = [composite_path]
            else:
                print(f"[5/7] Generating DALL-E images for overlays...")
                visual_cues = [seg.visual_cue for seg in project.script.segments if seg.visual_cue]
                images_map = await self.footage_mgr.get_images_for_cues(visual_cues)

                from moviepy import AudioFileClip
                audio_clip = AudioFileClip(project.audio_path)
                total_duration = audio_clip.duration
                audio_clip.close()

                segment_images = []
                num_segments = len(project.script.segments)
                segment_duration = total_duration / num_segments if num_segments > 0 else 5

                for i, seg in enumerate(project.script.segments):
                    if seg.visual_cue and seg.visual_cue in images_map:
                        paths = images_map[seg.visual_cue]
                        if paths:
                            segment_images.append({
                                "image_path": paths[0],
                                "start": i * segment_duration,
                                "duration": segment_duration,
                            })

                if segment_images and self.overlay_style != "none":
                    print(f"[6/7] Compositing {len(segment_images)} image overlays ({self.overlay_style})...")
                    self.assembler.composite_with_overlays(
                        talking_head_video,
                        segment_images,
                        composite_path,
                        overlay_style=self.overlay_style,
                    )
                    project.video_path = composite_path
                    project.footage_paths = [composite_path]
                    manifest.mark_step("composite")
                    print(f"      Final video: {composite_path}")

                # Add zoom effects at emotion transitions (for shorts)
                if self.is_short and project.voice_segments and project.segment_emotions:
                    emotion_times = self._calculate_emotion_times(project.voice_segments, project.segment_emotions)
                    if emotion_times:
                        print(f"      Adding zoom effects at {len(emotion_times)} emotion points...")
                        zoomed_path = str(project_dir / "video_zoomed.mp4")
                        self.assembler.add_zoom_effects(project.video_path, zoomed_path, emotion_times)
                        # Replace video with zoomed version
                        import shutil
                        shutil.move(zoomed_path, project.video_path)

                # Add animated captions (for shorts, requires whisper)
                if self.is_short and project.audio_path:
                    try:
                        from .video_assembler import get_word_timestamps
                        print(f"      Extracting word timestamps for captions...")
                        word_timings = get_word_timestamps(project.audio_path)
                        if word_timings:
                            print(f"      Adding animated captions ({len(word_timings)} words)...")
                            captioned_path = str(project_dir / "video_captioned.mp4")
                            self.assembler.add_animated_captions(project.video_path, captioned_path, word_timings)
                            import shutil
                            shutil.move(captioned_path, project.video_path)
                    except Exception as e:
                        print(f"      Captions skipped: {e}")

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

        if not project.video_path:
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

        thumbnail_path = str(project_dir / "thumbnail.png")
        if Path(thumbnail_path).exists():
            print(f"[6/6] Thumbnail already exists, loading...")
            project.thumbnail_path = thumbnail_path
        else:
            print(f"[6/6] Creating thumbnail...")
            bg_path = project.footage_paths[0] if project.footage_paths else None
            project.thumbnail_path = self.assembler.create_thumbnail(
                project.script.thumbnail_text or topic,
                bg_path,
                thumbnail_path,
                project_dir=str(project_dir),
            )
            print(f"      Thumbnail saved: {project.thumbnail_path}")

        attribution = self.footage_mgr.get_attribution_text()
        attribution_links = self.footage_mgr.get_attribution_links()

        full_description = project.script.description
        if attribution:
            full_description += f"\n\n---\n{attribution}"

        manifest.data["topic"] = project.topic
        manifest.data["title"] = project.script.title
        manifest.data["description"] = full_description
        manifest.data["tags"] = project.script.tags
        manifest.data["video_path"] = project.video_path
        manifest.data["thumbnail_path"] = project.thumbnail_path
        manifest.data["audio_path"] = project.audio_path
        manifest.data["created_at"] = project.created_at
        manifest.data["attribution"] = {
            "text": attribution,
            "links": attribution_links,
        }
        manifest.set_status("complete")
        manifest.save()

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
