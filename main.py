import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from video_studio.pipeline import VideoPipeline
from video_studio.voice_generator import VOICE_PRESETS, VOICE_STYLES


async def find_trending_topics(count: int = 15, show_evergreen: bool = True):
    from video_studio.topic_finder import TopicFinder
    finder = TopicFinder()

    print("=" * 60)
    print("TRENDING CONTROVERSIAL TOPICS")
    print("=" * 60 + "\n")

    topics = await finder.get_topics_for_video(count=count)

    for i, t in enumerate(topics, 1):
        controversy_bar = "+" * int(t['controversy_score'] * 10)
        print(f"{i:2}. [{t['source']:15}] {t['topic'][:65]}")
        print(f"    Controversy: [{controversy_bar:10}] | {t['category']}")
        print()

    if show_evergreen:
        print("\n" + "=" * 60)
        print("EVERGREEN CONTROVERSIAL TOPICS (always hot)")
        print("=" * 60 + "\n")

        evergreen = finder.get_evergreen_controversial()
        for i, t in enumerate(evergreen, 1):
            print(f"{i:2}. [{t['category']:12}] {t['topic']}")

    print("\n" + "-" * 60)
    print("Usage: python -m main --style turboencabulator \"<topic>\"")
    print("-" * 60)

    return topics


