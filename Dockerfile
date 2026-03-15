FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Tencent/HunyuanVideo-Avatar.git /app/HunyuanVideo-Avatar

WORKDIR /app/HunyuanVideo-Avatar

RUN pip install -r requirements.txt
RUN pip install runpod boto3

RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('tencent/HunyuanVideo-Avatar', local_dir='ckpts')"

COPY handler.py /app/handler.py

CMD ["python", "-u", "/app/handler.py"]
