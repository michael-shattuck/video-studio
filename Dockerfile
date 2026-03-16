FROM nvidia/cuda:12.4.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV HF_HOME=/app/huggingface
ENV MODEL_DIR=/app/HunyuanVideo-Avatar

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3-pip \
    git ffmpeg libsm6 libxext6 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3.11 /usr/bin/python

RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

RUN pip install --no-cache-dir \
    runpod requests huggingface_hub \
    "transformers>=4.50.0" "diffusers==0.33.0" accelerate \
    opencv-python einops tqdm loguru imageio imageio-ffmpeg \
    safetensors decord librosa scikit-video pandas numpy

COPY handler.py /app/handler.py

CMD ["python", "-u", "/app/handler.py"]
