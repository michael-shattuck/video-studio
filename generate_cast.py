#!/usr/bin/env python3
import os
import sys
import base64
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import config

CAST_MEMBERS = {
    "drew": {
        "prompt": "Professional headshot of a man in his 40s with short dark hair, wearing a navy blazer over gray shirt, warm smile, neutral studio background, podcast guest appearance, high quality portrait photography",
        "gender": "male"
    },
    "marcus": {
        "prompt": "Professional headshot of a tall thin Black man in his 60s with short gray hair and reading glasses on his nose, wearing a tan cardigan over checkered shirt, distinguished professor look, neutral studio background, high quality portrait photography",
        "gender": "male"
    },
    "elena": {
        "prompt": "Professional headshot of a plus-size Black woman in her 50s with short natural gray hair and bold red lipstick, wearing a bright yellow blazer, powerful commanding presence, neutral studio background, high quality portrait photography",
        "gender": "female"
    },
    "james": {
        "prompt": "Professional headshot of a wiry white man in his 70s with wild white hair and bushy eyebrows, wearing a rumpled tweed jacket with elbow patches, eccentric intellectual look, neutral studio background, high quality portrait photography",
        "gender": "male"
    },
    "sophia": {
        "prompt": "Professional headshot of an Asian woman in her 30s with shoulder-length black hair, wearing a cream blazer, sharp intelligent expression, neutral studio background, debate participant appearance, high quality portrait photography",
        "gender": "female"
    },
    "michael": {
        "prompt": "Professional headshot of a stocky Middle Eastern man in his 40s with thick black beard and shaved head, wearing a black turtleneck, intense focused expression, neutral studio background, high quality portrait photography",
        "gender": "male"
    },
    "guest_male": {
        "prompt": "Professional headshot of a skinny young white man in his early 20s with messy blonde hair and acne scars, wearing an ill-fitting suit jacket, nervous eager expression, neutral studio background, first-time guest appearance, high quality portrait photography",
        "gender": "male"
    },
    "guest_female": {
        "prompt": "Professional headshot of a petite elderly Asian woman in her 70s with silver hair in a bun, wearing a jade green silk blouse with pearl necklace, serene wise expression, neutral studio background, high quality portrait photography",
        "gender": "female"
    },
    "debater_a": {
        "prompt": "Professional headshot of a large imposing Black man in his 40s with dreadlocks pulled back, wearing a crisp white dress shirt no jacket, athletic build, confident confrontational expression, neutral studio background, high quality portrait photography",
        "gender": "male"
    },
    "debater_b": {
        "prompt": "Professional headshot of a short stocky Latino man in his 50s with slicked-back gray hair and thick mustache, wearing a pinstripe vest over purple shirt, fiery passionate expression, neutral studio background, high quality portrait photography",
        "gender": "male"
    },
    "panelist_1": {
        "prompt": "Professional headshot of a very tall thin white woman in her 60s with long straight gray hair, wearing oversized round glasses and a black mock neck, stern intellectual expression, neutral studio background, high quality portrait photography",
        "gender": "female"
    },
    "panelist_2": {
        "prompt": "Professional headshot of a heavyset South Asian man in his 30s with thick black hair and full beard, wearing a bright blue kurta, jovial warm expression, neutral studio background, high quality portrait photography",
        "gender": "male"
    },
    "panelist_3": {
        "prompt": "Professional headshot of a fit Black woman in her 40s with very short natural hair almost shaved, wearing a leather jacket over white t-shirt, sharp no-nonsense expression, neutral studio background, high quality portrait photography",
        "gender": "female"
    },
}


def generate_cast_images(members: list[str] = None, delay: int = 15):
    endpoint = config.azure_openai_foundry_endpoint
    key = config.azure_openai_foundry_key

    if not endpoint or not key:
        print("Error: Azure OpenAI not configured")
        return

    cast_dir = Path(config.assets_dir) / "cast"
    cast_dir.mkdir(parents=True, exist_ok=True)

    gen_url = f"{endpoint}openai/deployments/gpt-image/images/generations?api-version=2024-05-01-preview"

    to_generate = members or list(CAST_MEMBERS.keys())

    for name in to_generate:
        if name not in CAST_MEMBERS:
            print(f"Unknown cast member: {name}")
            continue

        output_path = cast_dir / f"{name}.png"
        if output_path.exists():
            print(f"  {name}: exists, skipping")
            continue

        member = CAST_MEMBERS[name]
        print(f"  {name}...", end=" ", flush=True)

        response = requests.post(
            gen_url,
            headers={"api-key": key, "Content-Type": "application/json"},
            json={
                "prompt": member["prompt"],
                "n": 1,
                "size": "1024x1024",
                "quality": "high"
            },
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            img_b64 = result["data"][0].get("b64_json")
            if img_b64:
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(img_b64))
                print("done")
            else:
                print("no image data")
        else:
            print(f"failed ({response.status_code})")

        time.sleep(delay)

    print(f"\nCast images saved to: {cast_dir}")


if __name__ == "__main__":
    members = sys.argv[1:] if len(sys.argv) > 1 else None
    generate_cast_images(members)
