import requests
import base64
from pathlib import Path
from config import config


def generate_rachel_avatar(style: str = "professional", save_path: str = None) -> str:
    prompt = f"""Professional headshot photo of Rachel, a podcast host in her early 30s.

Style: {style}
- Confident, intelligent expression with a hint of playful skepticism
- Sharp eyes that suggest she's about to reveal something surprising
- Professional but approachable appearance
- Well-lit studio photography, shallow depth of field
- Looking slightly off-camera, engaged in thought
- Natural makeup, polished but not overdone
- Neutral background suitable for video overlay

The kind of face that could deliver serious journalism one moment and absurdist comedy the next.
Photorealistic, high resolution, suitable for AI avatar generation."""

    url = f"{config.azure_openai_foundry_endpoint}openai/deployments/{config.azure_dalle_deployment}/images/generations?api-version=2025-04-01-preview"

    headers = {
        "api-key": config.azure_openai_foundry_key,
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "quality": "high"
    }

    print(f"Generating Rachel avatar ({style} style)...")
    response = requests.post(url, headers=headers, json=payload, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(f"Image generation failed: {response.status_code} {response.text}")

    data = response.json()
    image_b64 = data["data"][0]["b64_json"]
    image_bytes = base64.b64decode(image_b64)

    if save_path is None:
        save_path = Path(config.assets_dir) / "rachel_avatar.png"
    else:
        save_path = Path(save_path)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(image_bytes)

    print(f"Saved: {save_path}")
    return str(save_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Rachel avatar for talking head videos")
    parser.add_argument(
        "--style",
        default="professional",
        choices=["professional", "casual", "dramatic", "quirky"],
        help="Avatar style"
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output path (default: assets/rachel_avatar.png)"
    )
    parser.add_argument(
        "--variations",
        "-n",
        type=int,
        default=1,
        help="Generate multiple variations"
    )

    args = parser.parse_args()

    if args.variations > 1:
        for i in range(args.variations):
            output = Path(config.assets_dir) / f"rachel_avatar_{args.style}_{i+1}.png"
            generate_rachel_avatar(args.style, str(output))
    else:
        generate_rachel_avatar(args.style, args.output)
