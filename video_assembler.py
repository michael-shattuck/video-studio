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
        overlay_clips = []

        for seg in segment_images:
            image_path = seg.get("image_path")
            start_time = seg.get("start", 0)
            duration = seg.get("duration", 5)

            if not image_path or not Path(image_path).exists():
                continue

            img = ImageClip(image_path)

            if overlay_style == "pip":
                pip_width = int(self.config.width * 0.35)
                img = img.resized(width=pip_width)
                margin = 30
                overlay_duration = min(duration - 1, duration * 0.8)
                img = img.with_duration(overlay_duration)
                img = img.with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)])
                img = img.with_start(start_time + 0.5)
                img = img.with_position((self.config.width - pip_width - margin, margin))

            elif overlay_style == "cutaway":
                img = self._fit_clip(img)
                cutaway_duration = min(2.5, duration * 0.4)
                img = img.with_duration(cutaway_duration)
                img = img.with_effects([vfx.CrossFadeIn(0.2), vfx.CrossFadeOut(0.2)])
                img = img.with_start(start_time + duration * 0.3)

            elif overlay_style == "split":
                half_width = self.config.width // 2
                img = img.resized(width=half_width)
                img_height = int(half_width * img.h / img.w)
                y_pos = (self.config.height - img_height) // 2
                img = img.with_duration(duration)
                img = img.with_start(start_time)
                img = img.with_position((half_width, y_pos))

            elif overlay_style == "kenburns":
                img = self._fit_clip(img)
                img = img.with_duration(duration)
                img = img.resized(lambda t: 1 + 0.03 * t)
                img = img.with_effects([vfx.CrossFadeIn(0.4), vfx.CrossFadeOut(0.4)])
                img = img.with_start(start_time)
                img = img.with_position("center")

            overlay_clips.append(img)

        if overlay_clips:
            final = CompositeVideoClip([base] + overlay_clips)
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
        output_path: str = None
    ) -> str:
        if output_path is None:
            output_path = str(Path(config.output_dir) / "thumbnail.png")

        if background_path and Path(background_path).exists():
            if background_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                bg_clip = ImageClip(background_path).with_duration(1)
            else:
                bg = VideoFileClip(background_path).get_frame(0)
                bg_clip = ImageClip(bg).with_duration(1)
            bg_clip = self._fit_clip(bg_clip)
        else:
            bg_clip = ColorClip(
                size=(self.config.width, self.config.height),
                color=(20, 20, 40),
                duration=1
            )

        words = text.upper().split()
        if len(words) > 4:
            mid = len(words) // 2
            text = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
        else:
            text = text.upper()

        font_size = 100 if len(text) < 20 else 80 if len(text) < 30 else 60

        txt = TextClip(
            text=text,
            font_size=font_size,
            color="yellow",
            font=self.config.font,
            stroke_color="black",
            stroke_width=5,
            method="caption",
            size=(self.config.width - 200, None),
        )
        txt = txt.with_position("center")

        composite = CompositeVideoClip([bg_clip, txt])
        composite.save_frame(output_path, t=0)

        bg_clip.close()
        composite.close()

        return output_path
