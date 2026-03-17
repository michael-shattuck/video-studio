import os
import random
from pathlib import Path
from dataclasses import dataclass

from moviepy import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
    ColorClip,
    vfx,
)

from .config import config


@dataclass
class AssemblyConfig:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    background_color: tuple = (0, 0, 0)
    text_color: str = "white"
    font: str = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    font_size: int = 60
    is_short: bool = False

    @classmethod
    def for_short(cls):
        return cls(width=1080, height=1920, is_short=True, font_size=48)


class VideoAssembler:
    def __init__(self, assembly_config: AssemblyConfig = None):
        self.config = assembly_config or AssemblyConfig()

    def assemble(
        self,
        audio_path: str,
        footage_paths: list[str],
        output_path: str,
        subtitles: list[dict] = None,
        key_phrases: list[dict] = None,
    ) -> str:
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration

        if not footage_paths:
            video = ColorClip(
                size=(self.config.width, self.config.height),
                color=self.config.background_color,
                duration=total_duration
            )
        else:
            video = self._create_footage_sequence(footage_paths, total_duration)

        video = video.with_audio(audio)

        if subtitles:
            video = self._add_subtitles(video, subtitles)

        if key_phrases:
            video = self._add_key_phrases(video, key_phrases)

        video.write_videofile(
            output_path,
            fps=self.config.fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="medium",
        )

        audio.close()
        video.close()

        return output_path

    def _create_footage_sequence(self, footage_paths: list[str], total_duration: float) -> VideoFileClip:
        clips = []
        remaining_duration = total_duration

        footage_cycle = footage_paths.copy()
        random.shuffle(footage_cycle)
        idx = 0

        while remaining_duration > 0:
            if idx >= len(footage_cycle):
                random.shuffle(footage_cycle)
                idx = 0

            path = footage_cycle[idx]
            idx += 1

            try:
                if path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    use_duration = min(remaining_duration, 5)
                    clip = ImageClip(path).with_duration(use_duration)
                    clip = self._fit_clip(clip)
                else:
                    clip = VideoFileClip(path)
                    clip = self._fit_clip(clip)
                    use_duration = min(clip.duration, remaining_duration, 8)
                    if clip.duration > use_duration:
                        start = random.uniform(0, max(0, clip.duration - use_duration))
                        clip = clip.subclipped(start, start + use_duration)

                clips.append(clip)
                remaining_duration -= use_duration

            except Exception:
                continue

        if not clips:
            return ColorClip(
                size=(self.config.width, self.config.height),
                color=self.config.background_color,
                duration=total_duration
            )

        return concatenate_videoclips(clips, method="compose")

    def _fit_clip(self, clip: VideoFileClip) -> VideoFileClip:
        target_ratio = self.config.width / self.config.height
        clip_ratio = clip.w / clip.h

        if clip_ratio > target_ratio:
            new_width = int(clip.h * target_ratio)
            x_center = clip.w / 2
            clip = clip.cropped(x1=x_center - new_width/2, x2=x_center + new_width/2)
        elif clip_ratio < target_ratio:
            new_height = int(clip.w / target_ratio)
            y_center = clip.h / 2
            clip = clip.cropped(y1=y_center - new_height/2, y2=y_center + new_height/2)

        if clip.w != self.config.width or clip.h != self.config.height:
            clip = clip.resized(new_size=(self.config.width, self.config.height))

        return clip

    def _add_subtitles(self, video: VideoFileClip, subtitles: list[dict]) -> CompositeVideoClip:
        txt_clips = []

        for sub in subtitles:
            txt = TextClip(
                text=sub["text"],
                font_size=self.config.font_size,
                color=self.config.text_color,
                font=self.config.font,
                stroke_color="black",
                stroke_width=2,
                method="caption",
                size=(self.config.width - 200, None),
            )
            txt = txt.with_position(("center", self.config.height - 150))
            txt = txt.with_start(sub["start"])
            txt = txt.with_duration(sub["duration"])
            txt_clips.append(txt)

        return CompositeVideoClip([video] + txt_clips)

    def _add_key_phrases(self, video: VideoFileClip, key_phrases: list[dict]) -> CompositeVideoClip:
        phrase_clips = []

        for phrase in key_phrases:
            font_size = 72 if self.config.is_short else 90
            if len(phrase["text"]) > 20:
                font_size = int(font_size * 0.7)

            txt = TextClip(
                text=phrase["text"].upper(),
                font_size=font_size,
                color="white",
                font=self.config.font,
                stroke_color="black",
                stroke_width=4,
                method="caption",
                size=(self.config.width - 150, None),
            )

            y_pos = self.config.height // 3
            txt = txt.with_position(("center", y_pos))
            txt = txt.with_start(phrase["start"])
            txt = txt.with_duration(phrase["duration"])

            phrase_clips.append(txt)

        return CompositeVideoClip([video] + phrase_clips)

    def composite_with_overlays(
        self,
        base_video_path: str,
        segment_images: list[dict],
        output_path: str,
        overlay_style: str = "pip",
    ) -> str:
        base = VideoFileClip(base_video_path)
        base = self._fit_clip(base)
        overlay_clips = []

        chunks_dir = Path(base_video_path).parent / "video_chunks"
        seam_times = []
        if chunks_dir.exists():
            chunk_files = sorted(chunks_dir.glob("chunk_*.mp4"))
            cumulative = 0.0
            for chunk_file in chunk_files[:-1]:
                chunk_clip = VideoFileClip(str(chunk_file))
                cumulative += chunk_clip.duration
                seam_times.append(cumulative)
                chunk_clip.close()
            print(f"      Found {len(seam_times)} seams at: {[f'{t:.1f}s' for t in seam_times]}")

        image_paths = [seg.get("image_path") for seg in segment_images if seg.get("image_path") and Path(seg.get("image_path")).exists()]

        for i, seam_time in enumerate(seam_times):
            img_path = image_paths[i % len(image_paths)] if image_paths else None
            if not img_path:
                continue

            img = ImageClip(img_path)
            img = self._fit_clip(img)
            fade_duration = 0.5
            cutaway_duration = 3.0
            cutaway_start = seam_time - 1.5
            img = img.with_duration(cutaway_duration)
            img = img.with_effects([vfx.CrossFadeIn(fade_duration), vfx.CrossFadeOut(fade_duration)])
            img = img.with_start(max(0, cutaway_start))
            img = img.with_position("center")
            overlay_clips.append(img)

        if overlay_clips:
            final = CompositeVideoClip(
                [base] + overlay_clips,
                size=(self.config.width, self.config.height)
            )
        else:
            final = base

        final.write_videofile(
            output_path,
            fps=self.config.fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="medium",
        )

        base.close()
        final.close()
        for clip in overlay_clips:
            clip.close()

        return output_path

    def create_thumbnail(
        self,
        text: str,
        background_path: str = None,
        output_path: str = None,
        project_dir: str = None,
    ) -> str:
        from PIL import Image, ImageDraw, ImageFont, ImageEnhance

        if output_path is None:
            output_path = str(Path(config.output_dir) / "thumbnail.png")

        width, height = self.config.width, self.config.height

        podcast_logo_path = Path(config.assets_dir) / "deep_dive_logo.png"
        if podcast_logo_path.exists():
            bg = Image.open(podcast_logo_path).convert("RGB")
            bg_ratio = bg.width / bg.height
            target_ratio = width / height
            if bg_ratio > target_ratio:
                new_width = int(bg.height * target_ratio)
                left = (bg.width - new_width) // 2
                bg = bg.crop((left, 0, left + new_width, bg.height))
            else:
                new_height = int(bg.width / target_ratio)
                top = (bg.height - new_height) // 2
                bg = bg.crop((0, top, bg.width, top + new_height))
            bg = bg.resize((width, height), Image.LANCZOS)
            bg = ImageEnhance.Brightness(bg).enhance(0.7)
        else:
            bg = Image.new("RGB", (width, height), (15, 25, 45))

        gradient = Image.new("RGBA", (width, height // 2), (0, 0, 0, 0))
        draw_grad = ImageDraw.Draw(gradient)
        for y in range(height // 2):
            alpha = int(200 * (y / (height // 2)))
            draw_grad.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
        bg.paste(gradient, (0, height // 2), gradient)

        draw = ImageDraw.Draw(bg)

        try:
            topic_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Impact.ttf", 120)
        except:
            topic_font = ImageFont.load_default()

        topic_text = text.upper()
        max_width = width - 80
        words = topic_text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=topic_font)
            if bbox[2] - bbox[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))

        line_height = 130
        total_text_height = len(lines) * line_height
        start_y = height - total_text_height - 60

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=topic_font)
            line_width = bbox[2] - bbox[0]
            x = (width - line_width) // 2
            y = start_y + i * line_height

            for ox, oy in [(5, 5), (-5, -5), (5, -5), (-5, 5), (0, 6), (6, 0)]:
                draw.text((x + ox, y + oy), line, font=topic_font, fill=(0, 0, 0))
            draw.text((x, y), line, font=topic_font, fill=(255, 255, 255))

        bg.save(output_path, "PNG", quality=95)
        return output_path
