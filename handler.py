import runpod
import subprocess
import tempfile
import base64
import os
import sys
from pathlib import Path

MODEL_DIR = os.environ.get("MODEL_DIR", "/app/HunyuanVideo-Avatar")
INITIALIZED = False


def setup_model():
    global INITIALIZED
    if INITIALIZED:
        return True

    model_path = Path(MODEL_DIR)

    if not model_path.exists():
        print("First run: cloning HunyuanVideo-Avatar...")
        subprocess.run([
            "git", "clone",
            "https://github.com/Tencent/HunyuanVideo-Avatar.git",
            str(model_path)
        ], check=True)

    req_file = model_path / "requirements.txt"
    if req_file.exists():
        print("Installing dependencies...")
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)
        ], check=True)

    ckpts = model_path / "ckpts"
    if not ckpts.exists() or not any(ckpts.iterdir()):
        print("Downloading model weights (this takes a few minutes on first run)...")
        subprocess.run([
            sys.executable, "-c",
            f"from huggingface_hub import snapshot_download; snapshot_download('tencent/HunyuanVideo-Avatar', local_dir='{ckpts}')"
        ], check=True)

    sys.path.insert(0, str(model_path))
    INITIALIZED = True
    print("Model ready!")
    return True


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
    setup_model()

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
        sys.executable, "inference.py",
        "--image_path", image_path,
        "--audio_path", audio_path,
        "--output_path", output_path,
        "--mode", mode,
    ]

    result = subprocess.run(
        cmd,
        cwd=MODEL_DIR,
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
