FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

WORKDIR /app

RUN pip install --no-cache-dir \
    runpod \
    diffusers==0.20.2 \
    transformers \
    accelerate \
    safetensors \
    pillow

RUN python -c "from diffusers import DiffusionPipeline; DiffusionPipeline.from_pretrained('sudo-ai/zero123plus-v1.2', custom_pipeline='sudo-ai/zero123plus-pipeline')"

COPY handler.py /app/handler.py

CMD ["python", "-u", "handler.py"]
