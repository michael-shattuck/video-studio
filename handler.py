import runpod
import subprocess
import tempfile
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app/HunyuanVideo-Avatar")


def download_file(url_or_base64: str, suffix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

    if url_or_base64.startswith("data:") or len(url_or_base64) > 1000:
        if url_or_base64.startswith("data:"):
            url_or_base64 = url_or_base64.split(",", 1)[1]
        tmp.write(base64.b64decode(url_or_base64))
    else:
        import requests
        resp = requests.get(url_or_base64, timeout=120)
        resp.raise_for_status()
        tmp.write(resp.content)

    tmp.close()
    return tmp.name


def handler(job):
    job_input = job["input"]

    source_image = job_input.get("source_image")
    audio = job_input.get("audio")
    mode = job_input.get("mode", "upper_body")

    if not source_image or not audio:
        return {"error": "source_image and audio are required"}

    image_path = download_file(source_image, ".png")
    audio_path = download_file(audio, ".wav")

    output_dir = tempfile.mkdtemp()
    output_path = os.path.join(output_dir, "output.mp4")

    cmd = [
        "python", "inference.py",
        "--image_path", image_path,
        "--audio_path", audio_path,
        "--output_path", output_path,
        "--mode", mode,
    ]

    result = subprocess.run(
        cmd,
        cwd="/app/HunyuanVideo-Avatar",
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        return {
            "error": f"Generation failed: {result.stderr}",
            "stdout": result.stdout,
        }

    with open(output_path, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode()

    os.unlink(image_path)
    os.unlink(audio_path)
    os.unlink(output_path)
    os.rmdir(output_dir)

    return {
        "video_base64": video_b64,
        "mode": mode,
    }


runpod.serverless.start({"handler": handler})
