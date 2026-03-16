import subprocess
import shutil
import json
import time
import requests
from pathlib import Path
from dataclasses import dataclass

from .config import config
from .infinitetalk import InfiniteTalkGenerator, get_cast_member, CAST


AZURE_EMOTION_MAP = {
    "excited": {"style": "excited", "styledegree": "1.3"},
    "frustrated": {"style": "angry", "styledegree": "0.8"},
    "calm": {"style": "friendly", "styledegree": "0.8"},
    "passionate": {"style": "excited", "styledegree": "1.5"},
    "reflective": {"style": "sad", "styledegree": "0.6"},
    "sad": {"style": "sad", "styledegree": "1.0"},
    "angry": {"style": "angry", "styledegree": "1.2"},
    "hopeful": {"style": "hopeful", "styledegree": "1.0"},
    "friendly": {"style": "friendly", "styledegree": "1.0"},
    "whispering": {"style": "whispering", "styledegree": "1.0"},
    "shouting": {"style": "shouting", "styledegree": "1.5"},
    "default": {"style": "friendly", "styledegree": "1.0"},
}

AZURE_AVATAR_VOICES = {
    "female": "en-US-JaneNeural",
    "male": "en-US-GuyNeural",
    "female_alt": "en-US-AriaNeural",
    "male_alt": "en-US-DavisNeural",
    "jane": "en-US-JaneNeural",
    "jenny": "en-US-JennyNeural",
    "aria": "en-US-AriaNeural",
    "sara": "en-US-SaraNeural",
    "guy": "en-US-GuyNeural",
    "davis": "en-US-DavisNeural",
    "jason": "en-US-JasonNeural",
    "tony": "en-US-TonyNeural",
}

AZURE_AVATAR_CHARACTERS = {
    "harry": "harry",
    "jeff": "jeff",
    "lisa": "lisa",
    "lori": "lori",
    "max": "max",
    "meg": "meg",
}

AZURE_AVATAR_STYLES = {
    "harry": ["business", "casual", "youthful"],
    "jeff": ["business", "formal"],
    "lisa": ["casual-sitting", "graceful-sitting", "graceful-standing", "technical-sitting", "technical-standing"],
    "lori": ["casual", "graceful", "formal"],
    "max": ["business", "casual", "formal"],
    "meg": ["formal", "casual", "business"],
}

AZURE_PHOTO_AVATARS = {
    "anika": "vasa-1",
    "rachel": "vasa-1",
}


@dataclass
class TalkingHeadConfig:
    fps: int = 30
    inference_steps: int = 20
    guidance_scale: float = 3.5
    resolution: tuple[int, int] = (512, 512)


class AzureAvatarGenerator:
    def __init__(self, voice: str = "jane", avatar: str = "anika", avatar_style: str = "", use_photo_avatar: bool = True):
        self.speech_key = config.azure_speech_key
        self.region = config.azure_speech_region
        self.endpoint = config.azure_speech_endpoint or f"https://{self.region}.api.cognitive.microsoft.com"
        self.voice = AZURE_AVATAR_VOICES.get(voice, voice)
        self.avatar = avatar
        self.avatar_style = avatar_style
        self.use_photo_avatar = use_photo_avatar or avatar in AZURE_PHOTO_AVATARS
        self._available = None

    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = bool(self.speech_key and self.region)
        return self._available

    def _parse_emotion_marker(self, text: str) -> tuple[str, str]:
        import re
        emotion_pattern = r'^\[(\w+)\]\s*'
        match = re.match(emotion_pattern, text)
        if match:
            emotion = match.group(1).lower()
            clean_text = re.sub(emotion_pattern, '', text)
            return emotion, clean_text
        return "default", text

    def _build_ssml(self, text: str, emotion: str = "default") -> str:
        emotion_config = AZURE_EMOTION_MAP.get(emotion, AZURE_EMOTION_MAP["default"])
        style = emotion_config["style"]
        degree = emotion_config["styledegree"]

        ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
    xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US">
    <voice name="{self.voice}">
        <prosody rate="+15%" pitch="+3%">
            <mstts:express-as style="{style}" styledegree="{degree}">
                {text}
            </mstts:express-as>
        </prosody>
    </voice>
