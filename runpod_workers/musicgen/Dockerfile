FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    transformers \
    accelerate \
    scipy \
    runpod

# Pre-download model for faster cold starts
RUN python -c "from transformers import AutoProcessor, MusicgenForConditionalGeneration; \
    AutoProcessor.from_pretrained('facebook/musicgen-medium'); \
    MusicgenForConditionalGeneration.from_pretrained('facebook/musicgen-medium')"

COPY handler.py /app/handler.py

CMD ["python", "-u", "handler.py"]
