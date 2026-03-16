import torch
import base64
import io
import os
import runpod
from PIL import Image
from huggingface_hub import snapshot_download

pipeline = None
automasker = None

def load_models():
    global pipeline, automasker
    if pipeline is None:
        from model.pipeline import CatVTONPipeline
        from model.cloth_masker import AutoMasker

        model_path = snapshot_download(repo_id="zhengchong/CatVTON")

        pipeline = CatVTONPipeline(
            base_ckpt="runwayml/stable-diffusion-inpainting",
            attn_ckpt=model_path,
            attn_ckpt_version="mix",
            weight_dtype=torch.bfloat16,
            device="cuda"
        )

        automasker = AutoMasker(
            densepose_ckpt=os.path.join(model_path, "DensePose"),
            schp_ckpt=os.path.join(model_path, "SCHP"),
            device="cuda"
        )
    return pipeline, automasker

def handler(job):
    job_input = job["input"]

    person_b64 = job_input.get("person_image")
    cloth_b64 = job_input.get("cloth_image")
    cloth_type = job_input.get("cloth_type", "upper")  # upper, lower, overall
    num_steps = job_input.get("num_inference_steps", 50)
    guidance = job_input.get("guidance_scale", 2.5)
    seed = job_input.get("seed", -1)

    if not person_b64 or not cloth_b64:
        return {"error": "Both person_image and cloth_image required"}

    person_img = Image.open(io.BytesIO(base64.b64decode(person_b64))).convert("RGB")
    cloth_img = Image.open(io.BytesIO(base64.b64decode(cloth_b64))).convert("RGB")

    pipe, masker = load_models()

    # Auto-generate mask
    mask = masker(person_img, cloth_type)["mask"]

    # Run inference
    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator(device="cuda").manual_seed(seed)

    result = pipe(
        image=person_img,
        condition_image=cloth_img,
        mask=mask,
        num_inference_steps=num_steps,
        guidance_scale=guidance,
        generator=generator
    )[0]

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    result_b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "image": result_b64,
        "seed": seed
    }

runpod.serverless.start({"handler": handler})
