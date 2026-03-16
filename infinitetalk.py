import os
import base64
import time
import tempfile
import subprocess
import requests
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import config

CHUNK_DURATION_SEC = 30
RUNPOD_ENDPOINT = "smu7s0ky1u8cie"


@dataclass
class CastMember:
    name: str
    image_path: str
    voice_id: str = None
    prompt: str = "A person speaking naturally"


CAST = {
    "rachel": CastMember(
        name="Rachel",
        image_path="assets/rachel_avatar.png",
        voice_id="jane",
        prompt="A woman hosting a podcast, speaking naturally"
    ),
    "host": CastMember(
        name="Host",
        image_path="assets/rachel_avatar.png",
        voice_id="jane",
        prompt="A woman hosting a podcast, speaking naturally"
    ),
    "drew": CastMember(
        name="Drew",
        image_path="assets/cast/drew.png",
        voice_id="drew",
        prompt="A man being interviewed, speaking thoughtfully"
    ),
    "marcus": CastMember(
        name="Marcus",
        image_path="assets/cast/marcus.png",
        voice_id="marcus",
        prompt="A man speaking passionately in a debate"
    ),
    "elena": CastMember(
        name="Elena",
        image_path="assets/cast/elena.png",
        voice_id="elena",
        prompt="A woman expert explaining a concept"
    ),
    "james": CastMember(
        name="James",
        image_path="assets/cast/james.png",
        voice_id="james",
        prompt="A man arguing a point confidently"
    ),
    "sophia": CastMember(
        name="Sophia",
        image_path="assets/cast/sophia.png",
        voice_id="sophia",
        prompt="A woman debating with intensity"
    ),
    "michael": CastMember(
        name="Michael",
        image_path="assets/cast/michael.png",
        voice_id="michael",
        prompt="A man presenting facts calmly"
    ),
    "guest_male": CastMember(
        name="Guest",
        image_path="assets/cast/guest_male.png",
        voice_id="guy",
        prompt="A man being interviewed"
    ),
    "guest_female": CastMember(
        name="Guest",
        image_path="assets/cast/guest_female.png",
        voice_id="aria",
        prompt="A woman being interviewed"
    ),
    "side_a": CastMember(
        name="Side A",
        image_path="assets/cast/debater_a.png",
        voice_id="drew",
        prompt="A man debating passionately"
    ),
    "side_b": CastMember(
        name="Side B",
        image_path="assets/cast/debater_b.png",
        voice_id="clyde",
        prompt="A man arguing counterpoints"
    ),
    "panelist_1": CastMember(
        name="Panelist 1",
        image_path="assets/cast/panelist_1.png",
        voice_id="drew",
        prompt="A man on a panel discussion"
    ),
    "panelist_2": CastMember(
        name="Panelist 2",
        image_path="assets/cast/panelist_2.png",
        voice_id="elena",
        prompt="A woman on a panel discussion"
    ),
    "panelist_3": CastMember(
        name="Panelist 3",
        image_path="assets/cast/panelist_3.png",
        voice_id="james",
        prompt="A man on a panel discussion"
    ),
}


def get_cast_member(speaker_tag: str) -> CastMember:
    tag_lower = speaker_tag.lower()

    if "host" in tag_lower:
        return CAST["host"]
    elif "rachel" in tag_lower:
        return CAST["rachel"]
    elif "side_a" in tag_lower or "sidea" in tag_lower:
        return CAST["side_a"]
    elif "side_b" in tag_lower or "sideb" in tag_lower:
        return CAST["side_b"]
    elif "guest" in tag_lower:
        if "female" in tag_lower:
            return CAST["guest_female"]
        return CAST["guest_male"]
    elif "panelist_1" in tag_lower or "panelist1" in tag_lower:
        return CAST["panelist_1"]
    elif "panelist_2" in tag_lower or "panelist2" in tag_lower:
        return CAST["panelist_2"]
    elif "panelist_3" in tag_lower or "panelist3" in tag_lower:
        return CAST["panelist_3"]

    for key, member in CAST.items():
        if key in tag_lower or member.name.lower() in tag_lower:
            return member

    return CAST["rachel"]


