import asyncio
import hashlib
import re
from pathlib import Path

from .config import config


FISH_EMOTION_MAP = {
    "laughs": "(laughing)",
    "laughs maniacally": "(hysterical)(laughing)",
    "chuckles": "(chuckling)",
    "sighs": "(sighing)",
    "gasps": "(gasping)",
    "screaming": "(screaming)",
    "screams": "(screaming)",
    "shouting": "(shouting)",
    "shouts": "(shouting)",
    "whispering": "(whispering)",
    "whispers": "(whispering)",
    "frustrated": "(frustrated)",
    "angry": "(angry)",
    "excited": "(excited)",
    "nervous": "(nervous)",
    "scared": "(scared)",
    "worried": "(worried)",
    "confused": "(confused)",
    "surprised": "(surprised)",
    "sad": "(sad)",
    "happy": "(happy)",
    "sarcastic": "(sarcastic)",
    "sobbing": "(sobbing)",
    "crying": "(crying loudly)",
    "panting": "(panting)",
    "groaning": "(groaning)",
    "yawning": "(yawning)",
}

FISH_INTENSITY_MARKERS = {
    "calm": "(calm)",
    "building": "(curious)(determined)",
    "passionate": "(excited)(confident)",
    "emphatic": "(angry)(shouting)",
    "screaming": "(hysterical)(screaming)",
}

FISH_VOICE_POOL = {
    "host_female": ["61e7f07e64e84b788ef8b8b5b5d52cb5"],
    "host_male": ["bf8d0c9a85c14e8c88f36c8c8c5f9a7d"],
    "expert_female": ["a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"],
    "expert_male": ["d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9"],
    "contrarian_female": ["c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4"],
    "contrarian_male": ["f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7"],
}

VOICE_PRESETS = {
    "male_casual": "en-US-AndrewNeural",
    "female_casual": "en-US-EmmaNeural",
    "male_narrator": "en-US-BrianNeural",
    "female_narrator": "en-US-AvaNeural",
    "male_warm": "en-US-ChristopherNeural",
    "female_warm": "en-US-JennyNeural",
    "male_british": "en-GB-RyanNeural",
    "female_british": "en-GB-SoniaNeural",
    "male_deep": "en-US-GuyNeural",
    "female_professional": "en-US-AriaNeural",
    "jane": "en-US-JaneNeural",
    "jenny": "en-US-JennyNeural",
    "aria": "en-US-AriaNeural",
    "sara": "en-US-SaraNeural",
    "guy": "en-US-GuyNeural",
    "davis": "en-US-DavisNeural",
    "jason": "en-US-JasonNeural",
    "tony": "en-US-TonyNeural",
}

EDGE_EMOTION_STYLES = {
    "excited": {"rate": "+20%", "pitch": "+5Hz"},
    "frustrated": {"rate": "+10%", "pitch": "-3Hz"},
    "calm": {"rate": "-5%", "pitch": "-2Hz"},
    "passionate": {"rate": "+15%", "pitch": "+4Hz"},
    "reflective": {"rate": "-10%", "pitch": "-4Hz"},
    "sad": {"rate": "-15%", "pitch": "-5Hz"},
    "angry": {"rate": "+25%", "pitch": "+2Hz"},
    "hopeful": {"rate": "+5%", "pitch": "+3Hz"},
    "friendly": {"rate": "+10%", "pitch": "+2Hz"},
    "whispering": {"rate": "-20%", "pitch": "-6Hz"},
    "shouting": {"rate": "+30%", "pitch": "+6Hz"},
    "default": {"rate": "+15%", "pitch": "+3Hz"},
}

VOICE_STYLES = {
    "documentary": {"rate": "-5%", "pitch": "-2Hz"},
    "energetic": {"rate": "+10%", "pitch": "+2Hz"},
    "calm": {"rate": "-10%", "pitch": "-3Hz"},
    "conversational": {"rate": "+0%", "pitch": "+0Hz"},
    "turboencabulator": {"rate": "+5%", "pitch": "+2Hz"},
}

OPENAI_VOICE_PRESETS = {
    "male_casual": "onyx",
    "female_casual": "nova",
    "male_narrator": "echo",
    "female_narrator": "coral",
    "male_warm": "ash",
    "female_warm": "shimmer",
    "male_british": "fable",
    "female_british": "sage",
    "male_deep": "onyx",
    "female_professional": "alloy",
}


