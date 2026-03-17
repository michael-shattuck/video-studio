import torch
import base64
import io
import runpod
from transformers import AutoProcessor, MusicgenForConditionalGeneration
import scipy.io.wavfile

model = None
processor = None

def load_model():
    global model, processor
    if model is None:
        print("Loading MusicGen model...")
        processor = AutoProcessor.from_pretrained("facebook/musicgen-medium")
        model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-medium")
        model = model.to("cuda")
        print("Model loaded!")
    return model, processor

def handler(job):
    job_input = job["input"]
    
    prompt = job_input.get("prompt", "dramatic cinematic background music")
    duration = job_input.get("duration", 30)  # seconds
    
    model, processor = load_model()
    
    # Calculate tokens for duration (MusicGen generates ~50 tokens/sec at 32kHz)
    max_new_tokens = int(duration * 50)
    
    inputs = processor(
        text=[prompt],
        padding=True,
        return_tensors="pt",
    ).to("cuda")
    
    audio_values = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        guidance_scale=3.0,
    )
    
    # Convert to wav
    sampling_rate = model.config.audio_encoder.sampling_rate
    audio_data = audio_values[0, 0].cpu().numpy()
    
    # Save to buffer
    buffer = io.BytesIO()
    scipy.io.wavfile.write(buffer, rate=sampling_rate, data=audio_data)
    buffer.seek(0)
    
    audio_b64 = base64.b64encode(buffer.read()).decode()
    
    return {
        "audio": f"data:audio/wav;base64,{audio_b64}",
        "duration": duration,
        "prompt": prompt,
        "sampling_rate": sampling_rate,
    }

runpod.serverless.start({"handler": handler})