</speak>'''
        return ssml

    def _build_ssml_segments(self, segments: list[dict]) -> str:
        parts = []

        for seg in segments:
            text = seg["text"] if isinstance(seg, dict) else seg
            emotion, clean_text = self._parse_emotion_marker(text)
            emotion_config = AZURE_EMOTION_MAP.get(emotion, AZURE_EMOTION_MAP["default"])
            style = emotion_config["style"]
            degree = emotion_config["styledegree"]

            parts.append(f'''        <prosody rate="+15%" pitch="+3%">
            <mstts:express-as style="{style}" styledegree="{degree}">
                {clean_text}
            </mstts:express-as>
        </prosody>
        <break time="200ms"/>''')

        ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
    xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US">
    <voice name="{self.voice}">
{chr(10).join(parts)}
    </voice>
</speak>'''
        return ssml

    def generate(
        self,
        text: str,
        output_path: str,
        emotion: str = "default",
        segments: list[dict] = None,
    ) -> str:
        if not self.available:
            raise RuntimeError(
                "Azure Speech not configured. Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION."
            )

        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        if segments:
            ssml = self._build_ssml_segments(segments)
        else:
            ssml = self._build_ssml(text, emotion)

        job_id = self._submit_avatar_job(ssml, output_path)
        video_url = self._wait_for_completion(job_id)
        self._download_video(video_url, output_path)

        return output_path

    def _submit_avatar_job(self, ssml: str, output_path: str) -> str:
        import uuid
        job_id = str(uuid.uuid4())
        url = f"{self.endpoint}/avatar/batchsyntheses/{job_id}?api-version=2024-08-01"

        headers = {
            "Ocp-Apim-Subscription-Key": self.speech_key,
            "Content-Type": "application/json",
        }

        if self.use_photo_avatar:
            avatar_config = {
                "photoAvatarBaseModel": AZURE_PHOTO_AVATARS.get(self.avatar, "vasa-1"),
                "talkingAvatarCharacter": self.avatar,
                "talkingAvatarStyle": "",
                "videoFormat": "mp4",
                "videoCodec": "h264",
                "subtitleType": "soft_embedded",
                "backgroundColor": "#00FF00FF",
            }
            print(f"    Using Photo Avatar with VASA-1: {self.avatar}")
        else:
            avatar_config = {
                "talkingAvatarCharacter": self.avatar,
                "talkingAvatarStyle": self.avatar_style,
                "videoFormat": "mp4",
                "videoCodec": "h264",
                "subtitleType": "soft_embedded",
                "backgroundColor": "#00FF00FF",
            }
            print(f"    Using Standard Avatar: {self.avatar} ({self.avatar_style})")

        payload = {
            "synthesisConfig": {
                "voice": self.voice,
            },
            "inputKind": "SSML",
            "inputs": [{"content": ssml}],
            "avatarConfig": avatar_config,
        }

        print(f"    Submitting Azure Avatar job...")
        print(f"    Job ID: {job_id}")
        response = requests.put(url, headers=headers, json=payload)

        if response.status_code not in (200, 201, 202):
            raise RuntimeError(f"Azure Avatar submission failed: {response.status_code} {response.text}")

        return job_id

    def _wait_for_completion(self, job_id: str, timeout: int = 600, poll_interval: int = 5) -> str:
        url = f"{self.endpoint}/avatar/batchsyntheses/{job_id}?api-version=2024-08-01"

        headers = {
            "Ocp-Apim-Subscription-Key": self.speech_key,
        }

        start_time = time.time()
        while time.time() - start_time < timeout:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"Azure Avatar status check failed: {response.status_code}")

            data = response.json()
            status = data.get("status")

            if status == "Succeeded":
                outputs = data.get("outputs", {})
                video_url = outputs.get("result")
                if video_url:
                    print(f"    Avatar generation complete!")
                    return video_url
                raise RuntimeError("No video URL in completed job")

            elif status == "Failed":
                error = data.get("properties", {}).get("error", {})
                raise RuntimeError(f"Azure Avatar generation failed: {error}")

            elapsed = int(time.time() - start_time)
            print(f"    Status: {status} ({elapsed}s elapsed)...")
            time.sleep(poll_interval)

        raise RuntimeError(f"Azure Avatar generation timed out after {timeout}s")

    def _download_video(self, url: str, output_path: str):
        print(f"    Downloading avatar video...")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"    Saved: {output_path}")


