FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-devel

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    git \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Clone CatVTON
RUN git clone https://github.com/Zheng-Chong/CatVTON.git /app/catvton

WORKDIR /app/catvton

# Install Python deps
RUN pip install --no-cache-dir \
    runpod \
    diffusers==0.27.2 \
    transformers \
    accelerate \
    safetensors \
    pillow \
    huggingface_hub \
    opencv-python-headless

# Install detectron2 for DensePose
RUN pip install 'git+https://github.com/facebookresearch/detectron2.git'

# Install DensePose
RUN pip install 'git+https://github.com/facebookresearch/detectron2@main#subdirectory=projects/DensePose'

# Pre-download models
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('zhengchong/CatVTON')"
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('runwayml/stable-diffusion-inpainting')"

COPY handler.py /app/catvton/handler.py

CMD ["python", "-u", "handler.py"]
