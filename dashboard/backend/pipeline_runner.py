import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from video_studio.config import config
from video_studio.script_generator import ScriptGenerator, VideoScript as OriginalVideoScript, ScriptSegment as OriginalScriptSegment
from video_studio.voice_generator import VoiceGenerator, OpenAIVoiceGenerator, ElevenLabsVoiceGenerator, BarkVoiceGenerator, FishSpeechVoiceGenerator
from video_studio.stock_footage import StockFootageManager
from video_studio.video_assembler import VideoAssembler, AssemblyConfig
from video_studio.music import MusicFetcher, AudioMixer
from video_studio.talking_head import TalkingHeadManager

from .models import (
    Project, ProjectConfig, ProjectStatus, StepStatus,
    VideoScript, ScriptSegment, CHAOTIC_THRESHOLDS
)
from .project_manager import ProjectManager


class PipelineRunner:
    def __init__(
        self,
        project_manager: ProjectManager,
        progress_callback: Optional[Callable[[str, str, StepStatus, float, str], None]] = None
    ):
        self.project_manager = project_manager
        self.progress_callback = progress_callback
        self._pause_requested = False
        self._current_project_id: Optional[str] = None

    def _notify_progress(
        self,
        project_id: str,
        step: str,
        status: StepStatus,
        progress: float,
        message: str
    ):
        self.project_manager.update_step(
            project_id, step,
            status=status,
            progress=progress,
            message=message
        )
        if self.progress_callback:
            self.progress_callback(project_id, step, status, progress, message)

    def _convert_to_original_script(self, script: VideoScript) -> OriginalVideoScript:
        segments = [
            OriginalScriptSegment(
                text=seg.text,
                visual_cue=seg.visual_cue
            )
            for seg in script.segments
        ]
        return OriginalVideoScript(
            title=script.title,
            hook=script.hook,
            segments=segments,
            outro=script.outro,
            thumbnail_text=script.thumbnail_text,
            description=script.description,
            tags=script.tags,
            key_phrases=script.key_phrases
        )

    def _convert_from_original_script(self, script: OriginalVideoScript) -> VideoScript:
        segments = [
            ScriptSegment(
                text=seg.text,
                visual_cue=seg.visual_cue,
                speaker=None
            )
            for seg in script.segments
        ]
        return VideoScript(
            title=script.title,
            hook=script.hook,
            segments=segments,
            outro=script.outro,
            thumbnail_text=script.thumbnail_text,
            description=script.description,
            tags=script.tags,
            key_phrases=script.key_phrases
        )

    def _get_project_dir(self, project: Project) -> Path:
        if project.output_dir:
            return Path(project.output_dir)

        safe_topic = "".join(
            c if c.isalnum() or c in " -_" else ""
            for c in project.config.topic
        )[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = Path(config.output_dir) / f"{timestamp}_{safe_topic.replace(' ', '_')}"
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    def _create_voice_generator(self, cfg: ProjectConfig):
        effective_style = "turboencabulator" if cfg.style.value == "turboencabulator" else cfg.voice_style.value
        tts = cfg.tts_engine.value

        if cfg.style.value == "turboencabulator":
            if tts == "fish" or tts == "auto":
                return FishSpeechVoiceGenerator()
            elif tts == "elevenlabs":
                return ElevenLabsVoiceGenerator(voice_id=cfg.elevenlabs_voice_id)
            elif tts == "openai":
                return OpenAIVoiceGenerator(voice=cfg.voice.value, style="turboencabulator")
            elif tts == "bark":
                return BarkVoiceGenerator()

        if tts == "fish":
            return FishSpeechVoiceGenerator()
        elif tts == "elevenlabs":
            return ElevenLabsVoiceGenerator(voice_id=cfg.elevenlabs_voice_id)
        elif tts == "openai":
            return OpenAIVoiceGenerator(voice=cfg.voice.value, style=effective_style)
        elif tts == "bark":
            return BarkVoiceGenerator()
        else:
            return VoiceGenerator(cfg.voice.value, style=effective_style)

    def request_pause(self):
        self._pause_requested = True

    def is_paused(self) -> bool:
        return self._pause_requested

    async def run_script_step(self, project_id: str) -> Optional[Project]:
        project = self.project_manager.get(project_id)
        if not project:
            return None

        self._notify_progress(project_id, "script", StepStatus.RUNNING, 0, "Generating script...")

        try:
            project_dir = self._get_project_dir(project)
            self.project_manager.set_output_dir(project_id, str(project_dir))

            if project.config.transcript:
                self._notify_progress(project_id, "script", StepStatus.RUNNING, 50, "Parsing provided transcript...")
                script_data = json.loads(project.config.transcript)
                script = VideoScript.model_validate(script_data)
            else:
                script_gen = ScriptGenerator()
                self._notify_progress(project_id, "script", StepStatus.RUNNING, 20, "Researching topic...")

                original_script = script_gen.generate(
                    project.config.topic,
                    project.config.style.value,
                    project.config.duration_minutes,
                    project.config.format.value
                )

                self._notify_progress(project_id, "script", StepStatus.RUNNING, 80, "Processing script...")
                script = self._convert_from_original_script(original_script)

            script_path = project_dir / "script.json"
            with open(script_path, "w") as f:
                f.write(script.model_dump_json(indent=2))

            self.project_manager.set_script(project_id, script)
            self.project_manager.update_step(
                project_id, "script",
                artifacts=[str(script_path)]
            )

            self._notify_progress(project_id, "script", StepStatus.COMPLETE, 100, f"Script generated: {script.title}")
            self.project_manager.update_status(project_id, ProjectStatus.SCRIPT)

            return self.project_manager.get(project_id)

        except Exception as e:
            self._notify_progress(project_id, "script", StepStatus.FAILED, 0, str(e))
            self.project_manager.set_error(project_id, str(e))
            return None

    async def run_voice_step(self, project_id: str) -> Optional[Project]:
        project = self.project_manager.get(project_id)
        if not project or not project.script:
            return None

        self._notify_progress(project_id, "voice", StepStatus.RUNNING, 0, "Initializing voice generator...")

        try:
            project_dir = Path(project.output_dir)
            voice_gen = self._create_voice_generator(project.config)

            full_narration = project.script.hook + "\n\n"
            for i, seg in enumerate(project.script.segments):
                full_narration += seg.text + "\n\n"
            full_narration += project.script.outro

            self._notify_progress(project_id, "voice", StepStatus.RUNNING, 10, "Generating audio...")

            if project.config.style.value == "turboencabulator":
                thresholds = CHAOTIC_THRESHOLDS.get(project.config.chaotic_level, CHAOTIC_THRESHOLDS[3])
                audio_path = await self._generate_turbo_voice(
                    voice_gen, full_narration, project_dir, thresholds
                )
            else:
                audio_path = voice_gen.generate(
                    full_narration,
                    str(project_dir / "voice.mp3")
                )

            self.project_manager.update_step(
                project_id, "voice",
                artifacts=[audio_path]
            )

            self._notify_progress(project_id, "voice", StepStatus.COMPLETE, 100, "Voice generation complete")
            self.project_manager.update_status(project_id, ProjectStatus.VOICE)

            return self.project_manager.get(project_id)

        except Exception as e:
            self._notify_progress(project_id, "voice", StepStatus.FAILED, 0, str(e))
            self.project_manager.set_error(project_id, str(e))
            return None

    async def _generate_turbo_voice(
        self,
        voice_gen,
        text: str,
        project_dir: Path,
        thresholds: dict
    ) -> str:
        output_path = str(project_dir / "voice.mp3")

        if hasattr(voice_gen, 'generate_with_intensity'):
            return voice_gen.generate_with_intensity(text, output_path, thresholds)

        return voice_gen.generate(text, output_path)

    async def run_music_step(self, project_id: str) -> Optional[Project]:
        project = self.project_manager.get(project_id)
        if not project:
            return None

        if not project.config.add_music:
            self._notify_progress(project_id, "music", StepStatus.SKIPPED, 100, "Music skipped")
            return project

        self._notify_progress(project_id, "music", StepStatus.RUNNING, 0, "Fetching music...")

        try:
            project_dir = Path(project.output_dir)
            voice_step = project.steps.get("voice")
            if not voice_step or not voice_step.artifacts:
                raise ValueError("No voice audio found")

            voice_path = voice_step.artifacts[0]

            music_fetcher = MusicFetcher()
            audio_mixer = AudioMixer()

            self._notify_progress(project_id, "music", StepStatus.RUNNING, 30, "Downloading music track...")
            music_track = music_fetcher.fetch_music(project.config.style.value)

            if music_track:
                self._notify_progress(project_id, "music", StepStatus.RUNNING, 60, "Mixing audio...")
                output_path = str(project_dir / "narration.mp3")
                audio_mixer.mix(
                    voice_path,
                    music_track.path,
                    output_path,
                    music_volume=project.config.music_volume
                )

                self.project_manager.update_step(
                    project_id, "music",
                    artifacts=[output_path, music_track.path]
                )
            else:
                self.project_manager.update_step(
                    project_id, "music",
                    artifacts=[voice_path]
                )

            self._notify_progress(project_id, "music", StepStatus.COMPLETE, 100, "Music added")
            self.project_manager.update_status(project_id, ProjectStatus.MUSIC)

            return self.project_manager.get(project_id)

        except Exception as e:
            self._notify_progress(project_id, "music", StepStatus.FAILED, 0, str(e))
            self.project_manager.set_error(project_id, str(e))
            return None

    async def run_visuals_step(self, project_id: str) -> Optional[Project]:
        project = self.project_manager.get(project_id)
        if not project or not project.script:
            return None

        self._notify_progress(project_id, "visuals", StepStatus.RUNNING, 0, "Fetching visuals...")

        try:
            project_dir = Path(project.output_dir)

            if project.config.use_talking_head and project.config.avatar_path:
                self._notify_progress(project_id, "visuals", StepStatus.RUNNING, 50, "Generating talking head...")
                talking_head_mgr = TalkingHeadManager()

                audio_step = project.steps.get("music") or project.steps.get("voice")
                audio_path = audio_step.artifacts[0] if audio_step and audio_step.artifacts else None

                if audio_path:
                    output_path = str(project_dir / "talking_head.mp4")
                    talking_head_mgr.generate(
                        project.config.avatar_path,
                        audio_path,
                        output_path
                    )
                    footage_paths = [output_path]
                else:
                    footage_paths = []
            else:
                footage_mgr = StockFootageManager(vertical=project.config.is_short)
                footage_paths = []

                visual_cues = [seg.visual_cue for seg in project.script.segments if seg.visual_cue]
                total = len(visual_cues)

                for i, cue in enumerate(visual_cues):
                    self._notify_progress(
                        project_id, "visuals", StepStatus.RUNNING,
                        int((i / total) * 100),
                        f"Fetching visual {i+1}/{total}..."
                    )
                    footage = footage_mgr.fetch_footage(cue)
                    if footage:
                        footage_paths.append(footage.path)

            self.project_manager.update_step(
                project_id, "visuals",
                artifacts=footage_paths
            )

            self._notify_progress(project_id, "visuals", StepStatus.COMPLETE, 100, f"Fetched {len(footage_paths)} visuals")
            self.project_manager.update_status(project_id, ProjectStatus.VISUALS)

            return self.project_manager.get(project_id)

        except Exception as e:
            self._notify_progress(project_id, "visuals", StepStatus.FAILED, 0, str(e))
            self.project_manager.set_error(project_id, str(e))
            return None

    async def run_assembly_step(self, project_id: str) -> Optional[Project]:
        project = self.project_manager.get(project_id)
        if not project:
            return None

        self._notify_progress(project_id, "assembly", StepStatus.RUNNING, 0, "Assembling video...")

        try:
            project_dir = Path(project.output_dir)

            music_step = project.steps.get("music")
            voice_step = project.steps.get("voice")
            visuals_step = project.steps.get("visuals")

            audio_path = None
            if music_step and music_step.artifacts:
                audio_path = music_step.artifacts[0]
            elif voice_step and voice_step.artifacts:
                audio_path = voice_step.artifacts[0]

            footage_paths = visuals_step.artifacts if visuals_step and visuals_step.artifacts else []

            assembly_config = AssemblyConfig.for_short() if project.config.is_short else AssemblyConfig()
            assembler = VideoAssembler(assembly_config)

            self._notify_progress(project_id, "assembly", StepStatus.RUNNING, 50, "Encoding video...")

            output_path = str(project_dir / "video.mp4")
            key_phrases = project.script.key_phrases if project.script else []

            assembler.assemble(
                audio_path=audio_path,
                footage_paths=footage_paths,
                output_path=output_path,
                key_phrases=key_phrases
            )

            self.project_manager.update_step(
                project_id, "assembly",
                artifacts=[output_path]
            )

            self._notify_progress(project_id, "assembly", StepStatus.COMPLETE, 100, "Video assembled")
            self.project_manager.update_status(project_id, ProjectStatus.ASSEMBLY)

            return self.project_manager.get(project_id)

        except Exception as e:
            self._notify_progress(project_id, "assembly", StepStatus.FAILED, 0, str(e))
            self.project_manager.set_error(project_id, str(e))
            return None

    async def run_thumbnail_step(self, project_id: str) -> Optional[Project]:
        project = self.project_manager.get(project_id)
        if not project or not project.script:
            return None

        self._notify_progress(project_id, "thumbnail", StepStatus.RUNNING, 0, "Creating thumbnail...")

        try:
            project_dir = Path(project.output_dir)

            assembly_config = AssemblyConfig.for_short() if project.config.is_short else AssemblyConfig()
            assembler = VideoAssembler(assembly_config)

            output_path = str(project_dir / "thumbnail.png")
            assembler.create_thumbnail(
                text=project.script.thumbnail_text or project.script.title,
                output_path=output_path
            )

            self.project_manager.update_step(
                project_id, "thumbnail",
                artifacts=[output_path]
            )

            self._save_manifest(project)

            self._notify_progress(project_id, "thumbnail", StepStatus.COMPLETE, 100, "Thumbnail created")
            self.project_manager.update_status(project_id, ProjectStatus.COMPLETE)

            return self.project_manager.get(project_id)

        except Exception as e:
            self._notify_progress(project_id, "thumbnail", StepStatus.FAILED, 0, str(e))
            self.project_manager.set_error(project_id, str(e))
            return None

    def _save_manifest(self, project: Project):
        if not project.output_dir or not project.script:
            return

        manifest = {
            "topic": project.config.topic,
            "title": project.script.title,
            "description": project.script.description,
            "tags": project.script.tags,
            "style": project.config.style.value,
            "format": project.config.format.value,
            "created_at": project.created_at.isoformat(),
            "files": {
                step: project.steps[step].artifacts
                for step in project.steps
                if project.steps[step].artifacts
            }
        }

        manifest_path = Path(project.output_dir) / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    async def run_all(self, project_id: str) -> Optional[Project]:
        self._pause_requested = False
        self._current_project_id = project_id

        steps = [
            ("script", self.run_script_step),
            ("voice", self.run_voice_step),
            ("music", self.run_music_step),
            ("visuals", self.run_visuals_step),
            ("assembly", self.run_assembly_step),
            ("thumbnail", self.run_thumbnail_step),
        ]

        project = self.project_manager.get(project_id)
        if not project:
            return None

        for step_name, step_func in steps:
            if self._pause_requested:
                self.project_manager.update_status(project_id, ProjectStatus.PAUSED)
                break

            step = project.steps.get(step_name)
            if step and step.status in (StepStatus.PENDING, StepStatus.FAILED):
                result = await step_func(project_id)
                if not result:
                    break
                project = result

        self._current_project_id = None
        return self.project_manager.get(project_id)

    async def run_step(self, project_id: str, step_name: str) -> Optional[Project]:
        step_funcs = {
            "script": self.run_script_step,
            "voice": self.run_voice_step,
            "music": self.run_music_step,
            "visuals": self.run_visuals_step,
            "assembly": self.run_assembly_step,
            "thumbnail": self.run_thumbnail_step,
        }

        func = step_funcs.get(step_name)
        if not func:
            return None

        return await func(project_id)