class InfiniteTalkGenerator:
    def __init__(self, endpoint_id: str = None):
        self.api_key = config.runpod_api_key or os.environ.get("RUNPOD_API_KEY")
        self.endpoint_id = endpoint_id or RUNPOD_ENDPOINT
        self.base_url = f"https://api.runpod.ai/v2/{self.endpoint_id}"
        self._available = None

    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = bool(self.api_key)
        return self._available

    def _get_audio_duration(self, audio_path: str) -> float:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())

    def _split_audio(self, audio_path: str, output_dir: Path) -> list[str]:
        duration = self._get_audio_duration(audio_path)

        if duration <= CHUNK_DURATION_SEC:
            return [str(audio_path)]

        chunks = []
        start = 0
        idx = 0
        while start < duration:
            chunk_path = output_dir / f"chunk_{idx:03d}.wav"
            subprocess.run([
                "ffmpeg", "-y", "-i", str(audio_path),
                "-ss", str(start), "-t", str(CHUNK_DURATION_SEC),
                "-ar", "44100", "-ac", "1", str(chunk_path)
            ], capture_output=True)
            chunks.append(str(chunk_path))
            start += CHUNK_DURATION_SEC
            idx += 1

        return chunks

    def _upload_to_blob(self, file_path: str, blob_name: str) -> str:
        from azure.storage.blob import BlobServiceClient, ContentSettings

        conn_str = config.azure_storage_connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        container = config.azure_storage_container or os.environ.get("AZURE_STORAGE_CONTAINER", "media")

        blob_service = BlobServiceClient.from_connection_string(conn_str)
        container_client = blob_service.get_container_client(container)

        content_type = "audio/wav" if file_path.endswith(".wav") else "image/png"

        with open(file_path, "rb") as f:
            container_client.upload_blob(
                blob_name, f, overwrite=True,
                content_settings=ContentSettings(content_type=content_type)
            )

        return f"https://videostudiomedia.blob.core.windows.net/{container}/{blob_name}"

    def _submit_job(self, image_url: str, audio_url: str, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url}/run",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "input": {
                    "input_type": "image",
                    "person_count": "single",
                    "prompt": prompt,
                    "image_url": image_url,
                    "wav_url": audio_url,
                    "width": 512,
                    "height": 512
                }
            }
        )
        return response.json()["id"]

    def _poll_job(self, job_id: str, timeout: int = 900) -> dict:
        start = time.time()
        while time.time() - start < timeout:
            response = requests.get(
                f"{self.base_url}/status/{job_id}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            result = response.json()
            status = result.get("status")

            if status == "COMPLETED":
                return result
            elif status == "FAILED":
                raise Exception(f"Job {job_id} failed: {result.get('error')}")

            time.sleep(10)

        raise Exception(f"Job {job_id} timed out after {timeout}s")

    def _process_chunk(self, idx: int, audio_path: str, image_url: str, prompt: str, max_retries: int = 3) -> tuple[int, bytes]:
        chunk_name = f"chunk_{idx:03d}_{int(time.time())}.wav"
        audio_url = self._upload_to_blob(audio_path, chunk_name)

        for attempt in range(max_retries):
            try:
                job_id = self._submit_job(image_url, audio_url, prompt)
                print(f"      Chunk {idx}: job {job_id[:8]}...")

                result = self._poll_job(job_id, timeout=900)

                video_b64 = result.get("output", {}).get("video", "")
                if video_b64.startswith("data:video/mp4;base64,"):
                    video_b64 = video_b64[len("data:video/mp4;base64,"):]

                return idx, base64.b64decode(video_b64)
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"      Chunk {idx}: retry {attempt + 1}/{max_retries}")
                    time.sleep(30)
                else:
                    raise

    def generate(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        prompt: str = "A person speaking naturally",
        max_workers: int = 2,
    ) -> str:
        if not self.available:
            raise RuntimeError("RunPod API key not configured")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        duration = self._get_audio_duration(audio_path)
        print(f"    InfiniteTalk: {duration:.1f}s audio")

        image_name = f"avatar_{int(time.time())}.png"
        image_url = self._upload_to_blob(image_path, image_name)

        if duration <= CHUNK_DURATION_SEC:
            audio_name = f"audio_{int(time.time())}.wav"
            audio_url = self._upload_to_blob(audio_path, audio_name)

            job_id = self._submit_job(image_url, audio_url, prompt)
            print(f"    Job submitted: {job_id}")

            result = self._poll_job(job_id)
            video_b64 = result.get("output", {}).get("video", "")
            if video_b64.startswith("data:video/mp4;base64,"):
                video_b64 = video_b64[len("data:video/mp4;base64,"):]

            with open(output_path, "wb") as f:
                f.write(base64.b64decode(video_b64))

            return str(output_path)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            chunks_dir = tmp_path / "chunks"
            videos_dir = tmp_path / "videos"
            chunks_dir.mkdir()
            videos_dir.mkdir()

            chunks = self._split_audio(audio_path, chunks_dir)
            print(f"    Split into {len(chunks)} chunks")

            video_files = {}
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._process_chunk, i, chunk, image_url, prompt): i
                    for i, chunk in enumerate(chunks)
                }

                for future in as_completed(futures):
                    idx, video_data = future.result()
                    video_path = videos_dir / f"video_{idx:03d}.mp4"
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    video_files[idx] = str(video_path)
                    print(f"      Chunk {idx}: done")

            concat_list = videos_dir / "concat.txt"
            with open(concat_list, "w") as f:
                for i in sorted(video_files.keys()):
                    f.write(f"file '{video_files[i]}'\n")

            print(f"    Stitching {len(video_files)} segments...")
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list), "-c", "copy", str(output_path)
            ], capture_output=True)

        return str(output_path)

    def generate_multi_speaker(
        self,
        segments: list[dict],
        output_path: str,
        max_workers: int = 2,
    ) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            videos_dir = tmp_path / "videos"
            videos_dir.mkdir()

            video_files = {}

            for idx, seg in enumerate(segments):
                speaker = seg.get("speaker", "rachel")
                audio_path = seg.get("audio_path")

                if not audio_path or not Path(audio_path).exists():
                    continue

                cast_member = get_cast_member(speaker)

                if not Path(cast_member.image_path).exists():
                    print(f"      Warning: {cast_member.image_path} not found, using rachel")
                    cast_member = CAST["rachel"]

                print(f"    Segment {idx}: {cast_member.name}")

                video_path = videos_dir / f"segment_{idx:03d}.mp4"
                self.generate(
                    image_path=cast_member.image_path,
                    audio_path=audio_path,
                    output_path=str(video_path),
                    prompt=cast_member.prompt,
                    max_workers=1,
                )
                video_files[idx] = str(video_path)

            concat_list = videos_dir / "concat.txt"
            with open(concat_list, "w") as f:
                for i in sorted(video_files.keys()):
                    f.write(f"file '{video_files[i]}'\n")

            print(f"    Concatenating {len(video_files)} speaker segments...")
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list), "-c", "copy", str(output_path)
            ], capture_output=True)

        return str(output_path)
