import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


@dataclass
class Config:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    pexels_api_key: str = field(default_factory=lambda: os.getenv("PEXELS_API_KEY", ""))
    pixabay_api_key: str = field(default_factory=lambda: os.getenv("PIXABAY_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    elevenlabs_api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    fish_audio_api_key: str = field(default_factory=lambda: os.getenv("FISH_AUDIO_API_KEY", ""))
    fish_speech_url: str = field(default_factory=lambda: os.getenv("FISH_SPEECH_URL", "http://127.0.0.1:8080"))
    azure_speech_key: str = field(default_factory=lambda: os.getenv("AZURE_SPEECH_KEY", ""))
    azure_speech_region: str = field(default_factory=lambda: os.getenv("AZURE_SPEECH_REGION", "eastus"))
    azure_speech_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_SPEECH_ENDPOINT", ""))
    azure_openai_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    azure_openai_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_KEY", ""))
    azure_openai_audio_deployment: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_AUDIO_DEPLOYMENT", "gpt-4o-mini-audio"))
    azure_openai_foundry_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_FOUNDRY_ENDPOINT", ""))
    azure_openai_foundry_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_FOUNDRY_KEY", ""))
    azure_openai_script_deployment: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_SCRIPT_DEPLOYMENT", "gpt-5.4"))
    azure_dalle_deployment: str = field(default_factory=lambda: os.getenv("AZURE_DALLE_DEPLOYMENT", "dalle3"))
    azure_storage_connection_string: str = field(default_factory=lambda: os.getenv("AZURE_STORAGE_CONNECTION_STRING", ""))
    azure_storage_container: str = field(default_factory=lambda: os.getenv("AZURE_STORAGE_CONTAINER", "media"))

    runpod_api_key: str = field(default_factory=lambda: os.getenv("RUNPOD_API_KEY", ""))
    runpod_infinitetalk_endpoint: str = field(default_factory=lambda: os.getenv("RUNPOD_INFINITETALK_ENDPOINT", "smu7s0ky1u8cie"))

    output_dir: str = field(default_factory=lambda: str(Path(__file__).parent / "output"))
    assets_dir: str = field(default_factory=lambda: str(Path(__file__).parent / "assets"))
    cache_dir: str = field(default_factory=lambda: str(Path(__file__).parent / "cache"))

    default_voice: str = "en-US-ChristopherNeural"
    video_width: int = 1920
    video_height: int = 1080
    fps: int = 30

    target_duration_seconds: int = 480
    words_per_minute: int = 150

    def __post_init__(self):
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.assets_dir).mkdir(parents=True, exist_ok=True)
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.cache_dir, "footage").mkdir(parents=True, exist_ok=True)
        Path(self.cache_dir, "audio").mkdir(parents=True, exist_ok=True)


config = Config()
