FROM hunyuanvideo/hunyuanvideo:cuda_12

ENV MODEL_DIR=/app/HunyuanVideo-Avatar

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender1 \
    libfontconfig1 libice6 libxinerama1 libxi6 libxrandr2 libxcursor1 \
    libxdamage1 libxfixes3 libxcomposite1 libxss1 libxtst6 libnss3 \
    libnspr4 libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libdbus-1-3 libexpat1 libgbm1 libgtk-3-0 libpango-1.0-0 libcairo2 \
    libgdk-pixbuf2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir runpod requests decord librosa "transformers==4.41.2" "diffusers==0.33.0"

RUN pip install --no-cache-dir --force-reinstall "numpy==1.26.4"

COPY handler.py /app/handler.py

CMD ["python", "-u", "/app/handler.py"]
