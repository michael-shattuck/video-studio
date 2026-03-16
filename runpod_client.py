import os
import time
import uuid
import base64
import requests
from pathlib import Path
from azure.storage.blob import BlobServiceClient


class RunPodAvatarClient:
    def __init__(self):
        self.api_key = os.environ.get("RUNPOD_API_KEY")
        self.endpoint_id = os.environ.get("RUNPOD_AVATAR_ENDPOINT")
        self.storage_connection = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = os.environ.get("AZURE_STORAGE_CONTAINER", "media")

        if not self.api_key or not self.endpoint_id:
            raise ValueError("RUNPOD_API_KEY and RUNPOD_AVATAR_ENDPOINT must be set")

        self.base_url = f"https://api.runpod.ai/v2/{self.endpoint_id}"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        if self.storage_connection:
            self.blob_service = BlobServiceClient.from_connection_string(self.storage_connection)
            self.container_client = self.blob_service.get_container_client(self.container_name)
        else:
            self.blob_service = None
            self.container_client = None

    def upload_to_blob(self, file_path: str, blob_name: str = None) -> str:
        if not self.container_client:
            raise ValueError("Azure Storage not configured")

        file_path = Path(file_path)
        if not blob_name:
            blob_name = f"{uuid.uuid4().hex}_{file_path.name}"

        blob_client = self.container_client.get_blob_client(blob_name)

        with open(file_path, "rb") as f:
            blob_client.upload_blob(f, overwrite=True)

        return blob_client.url

    def generate_avatar_video(
        self,
        image_path: str,
        audio_path: str,
        mode: str = "upper_body",
        poll_interval: int = 5,
        timeout: int = 600,
    ) -> bytes:
        image_path = Path(image_path)
        audio_path = Path(audio_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio not found: {audio_path}")

        image_size = image_path.stat().st_size
        audio_size = audio_path.stat().st_size
        total_size = image_size + audio_size

        if total_size > 7 * 1024 * 1024:
            print(f"Files too large for direct upload ({total_size // 1024}KB), using Azure Blob...")
            image_url = self.upload_to_blob(str(image_path))
            audio_url = self.upload_to_blob(str(audio_path))
            print(f"Uploaded to: {image_url}")
            print(f"Uploaded to: {audio_url}")
            payload = {
                "input": {
                    "source_image": image_url,
                    "audio": audio_url,
                    "mode": mode,
                }
            }
        else:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()
            with open(audio_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()

            payload = {
                "input": {
                    "source_image": f"data:image/png;base64,{image_b64}",
                    "audio": f"data:audio/wav;base64,{audio_b64}",
                    "mode": mode,
                }
            }

        print("Submitting job to RunPod...")
        resp = requests.post(f"{self.base_url}/run", headers=self.headers, json=payload)
        resp.raise_for_status()
        job = resp.json()
        job_id = job["id"]
        print(f"Job ID: {job_id}")

        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Job {job_id} timed out after {timeout}s")

            status_resp = requests.get(f"{self.base_url}/status/{job_id}", headers=self.headers)
            status_resp.raise_for_status()
            status = status_resp.json()

            if status["status"] == "COMPLETED":
                print("Job completed!")
                output = status.get("output", {})
                video_b64 = output.get("video_base64")
                if not video_b64:
                    raise RuntimeError(f"No video in output: {output}")
                return base64.b64decode(video_b64)

            elif status["status"] == "FAILED":
                error = status.get("error", "Unknown error")
                raise RuntimeError(f"Job failed: {error}")

            elif status["status"] in ("IN_QUEUE", "IN_PROGRESS"):
                elapsed = int(time.time() - start_time)
                print(f"Status: {status['status']} ({elapsed}s elapsed)")
                time.sleep(poll_interval)

            else:
                print(f"Unknown status: {status}")
                time.sleep(poll_interval)

    def generate_and_save(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        mode: str = "upper_body",
    ) -> str:
        video_bytes = self.generate_avatar_video(image_path, audio_path, mode)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(video_bytes)

        print(f"Saved to: {output_path}")
        return str(output_path)


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    if len(sys.argv) < 3:
        print("Usage: python runpod_client.py <image_path> <audio_path> [output_path]")
        sys.exit(1)

    image_path = sys.argv[1]
    audio_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else "output/avatar_video.mp4"

    client = RunPodAvatarClient()
    client.generate_and_save(image_path, audio_path, output_path)
