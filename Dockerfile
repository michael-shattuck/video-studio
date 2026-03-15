FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

ENV HF_HOME=/app/huggingface
ENV MODEL_DIR=/app/HunyuanVideo-Avatar

WORKDIR /app

RUN apt-get update && apt-get install -y git ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir runpod requests huggingface_hub

COPY handler.py /app/handler.py

CMD ["python", "-u", "/app/handler.py"]