class MEMOGenerator:
    def __init__(self, memo_path: str = None, config: TalkingHeadConfig = None):
        self.memo_path = Path(memo_path) if memo_path else self._find_memo()
        self.config = config or TalkingHeadConfig()
        self._available = None

    def _find_memo(self) -> Path:
        possible_paths = [
            Path.home() / "memo",
            Path.home() / "dev" / "memo",
            Path("/opt/memo"),
            Path(__file__).parent.parent / "memo",
        ]
        for p in possible_paths:
            if (p / "inference.py").exists():
                return p
        return Path.home() / "memo"

    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = (
                self.memo_path.exists() and
                (self.memo_path / "inference.py").exists()
            )
        return self._available

    def generate(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        fps: int = None,
        inference_steps: int = None,
    ) -> str:
        if not self.available:
            raise RuntimeError(
                f"MEMO not found at {self.memo_path}. "
                "Install from: https://github.com/memoavatar/memo"
            )

        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        fps = fps or self.config.fps
        steps = inference_steps or self.config.inference_steps

        cmd = [
            "python", str(self.memo_path / "inference.py"),
            "--config", str(self.memo_path / "configs" / "inference.yaml"),
            "--input_image", str(image_path),
            "--input_audio", str(audio_path),
            "--output_dir", str(output_dir),
            "--fps", str(fps),
            "--inference_steps", str(steps),
        ]

        print(f"    Running MEMO inference...")
        print(f"    Image: {image_path}")
        print(f"    Audio: {audio_path}")

        result = subprocess.run(
            cmd,
            cwd=str(self.memo_path),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"MEMO failed: {result.stderr}")

        generated_video = output_dir / "output.mp4"
        if generated_video.exists() and str(generated_video) != output_path:
            shutil.move(str(generated_video), output_path)

        return output_path