class VoiceGenerator:
    def __init__(self, voice: str = None, style: str = "documentary"):
        self.voice = voice or "female_narrator"
        if self.voice in VOICE_PRESETS:
            self.voice = VOICE_PRESETS[self.voice]
        self.style_name = style
        self.style = VOICE_STYLES.get(style, VOICE_STYLES["documentary"])

    async def generate(self, text: str, output_path: str = None) -> str:
        import edge_tts

        if output_path is None:
            text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
            output_path = str(Path(config.cache_dir) / "audio" / f"{text_hash}.mp3")

        if Path(output_path).exists():
            return output_path

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=self.style["rate"],
            pitch=self.style["pitch"],
        )

        await communicate.save(output_path)
        return output_path

    async def generate_segments(self, segments: list[str], output_dir: str = None) -> list[str]:
        if output_dir is None:
            output_dir = Path(config.cache_dir) / "audio"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        paths = []
        for i, text in enumerate(segments):
            path = str(output_dir / f"segment_{i:03d}.mp3")
            await self.generate(text, path)
            paths.append(path)

        return paths

    def generate_sync(self, text: str, output_path: str = None) -> str:
        return asyncio.run(self.generate(text, output_path))

    @staticmethod
    def list_voices() -> list[str]:
        return list(VOICE_PRESETS.keys())

    def _parse_emotion_marker(self, text: str) -> tuple[str, str]:
        emotion_pattern = r'^\[(\w+)\]\s*'
        match = re.match(emotion_pattern, text)
        if match:
            emotion = match.group(1).lower()
            clean_text = re.sub(emotion_pattern, '', text)
            return emotion, clean_text
        return "default", text

    async def generate_with_emotion(self, text: str, output_path: str, emotion: str = "default") -> str:
        import edge_tts

        style = EDGE_EMOTION_STYLES.get(emotion, EDGE_EMOTION_STYLES["default"])

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if Path(output_path).exists():
            Path(output_path).unlink()

        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=style["rate"],
            pitch=style["pitch"],
        )

        await communicate.save(output_path)
        return output_path

    def generate_turboencabulator(self, segments: list[dict], output_dir: str) -> list[str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        total_segments = len(segments)
        paths = []

        import nest_asyncio
        nest_asyncio.apply()

        async def process_all():
            for i, segment in enumerate(segments):
                text = segment["text"] if isinstance(segment, dict) else segment
                emotion, clean_text = self._parse_emotion_marker(text)

                path = str(output_dir / f"segment_{i:03d}.mp3")

                emotion_label = emotion.capitalize() if emotion != "default" else "Neutral"
                print(f"        [{i+1}/{total_segments}] {emotion_label}: {clean_text[:50]}...")

                await self.generate_with_emotion(clean_text, path, emotion)
                paths.append(path)

        asyncio.run(process_all())
        return paths


TURBO_INSTRUCTIONS = {
    "calm": """You are a calm, professional documentary narrator. Speak slowly and clearly, like a PBS documentary host.
Measured pace. Neutral tone. No emotion. Just presenting facts objectively.""",

    "building": """You are a lecturer who is becoming increasingly engaged with your topic.
Start to emphasize key words. Let some genuine interest creep into your voice.
You're not emotional yet, but you're clearly invested in what you're explaining.
Speed up slightly. Add subtle emphasis on important terms.""",

    "passionate": """You are a passionate TED talk speaker making your core argument.
Your voice should RISE and FALL dramatically. Emphasize IMPORTANT words by saying them LOUDER.
Speak faster during exciting parts. Pause... for effect.
You BELIEVE what you're saying. Let that conviction show.
Example delivery: "And THIS is where it gets INTERESTING..." with the word "THIS" and "INTERESTING" noticeably louder.""",

    "emphatic": """You are an OUTRAGED pundit on cable news who cannot BELIEVE what the other side is saying.
RAISE YOUR VOICE significantly. You are practically YELLING key phrases.
Speak with INTENSE conviction. You are INDIGNANT. You are making THE MOST OBVIOUS POINT.
Words in ALL CAPS should be SHOUTED: louder, higher pitch, more forceful.
Your voice should strain with emotion. You are at about 80% of maximum intensity.
"How can ANYONE not see that THIS is OBVIOUSLY true?!" - that's your energy level.""",

    "screaming": """You are a preacher at the CLIMAX of a sermon, SHOUTING the gospel truth.
This is MAXIMUM INTENSITY. You are SCREAMING with righteous conviction.
Your voice should be LOUD, STRAINED, almost CRACKING with emotion.
Every capitalized word should be YELLED at the top of your lungs.
You are INCREDULOUS. You CANNOT BELIEVE anyone would disagree with such OBVIOUS truth.
Channel a street preacher, an angry sports commentator after a bad call, someone who has SNAPPED.
"ANYONE can see! It's SO OBVIOUS! How do you NOT UNDERSTAND?!"
Strain your voice. Let it crack. This is not calm. This is UNHINGED CONVICTION.""",
}


class OpenAIVoiceGenerator:
    def __init__(self, voice: str = "onyx", style: str = None):
        from openai import OpenAI
        self.client = OpenAI(api_key=config.openai_api_key)
        if voice in OPENAI_VOICE_PRESETS:
            self.voice = OPENAI_VOICE_PRESETS[voice]
        else:
            self.voice = voice
        self.style = style

    def generate(self, text: str, output_path: str = None, instructions: str = None) -> str:
        if output_path is None:
            text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
            output_path = str(Path(config.cache_dir) / "audio" / f"{text_hash}.mp3")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if Path(output_path).exists():
            return output_path

        create_params = {
            "model": "gpt-4o-mini-tts",
            "voice": self.voice,
            "input": text,
        }

        if instructions:
            create_params["instructions"] = instructions

        response = self.client.audio.speech.create(**create_params)
        response.stream_to_file(output_path)
        return output_path

    def generate_turboencabulator(self, segments: list[dict], output_dir: str) -> list[str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        total_segments = len(segments)
        paths = []

        intensity_labels = {
            "calm": "Calm",
            "building": "Building",
            "passionate": "Passionate",
            "emphatic": "EMPHATIC",
            "screaming": "SCREAMING",
        }

        for i, segment in enumerate(segments):
            progress = i / total_segments

            if progress < 0.15:
                intensity = "calm"
            elif progress < 0.30:
                intensity = "building"
            elif progress < 0.50:
                intensity = "passionate"
            elif progress < 0.75:
                intensity = "emphatic"
            else:
                intensity = "screaming"

            instructions = TURBO_INSTRUCTIONS[intensity]
            text = segment["text"] if isinstance(segment, dict) else segment

            path = str(output_dir / f"segment_{i:03d}.mp3")

            if Path(path).exists():
                Path(path).unlink()

            print(f"        [{i+1}/{total_segments}] {intensity_labels[intensity]}: {text[:50]}...")
            self.generate(text, path, instructions=instructions)
            paths.append(path)

        return paths


AZURE_TTS_VOICES = {
    "jane": "en-US-JaneNeural",
    "jenny": "en-US-JennyNeural",
    "aria": "en-US-AriaNeural",
    "sara": "en-US-SaraNeural",
    "guy": "en-US-GuyNeural",
    "davis": "en-US-DavisNeural",
    "jason": "en-US-JasonNeural",
    "tony": "en-US-TonyNeural",
}

AZURE_EMOTION_STYLES = {
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


class AzureTTSVoiceGenerator:
    def __init__(self, voice: str = "jane"):
        import requests
        self.speech_key = config.azure_speech_key
        self.region = config.azure_speech_region
        self.endpoint = getattr(config, 'azure_speech_endpoint', None) or f"https://{self.region}.tts.speech.microsoft.com"
        self.voice = AZURE_TTS_VOICES.get(voice, voice)
        if not self.voice.startswith("en-"):
            self.voice = AZURE_TTS_VOICES.get("jane")

    def _build_ssml(self, text: str, style: str = "friendly", styledegree: str = "1.0") -> str:
        return f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
    xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US">
    <voice name="{self.voice}">
        <prosody rate="+15%" pitch="+3%">
            <mstts:express-as style="{style}" styledegree="{styledegree}">
                {text}
            </mstts:express-as>
        </prosody>
    </voice>
</speak>'''

    def generate(self, text: str, output_path: str = None, style: str = "friendly", styledegree: str = "1.0") -> str:
        import requests

        if output_path is None:
            text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
            output_path = str(Path(config.cache_dir) / "audio" / f"{text_hash}.mp3")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        ssml = self._build_ssml(text, style, styledegree)

        url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": self.speech_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        }

        response = requests.post(url, headers=headers, data=ssml.encode('utf-8'))

        if response.status_code != 200:
            raise RuntimeError(f"Azure TTS failed: {response.status_code} {response.text}")

        with open(output_path, "wb") as f:
            f.write(response.content)

        return output_path

    def _parse_emotion_marker(self, text: str) -> tuple[str, str]:
        emotion_pattern = r'^\[(\w+)\]\s*'
        match = re.match(emotion_pattern, text)
        if match:
            emotion = match.group(1).lower()
            clean_text = re.sub(emotion_pattern, '', text)
            return emotion, clean_text
        return "default", text

    def generate_turboencabulator(self, segments: list[dict], output_dir: str) -> list[str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        total_segments = len(segments)
        paths = []

        for i, segment in enumerate(segments):
            text = segment["text"] if isinstance(segment, dict) else segment

            emotion, clean_text = self._parse_emotion_marker(text)
            style_config = AZURE_EMOTION_STYLES.get(emotion, AZURE_EMOTION_STYLES["default"])

            path = str(output_dir / f"segment_{i:03d}.mp3")

            if Path(path).exists():
                Path(path).unlink()

            emotion_label = emotion.capitalize() if emotion != "default" else "Neutral"
            print(f"        [{i+1}/{total_segments}] {emotion_label}: {clean_text[:50]}...")
            self.generate(clean_text, path, style=style_config["style"], styledegree=style_config["styledegree"])
            paths.append(path)

        return paths


AZURE_OPENAI_VOICE_INSTRUCTIONS = {
    "excited": "Speak with excitement and energy, like you just discovered something amazing. Your voice should be bright and animated.",
    "frustrated": "Speak with mild frustration, like you're explaining something obvious that people keep missing. Slight edge to your voice.",
    "calm": "Speak calmly and warmly, like a friendly conversation. Relaxed pace, approachable tone.",
    "passionate": "Speak with passion and conviction, like a TED talk presenter making their key point. Emphasize important words.",
    "reflective": "Speak thoughtfully and contemplatively, like you're pondering something deep. Slower pace, introspective tone.",
    "sad": "Speak with a hint of sadness or concern, like discussing something unfortunate. Softer, more subdued.",
    "angry": "Speak with intensity and conviction, like you're making an important point forcefully. Strong emphasis.",
    "hopeful": "Speak with hope and optimism, like sharing good news. Warm and uplifting tone.",
    "friendly": "Speak in a warm, friendly manner like chatting with a good friend. Natural and conversational.",
    "whispering": "Speak softly and intimately, like sharing a secret. Quiet but clear.",
    "shouting": "Speak loudly and emphatically, like making a bold proclamation. Strong and forceful.",
    "default": "Speak like a confident podcast host - warm, engaging, natural cadence. Not robotic or reading-like.",
}


class AzureOpenAIAudioGenerator:
    def __init__(self, deployment: str = None, voice: str = "nova"):
        self.endpoint = config.azure_openai_endpoint or "https://eastus.api.cognitive.microsoft.com/"
        self.api_key = config.azure_openai_key
        self.deployment = deployment or config.azure_openai_audio_deployment or "gpt-4o-mini-audio"
        self.voice = voice
        self.api_version = "2025-01-01-preview"

    def _build_system_prompt(self, emotion: str = "default") -> str:
        instruction = AZURE_OPENAI_VOICE_INSTRUCTIONS.get(emotion, AZURE_OPENAI_VOICE_INSTRUCTIONS["default"])
        return f"""You are Rachel, the host of "The Deep Dive" podcast. You're in your early 20s, curious, tenacious, and energetic.

Your speaking style:
- Speak at a BRISK pace, like an energetic YouTuber or podcast host
- Higher pitch, youthful energy
- Natural podcast cadence, not robotic or slow
- Conversational and engaging
- Confident, punchy delivery

Current emotional context: {instruction}

IMPORTANT: Speak QUICKLY and with energy. Just deliver the content naturally as if recording your podcast. No commentary, no "here's the text" - just speak it."""

    def generate(self, text: str, output_path: str, emotion: str = "default") -> str:
        import requests
        import base64

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if Path(output_path).exists():
            Path(output_path).unlink()

        url = f"{self.endpoint}openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        system_prompt = self._build_system_prompt(emotion)

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Speak this for my podcast: {text}"}
            ],
            "modalities": ["text", "audio"],
            "audio": {
                "voice": self.voice,
                "format": "mp3"
            }
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            raise RuntimeError(f"Azure OpenAI Audio failed: {response.status_code} {response.text}")

        data = response.json()
        audio_data = data.get("choices", [{}])[0].get("message", {}).get("audio", {}).get("data")

        if not audio_data:
            raise RuntimeError(f"No audio in response: {data}")

        audio_bytes = base64.b64decode(audio_data)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        return output_path

    def _parse_emotion_marker(self, text: str) -> tuple[str, str]:
        emotion_pattern = r'^\[(\w+)\]\s*'
        match = re.match(emotion_pattern, text)
        if match:
            emotion = match.group(1).lower()
            clean_text = re.sub(emotion_pattern, '', text)
            return emotion, clean_text
        return "default", text

    def generate_turboencabulator(self, segments: list[dict], output_dir: str) -> list[str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        total_segments = len(segments)
        paths = []

        for i, segment in enumerate(segments):
            text = segment["text"] if isinstance(segment, dict) else segment
            emotion, clean_text = self._parse_emotion_marker(text)

            path = str(output_dir / f"segment_{i:03d}.mp3")

            emotion_label = emotion.capitalize() if emotion != "default" else "Neutral"
            print(f"        [{i+1}/{total_segments}] {emotion_label}: {clean_text[:50]}...")

            self.generate(clean_text, path, emotion=emotion)
            paths.append(path)

        return paths


ELEVENLABS_VOICE_POOL = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "drew": "29vD33N1CtxCmqQRPOHJ",
    "clyde": "2EiwWnXFnvU5JabPnv8n",
    "paul": "5Q0t7uMcjvnagumLfvZi",
    "domi": "AZnzlk1XvdvUeBnXmlld",
    "dave": "CYw3kZ02Hs0563khs1Fj",
    "fin": "D38z5RcWu1voky8WS1ja",
    "sarah": "EXAVITQu4vr4xnSDxMaL",
    "antoni": "ErXwobaYiN019PkySvjV",
    "thomas": "GBv7mTt0atIp3Br8iCZE",
    "charlie": "IKne3meq5aSn9XLyUdCD",
    "george": "JBFqnCBsd6RMkjVDRZzb",
    "emily": "LcfcDJNUP1GQjkzn1xUU",
    "elli": "MF3mGyEYCl7XYWbV9V6O",
    "callum": "N2lVS1w4EtoT3dr4eOWO",
    "patrick": "ODq5zmih8GrVes37Dizd",
    "harry": "SOYHLrjzK2X1ezoPC6cr",
    "liam": "TX3LPaxmHKxFdv7VOQHJ",
    "dorothy": "ThT5KcBeYPX3keUQqHPh",
    "josh": "TxGEqnHWrfWFTfGW9XjX",
    "arnold": "VR6AewLTigWG4xSOukaG",
    "charlotte": "XB0fDUnXU5powFXDhCwa",
    "matilda": "XrExE9yKIg1WjnnlVkGX",
    "matthew": "Yko7PKs6WkxO6Y0mQVvD",
    "james": "ZQe5CZNOzWyzPSCn5a3c",
    "joseph": "Zlb1dXrM653N07WRdFW3",
    "jeremy": "bVMeCyTHy58xNoL34h3p",
    "michael": "flq6f7yk4E4fJM5XTYuZ",
    "ethan": "g5CIjZEefAph4nQFvHAz",
    "gigi": "jBpfuIE2acCO8z3wKNLl",
    "freya": "jsCqWAovK2LkecY7zXl4",
    "grace": "oWAxZDx7w5VEj9dCyTzz",
    "daniel": "onwK4e9ZLuTAKqWW03F9",
    "serena": "pFZP5JQG7iQjIQuC4Bku",
    "adam": "pNInz6obpgDQGcFmaJgB",
    "nicole": "piTKgcLEGmPE4e6mEKli",
    "jessie": "t0jbNlBVZ17f02VDIeMI",
    "ryan": "wViXBPUzp2ZZixB1xQuM",
    "sam": "yoZ06aMxZJJ28mfd3POQ",
    "glinda": "z9fAnlkpzviPz146aGWa",
    "giovanni": "zcAOhNBS3c14rBihAFp1",
    "mimi": "zrHiDhphv9ZnVXBqCLjz",
}

VOICE_PERSONAS = {
    "host_male": ["drew", "josh", "matthew", "daniel", "adam"],
    "host_female": ["rachel", "sarah", "charlotte", "grace", "nicole"],
    "expert_male": ["clyde", "paul", "thomas", "george", "james", "arnold"],
    "expert_female": ["domi", "emily", "elli", "dorothy", "matilda", "serena"],
    "contrarian_male": ["fin", "patrick", "harry", "liam", "jeremy", "ethan"],
    "contrarian_female": ["gigi", "freya", "jessie", "mimi", "glinda"],
    "wildcard": ["charlie", "callum", "joseph", "michael", "ryan", "sam", "giovanni"],
}


class ElevenLabsVoiceGenerator:
    DEFAULT_VOICE_ID = ELEVENLABS_VOICE_POOL["rachel"]

    def __init__(self, voice_id: str = None):
        self.api_key = config.elevenlabs_api_key
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
        self.base_url = "https://api.elevenlabs.io/v1"
        self.speaker_voices = {}
        self.speaker_names = {}

    def generate(self, text: str, output_path: str, voice_id: str = None, stability: float = 0.5, similarity_boost: float = 0.8, speed: float = 1.0) -> str:
        import requests
        import subprocess

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if Path(output_path).exists():
            Path(output_path).unlink()

        vid = voice_id or self.voice_id
        url = f"{self.base_url}/text-to-speech/{vid}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key,
        }

        data = {
            "text": text,
            "model_id": "eleven_v3",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
            }
        }

        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()

        if speed == 1.0:
            with open(output_path, "wb") as f:
                f.write(response.content)
        else:
            temp_path = output_path.replace(".mp3", "_temp.mp3")
            with open(temp_path, "wb") as f:
                f.write(response.content)
            subprocess.run([
                "ffmpeg", "-y", "-i", temp_path,
                "-filter:a", f"atempo={speed}",
                "-vn", output_path
            ], capture_output=True)
            Path(temp_path).unlink()

        return output_path

    def _detect_speaker(self, text: str) -> tuple[str, str, str, str]:
        import re
        speaker_pattern = r'^\[([A-Z_]+?)(?:_(MALE|FEMALE))?(?::\s*([^\]]+))?\]\s*'
        match = re.match(speaker_pattern, text)
        if match:
            speaker_type = match.group(1)
            gender = match.group(2)
            character_name = match.group(3)
            clean_text = re.sub(r'^\[[^\]]+\]\s*', '', text)
            return speaker_type, gender, character_name, clean_text
        return None, None, None, text

    def _assign_voice_to_speaker(self, speaker_type: str, gender: str, character_name: str, primary_voice_id: str) -> str:
        import random

        cache_key = f"{speaker_type}:{character_name}" if character_name else speaker_type

        if cache_key in self.speaker_voices:
            return self.speaker_voices[cache_key]

        type_upper = speaker_type.upper()

        if type_upper in ("HOST", "MODERATOR"):
            self.speaker_voices[cache_key] = primary_voice_id
            print(f"        Assigned voice 'rachel' (primary) to {speaker_type}")
            return primary_voice_id

        gender_upper = (gender or "").upper()

        if gender_upper == "FEMALE":
            if type_upper in ("SIDE_A", "PANELIST_1", "EXPERT_A", "GUEST"):
                pool = VOICE_PERSONAS["expert_female"]
            elif type_upper in ("SIDE_B", "PANELIST_2", "EXPERT_B"):
                pool = VOICE_PERSONAS["contrarian_female"]
            else:
                pool = VOICE_PERSONAS["expert_female"] + VOICE_PERSONAS["contrarian_female"]
        elif gender_upper == "MALE":
            if type_upper in ("SIDE_A", "PANELIST_1", "EXPERT_A", "GUEST"):
                pool = VOICE_PERSONAS["expert_male"]
            elif type_upper in ("SIDE_B", "PANELIST_2", "EXPERT_B"):
                pool = VOICE_PERSONAS["contrarian_male"]
            else:
                pool = VOICE_PERSONAS["expert_male"] + VOICE_PERSONAS["contrarian_male"]
        else:
            if type_upper in ("SIDE_A", "PANELIST_1", "EXPERT_A"):
                pool = VOICE_PERSONAS["expert_male"]
            elif type_upper in ("SIDE_B", "PANELIST_2", "EXPERT_B"):
                pool = VOICE_PERSONAS["contrarian_female"]
            elif type_upper in ("PANELIST_3", "EXPERT_C"):
                pool = VOICE_PERSONAS["contrarian_male"]
            elif type_upper == "PANELIST_4":
                pool = VOICE_PERSONAS["expert_female"]
            elif type_upper.startswith("GUEST"):
                pool = VOICE_PERSONAS["expert_male"]
            else:
                pool = VOICE_PERSONAS["wildcard"]

        used_voices = set(self.speaker_voices.values())
        available = [v for v in pool if ELEVENLABS_VOICE_POOL.get(v) not in used_voices]
        if not available:
            available = pool

        chosen_name = random.choice(available)
        chosen_id = ELEVENLABS_VOICE_POOL[chosen_name]
        self.speaker_voices[cache_key] = chosen_id

        display_name = character_name if character_name else speaker_type
        print(f"        Assigned voice '{chosen_name}' to {display_name}")
        return chosen_id

    def generate_turboencabulator(self, segments: list[dict], output_dir: str, voice_id: str = None, base_speed: float = 1.0) -> list[str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        total_segments = len(segments)
        paths = []
        primary_voice = voice_id or self.voice_id
        self.speaker_voices = {}
        self.speaker_names = {}

        intensity_settings = {
            "calm": {"stability": 1.0, "similarity_boost": 0.5, "speed": base_speed},
            "building": {"stability": 0.5, "similarity_boost": 0.6, "speed": base_speed * 1.02},
            "passionate": {"stability": 0.5, "similarity_boost": 0.7, "speed": base_speed * 1.05},
            "emphatic": {"stability": 0.0, "similarity_boost": 0.8, "speed": base_speed * 1.08},
            "screaming": {"stability": 0.0, "similarity_boost": 0.9, "speed": base_speed * 1.1},
        }

        intensity_labels = {
            "calm": "Calm",
            "building": "Building",
            "passionate": "Passionate",
            "emphatic": "EMPHATIC",
            "screaming": "SCREAMING",
        }

        for i, segment in enumerate(segments):
            progress = i / total_segments

            if progress < 0.15:
                intensity = "calm"
            elif progress < 0.30:
                intensity = "building"
            elif progress < 0.50:
                intensity = "passionate"
            elif progress < 0.75:
                intensity = "emphatic"
            else:
                intensity = "screaming"

            settings = intensity_settings[intensity]
            text = segment["text"] if isinstance(segment, dict) else segment

            speaker_type, gender, character_name, clean_text = self._detect_speaker(text)

            if speaker_type:
                segment_voice = self._assign_voice_to_speaker(speaker_type, gender, character_name, primary_voice)
            else:
                segment_voice = primary_voice

            clean_text = self._add_intensity_markers(clean_text, intensity)

            path = str(output_dir / f"segment_{i:03d}.mp3")

            display_speaker = character_name if character_name else (speaker_type if speaker_type else "")
            speaker_info = f"[{display_speaker}] " if display_speaker else ""
            print(f"        [{i+1}/{total_segments}] {intensity_labels[intensity]} {speaker_info}: {clean_text[:40]}...")

            self.generate(
                clean_text, path,
                voice_id=segment_voice,
                stability=settings["stability"],
                similarity_boost=settings["similarity_boost"],
                speed=settings.get("speed", 1.0),
            )
            paths.append(path)

        return paths

    def _add_intensity_markers(self, text: str, intensity: str) -> str:
        if intensity == "calm":
            return text
        elif intensity == "building":
            return f"{text} [sighs]"
        elif intensity == "passionate":
            return f"[excited] {text}"
        elif intensity == "emphatic":
            return f"[angry] [shouting] {text}!"
        elif intensity == "screaming":
            return f"[angry] [shouting] {text}!! [laughs]"
        return text


BARK_SPEAKERS = {
    "speaker_0": "v2/en_speaker_0",
    "speaker_1": "v2/en_speaker_1",
    "speaker_2": "v2/en_speaker_2",
    "speaker_3": "v2/en_speaker_3",
    "speaker_4": "v2/en_speaker_4",
    "speaker_5": "v2/en_speaker_5",
    "speaker_6": "v2/en_speaker_6",
    "speaker_7": "v2/en_speaker_7",
    "speaker_8": "v2/en_speaker_8",
    "speaker_9": "v2/en_speaker_9",
}

BARK_VOICE_PERSONAS = {
    "host": ["speaker_0", "speaker_3"],
    "expert_male": ["speaker_1", "speaker_6", "speaker_8"],
    "expert_female": ["speaker_2", "speaker_4", "speaker_9"],
    "contrarian_male": ["speaker_5", "speaker_7"],
    "contrarian_female": ["speaker_3", "speaker_4"],
}


class BarkVoiceGenerator:
    def __init__(self):
        self.model_loaded = False
        self.speaker_voices = {}

    def _ensure_model(self):
        if not self.model_loaded:
            import torch

            original_load = torch.load
            def patched_load(*args, **kwargs):
                kwargs.setdefault('weights_only', False)
                return original_load(*args, **kwargs)
            torch.load = patched_load

            from bark import preload_models
            preload_models()
            self.model_loaded = True

    def generate(self, text: str, output_path: str, speaker: str = None) -> str:
        from bark import generate_audio, SAMPLE_RATE
        from scipy.io.wavfile import write as write_wav
        import numpy as np

        self._ensure_model()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if Path(output_path).exists():
            Path(output_path).unlink()

        history_prompt = BARK_SPEAKERS.get(speaker, speaker) if speaker else None
        audio_array = generate_audio(text, history_prompt=history_prompt)

        wav_path = output_path.replace(".mp3", ".wav")
        write_wav(wav_path, SAMPLE_RATE, (audio_array * 32767).astype(np.int16))

        if output_path.endswith(".mp3"):
            import subprocess
            subprocess.run([
                "ffmpeg", "-y", "-i", wav_path,
                "-codec:a", "libmp3lame", "-qscale:a", "2",
                output_path
            ], capture_output=True)
            Path(wav_path).unlink()

        return output_path

    def _detect_speaker(self, text: str) -> tuple[str, str, str, str]:
        speaker_pattern = r'^\[([A-Z_]+?)(?:_(MALE|FEMALE))?(?::\s*([^\]]+))?\]\s*'
        match = re.match(speaker_pattern, text)
        if match:
            speaker_type = match.group(1)
            gender = match.group(2)
            character_name = match.group(3)
            clean_text = re.sub(r'^\[[^\]]+\]\s*', '', text)
            return speaker_type, gender, character_name, clean_text
        return None, None, None, text

    def _assign_voice_to_speaker(self, speaker_type: str, gender: str, character_name: str) -> str:
        import random

        cache_key = f"{speaker_type}:{character_name}" if character_name else speaker_type

        if cache_key in self.speaker_voices:
            return self.speaker_voices[cache_key]

        type_upper = speaker_type.upper()
        gender_upper = (gender or "").upper()

        if type_upper in ("HOST", "MODERATOR"):
            pool = BARK_VOICE_PERSONAS["host"]
        elif gender_upper == "FEMALE":
            if type_upper in ("SIDE_A", "PANELIST_1", "EXPERT_A", "GUEST"):
                pool = BARK_VOICE_PERSONAS["expert_female"]
            else:
                pool = BARK_VOICE_PERSONAS["contrarian_female"]
        elif gender_upper == "MALE":
            if type_upper in ("SIDE_A", "PANELIST_1", "EXPERT_A", "GUEST"):
                pool = BARK_VOICE_PERSONAS["expert_male"]
            else:
                pool = BARK_VOICE_PERSONAS["contrarian_male"]
        else:
            if type_upper in ("SIDE_A", "PANELIST_1", "EXPERT_A"):
                pool = BARK_VOICE_PERSONAS["expert_male"]
            elif type_upper in ("SIDE_B", "PANELIST_2", "EXPERT_B"):
                pool = BARK_VOICE_PERSONAS["expert_female"]
            else:
                pool = list(BARK_SPEAKERS.keys())

        used = set(self.speaker_voices.values())
        available = [v for v in pool if v not in used]
        if not available:
            available = pool

        chosen = random.choice(available)
        self.speaker_voices[cache_key] = chosen

        display_name = character_name if character_name else speaker_type
        print(f"        Assigned Bark voice '{chosen}' to {display_name}")
        return chosen

    def generate_turboencabulator(self, segments: list[dict], output_dir: str, base_speed: float = 1.0) -> list[str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        total_segments = len(segments)
        paths = []
        self.speaker_voices = {}

        intensity_labels = {
            "calm": "Calm",
            "building": "Building",
            "passionate": "Passionate",
            "emphatic": "EMPHATIC",
            "screaming": "SCREAMING",
        }

        for i, segment in enumerate(segments):
            progress = i / total_segments

            if progress < 0.15:
                intensity = "calm"
            elif progress < 0.30:
                intensity = "building"
            elif progress < 0.50:
                intensity = "passionate"
            elif progress < 0.75:
                intensity = "emphatic"
            else:
                intensity = "screaming"

            text = segment["text"] if isinstance(segment, dict) else segment

            speaker_type, gender, character_name, clean_text = self._detect_speaker(text)

            if speaker_type:
                speaker = self._assign_voice_to_speaker(speaker_type, gender, character_name)
            else:
                speaker = "speaker_0"

            clean_text = self._add_bark_markers(clean_text, intensity)

            path = str(output_dir / f"segment_{i:03d}.mp3")

            display_speaker = character_name if character_name else (speaker_type if speaker_type else "")
            speaker_info = f"[{display_speaker}] " if display_speaker else ""
            print(f"        [{i+1}/{total_segments}] {intensity_labels[intensity]} {speaker_info}: {clean_text[:40]}...")

            self.generate(clean_text, path, speaker=speaker)
            paths.append(path)

        return paths

    def _add_bark_markers(self, text: str, intensity: str) -> str:
        if intensity == "calm":
            return text
        elif intensity == "building":
            return text.replace("...", "... [sighs] ...")
        elif intensity == "passionate":
            text = text.upper() if any(c.isupper() for c in text) else text
            return f"[clears throat] {text}"
        elif intensity == "emphatic":
            text = text.replace("!", "!! [gasps]")
            return text
        elif intensity == "screaming":
            text = text.replace("!", "!!")
            text = text.replace("?", "?!")
            return f"{text} [gasps]"
        return text


class FishSpeechVoiceGenerator:
    DEFAULT_VOICE_ID = "61e7f07e64e84b788ef8b8b5b5d52cb5"

    def __init__(self, voice_id: str = None, base_url: str = None, local: bool = True):
        self.local = local
        self.api_key = config.fish_audio_api_key if not local else None
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
        if base_url:
            self.base_url = base_url
        elif local:
            self.base_url = config.fish_speech_url
        else:
            self.base_url = "https://api.fish.audio"
        self.speaker_voices = {}
        self.reference_audio = None
        self.reference_audio_map = {}

    def _convert_markers_to_fish(self, text: str) -> str:
        result = text
        marker_pattern = r'\[([^\]]+)\]'

        def replace_marker(match):
            marker = match.group(1).lower().strip()
            if marker in FISH_EMOTION_MAP:
                return FISH_EMOTION_MAP[marker]
            for key, value in FISH_EMOTION_MAP.items():
                if key in marker:
                    return value
            return match.group(0)

        result = re.sub(marker_pattern, replace_marker, result)
        result = re.sub(r'\[[A-Z_]+(?:_(?:MALE|FEMALE))?(?::[^\]]+)?\]\s*', '', result)
        return result.strip()

    def _add_intensity_markers(self, text: str, intensity: str) -> str:
        fish_marker = FISH_INTENSITY_MARKERS.get(intensity, "")
        if not fish_marker:
            return text
        return f"{fish_marker} {text}"

    def generate(self, text: str, output_path: str, voice_id: str = None, speed: float = 1.0) -> str:
        import requests
        import subprocess

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if Path(output_path).exists():
            Path(output_path).unlink()

        text_with_markers = self._convert_markers_to_fish(text)

        if self.local:
            url = f"{self.base_url}/v1/tts"
            data = {
                "text": text_with_markers,
                "format": "mp3",
                "streaming": False,
            }
            if self.reference_audio:
                import base64
                with open(self.reference_audio, "rb") as f:
                    data["reference_audio"] = base64.b64encode(f.read()).decode()

            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=data, headers=headers)
        else:
            vid = voice_id or self.voice_id
            url = f"{self.base_url}/v1/tts"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            data = {
                "text": text_with_markers,
                "reference_id": vid,
                "format": "mp3",
                "latency": "balanced",
            }
            if speed != 1.0:
                data["prosody"] = {"speed": speed}
            response = requests.post(url, json=data, headers=headers)

        response.raise_for_status()

        if speed != 1.0 and self.local:
            temp_path = output_path.replace(".mp3", "_temp.mp3")
            with open(temp_path, "wb") as f:
                f.write(response.content)
            subprocess.run([
                "ffmpeg", "-y", "-i", temp_path,
                "-filter:a", f"atempo={speed}",
                "-vn", output_path
            ], capture_output=True)
            Path(temp_path).unlink()
        else:
            with open(output_path, "wb") as f:
                f.write(response.content)

        return output_path

    def _detect_speaker(self, text: str) -> tuple[str, str, str, str]:
        speaker_pattern = r'^\[([A-Z_]+?)(?:_(MALE|FEMALE))?(?::\s*([^\]]+))?\]\s*'
        match = re.match(speaker_pattern, text)
        if match:
            speaker_type = match.group(1)
            gender = match.group(2)
            character_name = match.group(3)
            clean_text = re.sub(r'^\[[^\]]+\]\s*', '', text)
            return speaker_type, gender, character_name, clean_text
        return None, None, None, text

    def _assign_voice_to_speaker(self, speaker_type: str, gender: str, character_name: str, primary_voice_id: str) -> str:
        import random

        cache_key = f"{speaker_type}:{character_name}" if character_name else speaker_type

        if cache_key in self.speaker_voices:
            return self.speaker_voices[cache_key]

        type_upper = speaker_type.upper()

        if type_upper in ("HOST", "MODERATOR"):
            self.speaker_voices[cache_key] = primary_voice_id
            return primary_voice_id

        gender_upper = (gender or "").upper()

        if gender_upper == "FEMALE":
            if type_upper in ("SIDE_A", "PANELIST_1", "EXPERT_A", "GUEST"):
                pool = FISH_VOICE_POOL.get("expert_female", [self.DEFAULT_VOICE_ID])
            else:
                pool = FISH_VOICE_POOL.get("contrarian_female", [self.DEFAULT_VOICE_ID])
        elif gender_upper == "MALE":
            if type_upper in ("SIDE_A", "PANELIST_1", "EXPERT_A", "GUEST"):
                pool = FISH_VOICE_POOL.get("expert_male", [self.DEFAULT_VOICE_ID])
            else:
                pool = FISH_VOICE_POOL.get("contrarian_male", [self.DEFAULT_VOICE_ID])
        else:
            if type_upper in ("SIDE_A", "PANELIST_1", "EXPERT_A"):
                pool = FISH_VOICE_POOL.get("expert_male", [self.DEFAULT_VOICE_ID])
            elif type_upper in ("SIDE_B", "PANELIST_2", "EXPERT_B"):
                pool = FISH_VOICE_POOL.get("contrarian_female", [self.DEFAULT_VOICE_ID])
            else:
                pool = [self.DEFAULT_VOICE_ID]

        used_voices = set(self.speaker_voices.values())
        available = [v for v in pool if v not in used_voices]
        if not available:
            available = pool

        chosen_id = random.choice(available)
        self.speaker_voices[cache_key] = chosen_id
        return chosen_id

    def set_reference_audio(self, speaker_type: str, audio_path: str):
        self.reference_audio_map[speaker_type.upper()] = audio_path

    def generate_turboencabulator(self, segments: list[dict], output_dir: str, voice_id: str = None, base_speed: float = 1.0) -> list[str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        total_segments = len(segments)
        paths = []
        primary_voice = voice_id or self.voice_id
        self.speaker_voices = {}

        intensity_labels = {
            "calm": "Calm",
            "building": "Building",
            "passionate": "Passionate",
            "emphatic": "EMPHATIC",
            "screaming": "SCREAMING",
        }

        speed_multipliers = {
            "calm": 1.0,
            "building": 1.02,
            "passionate": 1.05,
            "emphatic": 1.08,
            "screaming": 1.1,
        }

        for i, segment in enumerate(segments):
            progress = i / total_segments

            if progress < 0.15:
                intensity = "calm"
            elif progress < 0.30:
                intensity = "building"
            elif progress < 0.50:
                intensity = "passionate"
            elif progress < 0.75:
                intensity = "emphatic"
            else:
                intensity = "screaming"

            text = segment["text"] if isinstance(segment, dict) else segment

            speaker_type, gender, character_name, clean_text = self._detect_speaker(text)

            if self.local:
                segment_voice = primary_voice
                if speaker_type and speaker_type.upper() in self.reference_audio_map:
                    self.reference_audio = self.reference_audio_map[speaker_type.upper()]
                else:
                    self.reference_audio = None
            else:
                if speaker_type:
                    segment_voice = self._assign_voice_to_speaker(speaker_type, gender, character_name, primary_voice)
                else:
                    segment_voice = primary_voice

            clean_text = self._add_intensity_markers(clean_text, intensity)

            path = str(output_dir / f"segment_{i:03d}.mp3")

            display_speaker = character_name if character_name else (speaker_type if speaker_type else "")
            speaker_info = f"[{display_speaker}] " if display_speaker else ""
            print(f"        [{i+1}/{total_segments}] {intensity_labels[intensity]} {speaker_info}: {clean_text[:40]}...")

            speed = base_speed * speed_multipliers[intensity]
            self.generate(clean_text, path, voice_id=segment_voice, speed=speed)
            paths.append(path)

        return paths


XTTS_SAMPLE_VOICES = {
    "male_1": "https://github.com/coqui-ai/TTS/raw/dev/tests/inputs/ljspeech/wavs/LJ001-0001.wav",
    "male_2": "https://keithito.com/LJ-Speech-Dataset/LJ037-0171.wav",
    "female_1": "https://github.com/coqui-ai/TTS/raw/dev/tests/inputs/vctk/wavs/p225_001.wav",
    "female_2": "https://github.com/coqui-ai/TTS/raw/dev/tests/inputs/vctk/wavs/p226_001.wav",
}


class CoquiXTTSVoiceGenerator:
    def __init__(self, model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"):
        self.model_name = model_name
        self.tts = None
        self.speaker_wavs = {}
        self.speaker_voices = {}
        self.voice_mappings = {}
        self.voices_dir = Path(config.cache_dir) / "xtts_voices"
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self._load_voice_mappings()

    def _load_voice_mappings(self):
        import json
        mappings_file = self.voices_dir / "voice_mappings.json"
        if mappings_file.exists():
            with open(mappings_file) as f:
                self.voice_mappings = json.load(f)
            print(f"        Loaded voice mappings: {list(self.voice_mappings.keys())}")

    def save_voice_mappings(self):
        import json
        mappings_file = self.voices_dir / "voice_mappings.json"
        with open(mappings_file, "w") as f:
            json.dump(self.voice_mappings, f, indent=2)
        print(f"        Saved voice mappings to {mappings_file}")

    def map_voice(self, speaker_type: str, voice_name: str):
        self.voice_mappings[speaker_type.upper()] = voice_name
        self.save_voice_mappings()

    def list_available_voices(self) -> list[str]:
        samples_dir = self.voices_dir / "samples"
        if not samples_dir.exists():
            return []
        return [f.stem for f in samples_dir.glob("*.wav")]

    def _ensure_model(self):
        if self.tts is None:
            from TTS.api import TTS
            import torch
            device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
            self.tts = TTS(self.model_name).to(device)
            print(f"        Loaded XTTS model on {device}")

    def download_sample_voices(self):
        import requests
        samples_dir = self.voices_dir / "samples"
        samples_dir.mkdir(exist_ok=True)

        for name, url in XTTS_SAMPLE_VOICES.items():
            dest = samples_dir / f"{name}.wav"
            if not dest.exists():
                print(f"        Downloading {name}...")
                try:
                    resp = requests.get(url, timeout=30)
                    resp.raise_for_status()
                    dest.write_bytes(resp.content)
                    self.speaker_wavs[name] = str(dest)
                except Exception as e:
                    print(f"        Failed to download {name}: {e}")
            else:
                self.speaker_wavs[name] = str(dest)

        return len(self.speaker_wavs)

    def add_voice(self, name: str, wav_path: str):
        self.speaker_wavs[name] = wav_path

    def _get_default_voices(self) -> dict[str, str]:
        defaults = {}
        samples_dir = self.voices_dir / "samples"
        samples_dir.mkdir(exist_ok=True)

        sample_files = list(samples_dir.glob("*.wav"))
        if len(sample_files) >= 2:
            for f in sample_files:
                defaults[f.stem] = str(f)
            return defaults

        print("        No voice samples found. Downloading defaults...")
        self.download_sample_voices()
        return dict(self.speaker_wavs)

    def generate(self, text: str, output_path: str, speaker_wav: str = None, language: str = "en") -> str:
        self._ensure_model()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if Path(output_path).exists():
            Path(output_path).unlink()

        wav_path = output_path.replace(".mp3", ".wav")

        if speaker_wav and Path(speaker_wav).exists():
            self.tts.tts_to_file(
                text=text,
                file_path=wav_path,
                speaker_wav=speaker_wav,
                language=language
            )
        else:
            self.tts.tts_to_file(
                text=text,
                file_path=wav_path,
                language=language
            )

        if output_path.endswith(".mp3"):
            import subprocess
            subprocess.run([
                "ffmpeg", "-y", "-i", wav_path,
                "-codec:a", "libmp3lame", "-qscale:a", "2",
                output_path
            ], capture_output=True)
            Path(wav_path).unlink()
        else:
            import shutil
            shutil.move(wav_path, output_path)

        return output_path

    def _detect_speaker(self, text: str) -> tuple[str, str, str, str]:
        speaker_pattern = r'^\[([A-Z_]+?)(?:_(MALE|FEMALE))?(?::\s*([^\]]+))?\]\s*'
        match = re.match(speaker_pattern, text)
        if match:
            speaker_type = match.group(1)
            gender = match.group(2)
            character_name = match.group(3)
            clean_text = re.sub(r'^\[[^\]]+\]\s*', '', text)
            return speaker_type, gender, character_name, clean_text
        return None, None, None, text

    def _assign_voice_to_speaker(self, speaker_type: str, character_name: str) -> str:
        cache_key = f"{speaker_type}:{character_name}" if character_name else speaker_type

        if cache_key in self.speaker_voices:
            return self.speaker_voices[cache_key]

        type_upper = speaker_type.upper() if speaker_type else None
        if type_upper and type_upper in self.voice_mappings:
            chosen = self.voice_mappings[type_upper]
            self.speaker_voices[cache_key] = chosen
            display_name = character_name if character_name else speaker_type
            print(f"        Using mapped voice '{chosen}' for {display_name}")
            return chosen

        available_voices = list(self.speaker_wavs.keys())
        if not available_voices:
            defaults = self._get_default_voices()
            self.speaker_wavs.update(defaults)
            available_voices = list(self.speaker_wavs.keys())

        if not available_voices:
            return None

        used = set(self.speaker_voices.values())
        free = [v for v in available_voices if v not in used]
        if not free:
            free = available_voices

        import random
        chosen = random.choice(free)
        self.speaker_voices[cache_key] = chosen

        display_name = character_name if character_name else speaker_type
        print(f"        Assigned XTTS voice '{chosen}' to {display_name}")
        return chosen

    def generate_turboencabulator(self, segments: list[dict], output_dir: str, base_speed: float = 1.0) -> list[str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        total_segments = len(segments)
        paths = []
        self.speaker_voices = {}

        intensity_labels = {
            "calm": "Calm",
            "building": "Building",
            "passionate": "Passionate",
            "emphatic": "EMPHATIC",
            "screaming": "SCREAMING",
        }

        for i, segment in enumerate(segments):
            progress = i / total_segments

            if progress < 0.15:
                intensity = "calm"
            elif progress < 0.30:
                intensity = "building"
            elif progress < 0.50:
                intensity = "passionate"
            elif progress < 0.75:
                intensity = "emphatic"
            else:
                intensity = "screaming"

            text = segment["text"] if isinstance(segment, dict) else segment

            speaker_type, gender, character_name, clean_text = self._detect_speaker(text)

            speaker_wav = None
            if speaker_type:
                voice_name = self._assign_voice_to_speaker(speaker_type, character_name)
                if voice_name and voice_name in self.speaker_wavs:
                    speaker_wav = self.speaker_wavs[voice_name]

            path = str(output_dir / f"segment_{i:03d}.mp3")

            display_speaker = character_name if character_name else (speaker_type if speaker_type else "")
            speaker_info = f"[{display_speaker}] " if display_speaker else ""
            print(f"        [{i+1}/{total_segments}] {intensity_labels[intensity]} {speaker_info}: {clean_text[:40]}...")

            self.generate(clean_text, path, speaker_wav=speaker_wav)
            paths.append(path)

        return paths
