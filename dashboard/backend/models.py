from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    SCRIPT = "script"
    VOICE = "voice"
    MUSIC = "music"
    VISUALS = "visuals"
    ASSEMBLY = "assembly"
    THUMBNAIL = "thumbnail"
    COMPLETE = "complete"
    PAUSED = "paused"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class VideoStyle(str, Enum):
    EDUCATIONAL = "educational"
    STORYTELLING = "storytelling"
    LISTICLE = "listicle"
    DOCUMENTARY = "documentary"
    MOTIVATIONAL = "motivational"
    RELAXING = "relaxing"
    TURBOENCABULATOR = "turboencabulator"


class ScriptFormat(str, Enum):
    MONOLOGUE = "monologue"
    INTERVIEW = "interview"
    PANEL = "panel"
    DEBATE = "debate"


class TTSEngine(str, Enum):
    AUTO = "auto"
    EDGE = "edge"
    OPENAI = "openai"
    ELEVENLABS = "elevenlabs"
    BARK = "bark"
    FISH = "fish"
    XTTS = "xtts"


class VoicePreset(str, Enum):
    MALE_CASUAL = "male_casual"
    FEMALE_CASUAL = "female_casual"
    MALE_NARRATOR = "male_narrator"
    FEMALE_NARRATOR = "female_narrator"
    MALE_WARM = "male_warm"
    FEMALE_WARM = "female_warm"
    MALE_BRITISH = "male_british"
    FEMALE_BRITISH = "female_british"
    MALE_DEEP = "male_deep"
    FEMALE_PROFESSIONAL = "female_professional"


class VoiceStyle(str, Enum):
    DOCUMENTARY = "documentary"
    ENERGETIC = "energetic"
    CALM = "calm"
    CONVERSATIONAL = "conversational"
    TURBOENCABULATOR = "turboencabulator"


class ProjectConfig(BaseModel):
    topic: str
    style: VideoStyle = VideoStyle.EDUCATIONAL
    format: ScriptFormat = ScriptFormat.MONOLOGUE
    duration_minutes: int = Field(default=8, ge=1, le=60)
    voice: VoicePreset = VoicePreset.FEMALE_NARRATOR
    voice_style: VoiceStyle = VoiceStyle.DOCUMENTARY
    tts_engine: TTSEngine = TTSEngine.FISH
    chaotic_level: int = Field(default=3, ge=1, le=5)
    seed: Optional[str] = None
    transcript: Optional[str] = None
    cast: List[str] = Field(default_factory=list)
    add_music: bool = True
    music_volume: float = Field(default=0.12, ge=0.0, le=1.0)
    is_short: bool = False
    use_talking_head: bool = False
    avatar_path: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class PipelineStep(BaseModel):
    name: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    message: str = ""
    artifacts: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class ScriptSegment(BaseModel):
    text: str
    visual_cue: str = ""
    speaker: Optional[str] = None


class VideoScript(BaseModel):
    title: str
    hook: str
    segments: List[ScriptSegment]
    outro: str
    thumbnail_text: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    key_phrases: List[str] = Field(default_factory=list)


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    config: ProjectConfig
    status: ProjectStatus = ProjectStatus.DRAFT
    steps: Dict[str, PipelineStep] = Field(default_factory=dict)
    script: Optional[VideoScript] = None
    output_dir: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None

    def model_post_init(self, __context):
        if not self.steps:
            self.steps = {
                "script": PipelineStep(name="Script Generation"),
                "voice": PipelineStep(name="Voice Generation"),
                "music": PipelineStep(name="Music"),
                "visuals": PipelineStep(name="Visuals"),
                "assembly": PipelineStep(name="Assembly"),
                "thumbnail": PipelineStep(name="Thumbnail"),
            }


class CreateProjectRequest(BaseModel):
    config: ProjectConfig


class UpdateConfigRequest(BaseModel):
    config: ProjectConfig


class UpdateScriptRequest(BaseModel):
    script: VideoScript


class RegenerateScriptRequest(BaseModel):
    model: Optional[str] = None
    prompt_override: Optional[str] = None


class ProgressUpdate(BaseModel):
    project_id: str
    step: str
    status: StepStatus
    progress: float
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


VOICE_PERSONAS = {
    "host_male": ["drew", "josh", "matthew", "daniel", "adam"],
    "host_female": ["rachel", "sarah", "charlotte", "grace", "nicole"],
    "expert_male": ["clyde", "paul", "thomas", "george", "james", "arnold"],
    "expert_female": ["domi", "emily", "elli", "dorothy", "matilda", "serena"],
    "contrarian_male": ["fin", "patrick", "harry", "liam", "jeremy", "ethan"],
    "contrarian_female": ["gigi", "freya", "jessie", "mimi", "glinda"],
    "wildcard": ["charlie", "callum", "joseph", "michael", "ryan", "sam", "giovanni"],
}


CHAOTIC_THRESHOLDS = {
    1: {"calm": 0.50, "building": 0.70, "passionate": 0.85, "emphatic": 0.95},
    2: {"calm": 0.30, "building": 0.50, "passionate": 0.70, "emphatic": 0.85},
    3: {"calm": 0.15, "building": 0.30, "passionate": 0.50, "emphatic": 0.75},
    4: {"calm": 0.08, "building": 0.18, "passionate": 0.35, "emphatic": 0.55},
    5: {"calm": 0.03, "building": 0.08, "passionate": 0.18, "emphatic": 0.30},
}


class ConfigOptions(BaseModel):
    styles: List[str] = [s.value for s in VideoStyle]
    formats: List[str] = [f.value for f in ScriptFormat]
    tts_engines: List[str] = [e.value for e in TTSEngine]
    voice_presets: List[str] = [v.value for v in VoicePreset]
    voice_styles: List[str] = [s.value for s in VoiceStyle]
    voice_personas: Dict[str, List[str]] = VOICE_PERSONAS
    chaotic_thresholds: Dict[int, Dict[str, float]] = CHAOTIC_THRESHOLDS