class Hallo3Generator:
    def __init__(self, hallo_path: str = None, config: TalkingHeadConfig = None):
        self.hallo_path = Path(hallo_path) if hallo_path else self._find_hallo()
        self.config = config or TalkingHeadConfig()
        self._available = None

    def _find_hallo(self) -> Path:
        possible_paths = [
            Path.home() / "hallo3",
            Path.home() / "dev" / "hallo3",
            Path("/opt/hallo3"),
            Path(__file__).parent.parent / "hallo3",
        ]
        for p in possible_paths:
            if (p / "inference.py").exists():
                return p
        return Path.home() / "hallo3"

    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = (
                self.hallo_path.exists() and
                (self.hallo_path / "inference.py").exists()
            )
        return self._available

    def generate(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        fps: int = None,
    ) -> str:
        if not self.available:
            raise RuntimeError(
                f"Hallo3 not found at {self.hallo_path}. "
                "Install from: https://github.com/fudan-generative-vision/hallo3"
            )

        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        fps = fps or self.config.fps

        cmd = [
            "python", str(self.hallo_path / "inference.py"),
            "--ref_img_path", str(image_path),
            "--audio_path", str(audio_path),
            "--output_path", str(output_path),
            "--fps", str(fps),
        ]

        print(f"    Running Hallo3 inference...")
        print(f"    Image: {image_path}")
        print(f"    Audio: {audio_path}")

        result = subprocess.run(
            cmd,
            cwd=str(self.hallo_path),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Hallo3 failed: {result.stderr}")

        return output_path


class TalkingHeadManager:
    def __init__(self, backend: str = "infinitetalk", avatar_voice: str = "jane", avatar_character: str = "rachel", avatar_style: str = "", use_photo_avatar: bool = True):
        self.backend = backend
        self.avatar_voice = avatar_voice
        self.avatar_character = avatar_character
        self.avatar_style = avatar_style
        self.use_photo_avatar = use_photo_avatar
        self._memo = None
        self._hallo = None
        self._azure = None
        self._infinitetalk = None

    @property
    def memo(self) -> MEMOGenerator:
        if self._memo is None:
            self._memo = MEMOGenerator()
        return self._memo

    @property
    def hallo(self) -> Hallo3Generator:
        if self._hallo is None:
            self._hallo = Hallo3Generator()
        return self._hallo

    @property
    def azure(self) -> AzureAvatarGenerator:
        if self._azure is None:
            self._azure = AzureAvatarGenerator(
                voice=self.avatar_voice,
                avatar=self.avatar_character,
                avatar_style=self.avatar_style,
                use_photo_avatar=self.use_photo_avatar,
            )
        return self._azure

    @property
    def infinitetalk(self) -> InfiniteTalkGenerator:
        if self._infinitetalk is None:
            self._infinitetalk = InfiniteTalkGenerator()
        return self._infinitetalk

    @property
    def available(self) -> bool:
        return self.infinitetalk.available or self.azure.available or self.memo.available or self.hallo.available

    def get_backend(self) -> str:
        if self.backend != "auto":
            return self.backend
        if self.infinitetalk.available:
            return "infinitetalk"
        if self.azure.available:
            return "azure"
        if self.memo.available:
            return "memo"
        if self.hallo.available:
            return "hallo"
        return None

    def generate(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        **kwargs,
    ) -> str:
        backend = self.get_backend()

        if backend is None:
            raise RuntimeError(
                "No talking head backend available. Options:\n"
                "  InfiniteTalk: Set RUNPOD_API_KEY (RunPod serverless)\n"
                "  Azure Avatar: Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION\n"
                "  MEMO: https://github.com/memoavatar/memo (requires GPU)\n"
                "  Hallo3: https://github.com/fudan-generative-vision/hallo3 (requires GPU)"
            )

        if backend == "infinitetalk":
            prompt = kwargs.pop("prompt", "A person speaking naturally")
            speaker = kwargs.pop("speaker", self.avatar_character)
            cast_member = get_cast_member(speaker)
            if image_path and Path(image_path).exists():
                img = image_path
            elif Path(cast_member.image_path).exists():
                img = cast_member.image_path
            else:
                img = CAST["rachel"].image_path
            return self.infinitetalk.generate(img, audio_path, output_path, prompt=cast_member.prompt)
        elif backend == "azure":
            text = kwargs.pop("text", None)
            segments = kwargs.pop("segments", None)
            emotion = kwargs.pop("emotion", "default")
            if not text and not segments:
                raise RuntimeError("Azure Avatar requires 'text' or 'segments' parameter")
            return self.azure.generate(text or "", output_path, emotion=emotion, segments=segments)
        elif backend == "memo":
            return self.memo.generate(image_path, audio_path, output_path, **kwargs)
        elif backend == "hallo":
            return self.hallo.generate(image_path, audio_path, output_path, **kwargs)
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def generate_multi_speaker(
        self,
        segments: list[dict],
        output_path: str,
    ) -> str:
        backend = self.get_backend()
        if backend != "infinitetalk":
            raise RuntimeError("generate_multi_speaker only works with InfiniteTalk backend")
        return self.infinitetalk.generate_multi_speaker(segments, output_path)

    def generate_from_script(self, script, output_path: str) -> str:
        backend = self.get_backend()
        if backend == "azure":
            segments = [{"text": script.hook}]
            for seg in script.segments:
                segments.append({"text": seg.text})
            segments.append({"text": script.outro})
            return self.azure.generate("", output_path, segments=segments)
        else:
            raise RuntimeError("generate_from_script requires pre-generated audio for non-Azure backends")
