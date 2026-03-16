#!/usr/bin/env python3
import os
import sys
import json
import time
import base64
import tempfile
import subprocess
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from azure.storage.blob import BlobServiceClient, ContentSettings

CHUNK_DURATION_SEC = 30
RUNPOD_INFINITETALK_ENDPOINT = "47dp49svgwgb8y"

class ChunkGenerator:
    def __init__(self):
        self.api_key = os.environ["RUNPOD_API_KEY"]
        self.conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
        self.container = os.environ["AZURE_STORAGE_CONTAINER"]
        self.blob_service = BlobServiceClient.from_connection_string(self.conn_str)
        self.container_client = self.blob_service.get_container_client(self.container)

    def split_audio(self, audio_path: str, output_dir: str) -> list[str]:
        audio_path = Path(audio_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip())

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

        print(f"Split audio into {len(chunks)} chunks")
        return chunks

    def upload_chunk(self, chunk_path: str, name: str) -> str:
        with open(chunk_path, "rb") as f:
            self.container_client.upload_blob(
                name, f, overwrite=True,
                content_settings=ContentSettings(content_type="audio/wav")
            )
        return f"https://videostudiomedia.blob.core.windows.net/{self.container}/{name}"

    def submit_job(self, image_url: str, audio_url: str, prompt: str) -> str:
        response = requests.post(
            f"https://api.runpod.ai/v2/{RUNPOD_INFINITETALK_ENDPOINT}/run",
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

    def poll_job(self, job_id: str, timeout: int = 600) -> dict:
        start = time.time()
        while time.time() - start < timeout:
            response = requests.get(
                f"https://api.runpod.ai/v2/{RUNPOD_INFINITETALK_ENDPOINT}/status/{job_id}",
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

    def process_chunk(self, idx: int, chunk_path: str, image_url: str, prompt: str, max_retries: int = 3) -> tuple[int, str]:
        chunk_name = f"chunk_{idx:03d}.wav"
        audio_url = self.upload_chunk(chunk_path, chunk_name)
        print(f"Chunk {idx}: Uploaded audio")

        for attempt in range(max_retries):
            try:
                job_id = self.submit_job(image_url, audio_url, prompt)
                print(f"Chunk {idx}: Submitted job {job_id} (attempt {attempt + 1})")

                result = self.poll_job(job_id, timeout=900)
                print(f"Chunk {idx}: Completed")

                video_b64 = result.get("output", {}).get("video", "")
                if video_b64.startswith("data:video/mp4;base64,"):
                    video_b64 = video_b64[len("data:video/mp4;base64,"):]

                return idx, video_b64
            except Exception as e:
                if "Connection refused" in str(e) or "time" in str(e):
                    print(f"Chunk {idx}: Cold start error, retrying in 30s... ({attempt + 1}/{max_retries})")
                    time.sleep(30)
                else:
                    raise

        raise Exception(f"Chunk {idx} failed after {max_retries} retries")

    def generate(self, audio_path: str, image_url: str, prompt: str, output_path: str, max_workers: int = 3):
        with tempfile.TemporaryDirectory() as tmp_dir:
            chunks_dir = Path(tmp_dir) / "chunks"
            videos_dir = Path(tmp_dir) / "videos"
            videos_dir.mkdir(parents=True, exist_ok=True)

            chunks = self.split_audio(audio_path, str(chunks_dir))

            video_files = {}
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self.process_chunk, i, chunk, image_url, prompt): i
                    for i, chunk in enumerate(chunks)
                }

                for future in as_completed(futures):
                    idx, video_b64 = future.result()
                    video_path = videos_dir / f"video_{idx:03d}.mp4"
                    with open(video_path, "wb") as f:
                        f.write(base64.b64decode(video_b64))
                    video_files[idx] = str(video_path)

            concat_list = videos_dir / "concat.txt"
            with open(concat_list, "w") as f:
                for i in sorted(video_files.keys()):
                    f.write(f"file '{video_files[i]}'\n")

            print(f"Stitching {len(video_files)} video segments...")
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list), "-c", "copy", output_path
            ], capture_output=True)

            print(f"Output saved to: {output_path}")


def main():
    if len(sys.argv) < 4:
        print("Usage: chunk_generator.py <audio_path> <image_url> <output_path> [prompt]")
        sys.exit(1)

    audio_path = sys.argv[1]
    image_url = sys.argv[2]
    output_path = sys.argv[3]
    prompt = sys.argv[4] if len(sys.argv) > 4 else "A woman hosting a podcast, speaking naturally"

    generator = ChunkGenerator()
    generator.generate(audio_path, image_url, prompt, output_path, max_workers=1)


if __name__ == "__main__":
    main()
