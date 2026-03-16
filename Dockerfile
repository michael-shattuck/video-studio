FROM hunyuanvideo/hunyuanvideo:cuda_12

ENV MODEL_DIR=/app/HunyuanVideo-Avatar

WORKDIR /app

RUN apt-get update && apt-get install -y libgl1 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir runpod requests

RUN pip install --no-cache-dir "transformers==4.41.2" "diffusers==0.33.0"

COPY handler.py /app/handler.py

CMD ["python", "-u", "/app/handler.py"]
