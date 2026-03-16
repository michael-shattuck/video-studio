import runpod
import subprocess
import tempfile
import base64
import os
import sys
import csv
from pathlib import Path

MODEL_DIR = os.environ.get("MODEL_DIR", "/app/HunyuanVideo-Avatar")
INITIALIZED = False


def setup_model():
    global INITIALIZED
    if INITIALIZED:
        return True

    import shutil
    total, used, free = shutil.disk_usage("/")
    print(f"Disk space: {free // (1024**3)}GB free of {total // (1024**3)}GB total")

    model_path = Path(MODEL_DIR)

    if not model_path.exists():
        print("First run: cloning HunyuanVideo-Avatar...")
        result = subprocess.run([
            "git", "clone", "--depth", "1",
            "https://github.com/Tencent-Hunyuan/HunyuanVideo-Avatar.git",
            str(model_path)
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")


    weights_dir = model_path / "weights" / "ckpts"
    if not weights_dir.exists() or not any(weights_dir.glob("**/*.pt")):
        print("Downloading model weights from HuggingFace...")
        weights_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([
            sys.executable, "-c",
            f"""
from huggingface_hub import snapshot_download
snapshot_download('tencent/HunyuanVideo-Avatar', local_dir='{model_path / "weights"}', local_dir_use_symlinks=False)
"""
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Model download failed: {result.stderr}\n{result.stdout}")

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
    csv_path = os.path.join(output_dir, "input.csv")

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["videoid", "image", "audio", "prompt", "fps"])
        writer.writerow(["test_video", image_path, audio_path, "A person talking", 25.0])

    model_path = Path(MODEL_DIR)
    weights_path = model_path / "weights" / "ckpts" / "hunyuan-video-t2v-720p" / "transformers" / "mp_rank_00_model_states_fp8.pt"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(model_path)
    env["MODEL_BASE"] = str(model_path / "weights")
    env["DISABLE_SP"] = "1"

    cmd = [
        sys.executable,
        str(model_path / "hymm_sp" / "sample_gpu_poor.py"),
        "--input", csv_path,
        "--ckpt", str(weights_path),
        "--sample-n-frames", "129",
        "--seed", "128",
        "--image-size", "704",
        "--cfg-scale", "7.5",
        "--infer-steps", "50",
        "--use-deepcache", "1",
        "--flow-shift-eval-video", "5.0",
        "--save-path", output_dir,
        "--use-fp8",
        "--infer-min",
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=str(model_path),
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )

    if result.returncode != 0:
        return {
            "error": f"Generation failed: {result.stderr}",
            "stdout": result.stdout,
        }

    output_videos = list(Path(output_dir).glob("**/*.mp4"))
    if not output_videos:
        return {
            "error": "No output video generated",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    with open(output_videos[0], "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode()

    os.unlink(image_path)
    os.unlink(audio_path)

    return {
        "video_base64": video_b64,
        "mode": mode,
    }


runpod.serverless.start({"handler": handler})
