import torch
import base64
import io
import runpod
from PIL import Image
from diffusers import DiffusionPipeline, EulerAncestralDiscreteScheduler

pipeline = None

def load_model():
    global pipeline
    if pipeline is None:
        pipeline = DiffusionPipeline.from_pretrained(
            "sudo-ai/zero123plus-v1.2",
            custom_pipeline="sudo-ai/zero123plus-pipeline",
            torch_dtype=torch.float16
        )
        pipeline.scheduler = EulerAncestralDiscreteScheduler.from_config(
            pipeline.scheduler.config, timestep_spacing='trailing'
        )
        pipeline.to('cuda:0')
    return pipeline

def handler(job):
    job_input = job["input"]

    image_b64 = job_input.get("image")
    num_steps = job_input.get("num_inference_steps", 75)

    if not image_b64:
        return {"error": "No image provided"}

    image_data = base64.b64decode(image_b64)
    cond = Image.open(io.BytesIO(image_data)).convert("RGB")

    min_dim = min(cond.size)
    left = (cond.width - min_dim) // 2
    top = (cond.height - min_dim) // 2
    cond = cond.crop((left, top, left + min_dim, top + min_dim))
    cond = cond.resize((320, 320), Image.LANCZOS)

    pipe = load_model()
    result = pipe(cond, num_inference_steps=num_steps).images[0]

    views = []
    view_size = result.width // 3
    for row in range(2):
        for col in range(3):
            x = col * view_size
            y = row * view_size
            view = result.crop((x, y, x + view_size, y + view_size))
            buf = io.BytesIO()
            view.save(buf, format="PNG")
            views.append(base64.b64encode(buf.getvalue()).decode())

    full_buf = io.BytesIO()
    result.save(full_buf, format="PNG")
    full_b64 = base64.b64encode(full_buf.getvalue()).decode()

    return {
        "full_grid": full_b64,
        "views": views
    }

runpod.serverless.start({"handler": handler})