async def main():
    parser = argparse.ArgumentParser(description="Automated Faceless YouTube Video Studio")
    parser.add_argument(
        "topic",
        nargs="?",
        help="Topic to create video about",
    )
    parser.add_argument(
        "--topics",
        "-t",
        nargs="+",
        help="Multiple topics for batch creation",
    )
    parser.add_argument(
        "--find-topics",
        action="store_true",
        help="Find trending controversial topics",
    )
    parser.add_argument(
        "--topic-count",
        type=int,
        default=15,
        help="Number of topics to find (with --find-topics)",
    )
    parser.add_argument(
        "--random-topic",
        action="store_true",
        help="Pick a random trending or evergreen topic and generate",
    )
    parser.add_argument(
        "--evergreen",
        action="store_true",
        help="Use evergreen topics instead of trending (with --random-topic)",
    )
    parser.add_argument(
        "--style",
        "-s",
        default="educational",
        choices=["educational", "storytelling", "listicle", "documentary", "motivational", "relaxing", "turboencabulator"],
        help="Video style (turboencabulator = absurdist doublespeak satire)",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=8,
        help="Target duration in minutes",
    )
    parser.add_argument(
        "--voice",
        "-v",
        default="female_narrator",
        choices=list(VOICE_PRESETS.keys()),
        help="Voice preset to use",
    )
    parser.add_argument(
        "--voice-style",
        default="documentary",
        choices=list(VOICE_STYLES.keys()),
        help="Voice style (pacing/tone)",
    )
    parser.add_argument(
        "--no-footage",
        action="store_true",
        help="Skip stock footage (black background)",
    )
    parser.add_argument(
        "--no-music",
        action="store_true",
        help="Skip background music",
    )
    parser.add_argument(
        "--music-volume",
        type=float,
        default=0.12,
        help="Background music volume (0.0-1.0, default 0.12)",
    )
    parser.add_argument(
        "--from-niche-finder",
        "-f",
        action="store_true",
        help="Use top opportunities from niche_finder results",
    )
    parser.add_argument(
        "--count",
        "-c",
        type=int,
        default=3,
        help="Number of videos to create from niche finder",
    )
    parser.add_argument(
        "--short",
        action="store_true",
        help="Create vertical short/TikTok format (9:16, 60 seconds)",
    )
    parser.add_argument(
        "--voice-only",
        action="store_true",
        help="Only generate script and voice (skip video assembly)",
    )
    parser.add_argument(
        "--script-only",
        action="store_true",
        help="Only generate script (skip voice and video)",
    )
    parser.add_argument(
        "--tts-engine",
        default="azure-openai",
        choices=["auto", "azure-openai", "azure", "edge", "openai", "elevenlabs", "bark", "fish", "xtts"],
        help="TTS engine (azure-openai=GPT-4o audio, edge=free, azure=SSML, xtts=local)",
    )
    parser.add_argument(
        "--elevenlabs-voice-id",
        default=None,
        help="ElevenLabs voice ID (find at elevenlabs.io/voice-library)",
    )
    parser.add_argument(
        "--approve-script",
        action="store_true",
        help="Review and approve script before generating voice",
    )
    parser.add_argument(
        "--script-file",
        type=str,
        default=None,
        help="Use existing script JSON file instead of generating",
    )
    parser.add_argument(
        "--format",
        default="monologue",
        choices=["monologue", "interview", "panel", "debate"],
        help="Script format: monologue (default), interview (host+guest), panel (multiple guests), debate (adversarial)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.15,
        help="Voice speed multiplier (default 1.15 for natural conversation, 1.0=normal, 1.3=fast)",
    )
    parser.add_argument(
        "--talking-head",
        action="store_true",
        help="Generate talking head video from avatar image",
    )
    parser.add_argument(
        "--avatar",
        type=str,
        default=None,
        help="Path to avatar image for talking head generation",
    )
    parser.add_argument(
        "--talking-head-backend",
        default="auto",
        choices=["auto", "azure", "memo", "hallo"],
        help="Talking head backend (azure=cloud/no GPU, memo=best expressions, hallo=fastest)",
    )
    parser.add_argument(
        "--avatar-voice",
        default="jane",
        choices=["female", "male", "jane", "jenny", "aria", "sara", "guy", "davis", "jason", "tony"],
        help="Azure Avatar voice (jane=default, guy=male, aria/sara=female alt, davis/jason/tony=male alt)",
    )
    parser.add_argument(
        "--avatar-character",
        default="anika",
        choices=["anika", "harry", "jeff", "lisa", "lori", "max", "meg"],
        help="Azure Avatar character (anika=photo avatar with VASA-1, others=standard avatars)",
    )
    parser.add_argument(
        "--avatar-style",
        default="",
        help="Azure Avatar style (for standard avatars only, ignored for photo avatars)",
    )
    parser.add_argument(
        "--photo-avatar",
        action="store_true",
        default=True,
        help="Use photo avatar with VASA-1 (default: True for anika)",
    )
    parser.add_argument(
        "--standard-avatar",
        action="store_true",
        help="Use standard avatar instead of photo avatar",
    )

    args = parser.parse_args()

    if args.find_topics:
        await find_trending_topics(args.topic_count)
        return

    if args.random_topic:
        import random
        from video_studio.topic_finder import TopicFinder
        finder = TopicFinder()

        if args.evergreen:
            evergreen = finder.get_evergreen_controversial()
            chosen = random.choice(evergreen)
            args.topic = chosen["topic"]
            print(f"Selected evergreen topic: {args.topic}\n")
        else:
            topics = await finder.get_topics_for_video(count=20)
            if topics:
                chosen = random.choice(topics[:10])
                args.topic = chosen["topic"]
                print(f"Selected trending topic: {args.topic}\n")
            else:
                evergreen = finder.get_evergreen_controversial()
                chosen = random.choice(evergreen)
                args.topic = chosen["topic"]
                print(f"No trending topics found, using evergreen: {args.topic}\n")

    if not args.topic and not args.topics and not args.from_niche_finder:
        parser.print_help()
        print("\nTip: Use --find-topics to discover trending controversial topics")
        return

    duration = 1 if args.short else args.duration
    use_photo_avatar = not args.standard_avatar and (args.photo_avatar or args.avatar_character == "anika")
    pipeline = VideoPipeline(
        voice=args.voice,
        voice_style=args.voice_style,
        is_short=args.short,
        video_style=args.style,
        tts_engine=args.tts_engine,
        elevenlabs_voice_id=args.elevenlabs_voice_id,
        voice_speed=args.speed,
        talking_head=args.talking_head_backend if args.talking_head else None,
        avatar_image=args.avatar,
        avatar_voice=args.avatar_voice,
        avatar_character=args.avatar_character,
        avatar_style=args.avatar_style,
        use_photo_avatar=use_photo_avatar,
    )

    if args.from_niche_finder:
        import json
        niche_file = Path(__file__).parent.parent / "niche_finder" / "data" / "opportunities.json"
        if not niche_file.exists():
            print("No niche_finder results found. Run niche_finder first.")
            return

        with open(niche_file) as f:
            opportunities = json.load(f)

        topics = [opp["keyword"] for opp in opportunities[:args.count]]
        print(f"Creating videos for top {len(topics)} niches:")
        for t in topics:
            print(f"  - {t}")

        await pipeline.batch_create(topics, args.style, duration)

    elif args.topics:
        await pipeline.batch_create(args.topics, args.style, duration)

    elif args.topic or args.script_file:
        await pipeline.create_video(
            args.topic or "custom",
            args.style,
            duration,
            skip_footage=args.no_footage,
            add_music=not args.no_music,
            music_volume=args.music_volume,
            voice_only=args.voice_only,
            script_only=args.script_only,
            approve_script=args.approve_script,
            script_file=args.script_file,
            script_format=args.format,
            use_talking_head=args.talking_head,
            avatar_image=args.avatar,
        )

    else:
        parser.print_help()


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
