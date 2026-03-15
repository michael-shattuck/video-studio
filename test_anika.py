import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from video_studio.talking_head import AzureAvatarGenerator

def test_anika():
    gen = AzureAvatarGenerator(
        voice="jane",
        avatar="anika",
        use_photo_avatar=True,
    )

    print(f"Available: {gen.available}")
    print(f"Using photo avatar: {gen.use_photo_avatar}")
    print(f"Avatar: {gen.avatar}")
    print(f"Voice: {gen.voice}")

    if not gen.available:
        print("Azure Speech not configured!")
        return

    output_path = Path(__file__).parent / "output" / "test_anika.mp4"

    test_text = """
    [excited] Welcome to The Deep Dive! I'm Rachel, and today we're testing something incredible.
    [calm] Azure's VASA-1 technology can generate realistic facial expressions from just audio.
    [passionate] This is the future of content creation, and it's happening right now!
    """

    print(f"\nGenerating test video with anika + VASA-1...")
    print(f"Output: {output_path}")

    try:
        result = gen.generate(
            text=test_text,
            output_path=str(output_path),
            emotion="excited",
        )
        print(f"\nSuccess! Video saved to: {result}")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    test_anika()
