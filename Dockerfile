FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

ENV HF_HOME=/app/huggingface
ENV MODEL_DIR=/app/HunyuanVideo-Avatar

WORKDIR /app

RUN apt-get update && apt-get install -y git ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir runpod requests huggingface_hub \
    && pip install --no-cache-dir "transformers>=4.50.0" "diffusers==0.33.0" accelerate

COPY handler.py /app/handler.py

CMD ["python", "-u", "/app/handler.py"]
