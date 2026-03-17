import asyncio
import aiohttp
import hashlib
import subprocess
from pathlib import Path
from dataclasses import dataclass

from .config import config


@dataclass
class VideoClip:
    id: str
    url: str
    width: int
    height: int
    duration: int
    local_path: str = ""
    source: str = "pixabay"
    page_url: str = ""


@dataclass
class ImageAsset:
    id: str
    url: str
    width: int
    height: int
    local_path: str = ""
    source: str = "pixabay"
    page_url: str = ""


class PixabayClient:
    def __init__(self):
        self.api_key = config.pixabay_api_key
        self.base_url = "https://pixabay.com/api"

    async def search_videos(self, query: str, per_page: int = 10) -> list[VideoClip]:
        if not self.api_key:
            return []

        params = {
            "key": self.api_key,
            "q": query,
            "video_type": "all",
            "per_page": min(per_page, 200),
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/videos/", params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

        clips = []
        for hit in data.get("hits", []):
            videos = hit.get("videos", {})
            large = videos.get("large", {}) or videos.get("medium", {})
            if large.get("url"):
                clips.append(VideoClip(
                    id=str(hit["id"]),
                    url=large["url"],
                    width=large.get("width", 1920),
                    height=large.get("height", 1080),
                    duration=hit.get("duration", 10),
                    source="pixabay",
                    page_url=hit.get("pageURL", f"https://pixabay.com/videos/id-{hit['id']}/"),
                ))

        return clips

    async def search_images(self, query: str, per_page: int = 10, vertical: bool = False) -> list[ImageAsset]:
        if not self.api_key:
            return []

        params = {
            "key": self.api_key,
            "q": query,
            "image_type": "photo",
            "orientation": "vertical" if vertical else "horizontal",
            "per_page": min(per_page, 200),
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

        images = []
        for hit in data.get("hits", []):
            images.append(ImageAsset(
                id=str(hit["id"]),
                url=hit.get("largeImageURL", hit.get("webformatURL", "")),
                width=hit.get("imageWidth", 1920),
                height=hit.get("imageHeight", 1080),
                source="pixabay",
                page_url=hit.get("pageURL", f"https://pixabay.com/photos/id-{hit['id']}/"),
            ))

        return images

    async def download_clip(self, clip: VideoClip, output_dir: str = None) -> str:
        if output_dir is None:
            output_dir = Path(config.cache_dir) / "footage"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"pixabay_{clip.id}.mp4"
        output_path = output_dir / filename

        if output_path.exists():
            clip.local_path = str(output_path)
            return str(output_path)

        async with aiohttp.ClientSession() as session:
            async with session.get(clip.url) as resp:
                if resp.status != 200:
                    return ""
                content = await resp.read()

        with open(output_path, "wb") as f:
            f.write(content)

        clip.local_path = str(output_path)
        return str(output_path)

    async def download_image(self, image: ImageAsset, output_dir: str = None) -> str:
        if output_dir is None:
            output_dir = Path(config.cache_dir) / "images"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"pixabay_{image.id}.jpg"
        output_path = output_dir / filename

        if output_path.exists():
            image.local_path = str(output_path)
            return str(output_path)

        async with aiohttp.ClientSession() as session:
            async with session.get(image.url) as resp:
                if resp.status != 200:
                    return ""
                content = await resp.read()

        with open(output_path, "wb") as f:
            f.write(content)

        image.local_path = str(output_path)
        return str(output_path)


class PexelsClient:
    def __init__(self):
        self.api_key = config.pexels_api_key
        self.base_url = "https://api.pexels.com"

    async def search_videos(self, query: str, per_page: int = 15, orientation: str = "landscape") -> list[VideoClip]:
        if not self.api_key:
            return []

        headers = {"Authorization": self.api_key}
        params = {
            "query": query,
            "per_page": per_page,
            "orientation": orientation,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/videos/search",
                headers=headers,
                params=params
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

        clips = []
        for video in data.get("videos", []):
            best_file = None
            for vf in video.get("video_files", []):
                if vf.get("quality") == "hd" and vf.get("width", 0) >= 1280:
                    best_file = vf
                    break
            if not best_file and video.get("video_files"):
                best_file = video["video_files"][0]

            if best_file:
                clips.append(VideoClip(
                    id=str(video["id"]),
                    url=best_file["link"],
                    width=best_file.get("width", 1920),
                    height=best_file.get("height", 1080),
                    duration=video.get("duration", 10),
                ))

        return clips

    async def download_clip(self, clip: VideoClip, output_dir: str = None) -> str:
        if output_dir is None:
            output_dir = Path(config.cache_dir) / "footage"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"pexels_{clip.id}.mp4"
        output_path = output_dir / filename

        if output_path.exists():
            clip.local_path = str(output_path)
            return str(output_path)

        async with aiohttp.ClientSession() as session:
            async with session.get(clip.url) as resp:
                if resp.status != 200:
                    return ""
                content = await resp.read()

        with open(output_path, "wb") as f:
            f.write(content)

        clip.local_path = str(output_path)
        return str(output_path)


class AIImageGenerator:
    def __init__(self):
        self.cache_dir = Path(config.cache_dir) / "ai_images"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.image_counter = 0

    async def generate(self, prompt: str, output_path: str = None, vertical: bool = False) -> str:
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:12]
        suffix = "_v" if vertical else ""
        if output_path is None:
            output_path = str(self.cache_dir / f"{prompt_hash}{suffix}.jpg")

        if Path(output_path).exists():
            return output_path

        self.image_counter += 1
        seed = hash(prompt) % 10000

        if vertical:
            url = f"https://picsum.photos/seed/{seed}/1080/1920"
        else:
            url = f"https://picsum.photos/seed/{seed}/1920/1080"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    with open(output_path, "wb") as f:
                        f.write(content)
                    return output_path

        return ""


class DalleImageGenerator:
    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else None
        self.endpoint = config.azure_openai_foundry_endpoint
        self.key = config.azure_openai_foundry_key
        self.last_request_time = 0
        self.min_delay = 10
        self.max_retries = 3

    def set_output_dir(self, output_dir: str):
        self.output_dir = Path(output_dir) / "dalle_images"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        return bool(self.endpoint and self.key)

    def _enhance_prompt(self, visual_cue: str, vertical: bool = False) -> str:
        return f"{visual_cue}. High quality digital illustration, professional video thumbnail style, dramatic lighting, no text or watermarks"

    async def generate(self, visual_cue: str, output_path: str = None, vertical: bool = False) -> str:
        if not self.available:
            return ""

        if not self.output_dir:
            raise RuntimeError("DalleImageGenerator.output_dir not set. Call set_output_dir() first.")

        prompt_hash = hashlib.md5(visual_cue.encode()).hexdigest()[:12]
        suffix = "_v" if vertical else ""
        if output_path is None:
            output_path = str(self.output_dir / f"dalle_{prompt_hash}{suffix}.png")

        if Path(output_path).exists():
            return output_path

        import time
        import base64

        enhanced_prompt = self._enhance_prompt(visual_cue, vertical)
        size = "1024x1024"
        gen_url = f"{self.endpoint}openai/deployments/gpt-image/images/generations?api-version=2024-05-01-preview"

        for attempt in range(self.max_retries):
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_delay:
                await asyncio.sleep(self.min_delay - elapsed)

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        gen_url,
                        headers={"api-key": self.key, "Content-Type": "application/json"},
                        json={
                            "prompt": enhanced_prompt,
                            "n": 1,
                            "size": size,
                            "quality": "high"
                        },
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as resp:
                        self.last_request_time = time.time()
                        if resp.status == 200:
                            result = await resp.json()
                            img_b64 = result.get("data", [{}])[0].get("b64_json")
                            if img_b64:
                                with open(output_path, "wb") as f:
                                    f.write(base64.b64decode(img_b64))
                                return output_path
                        elif resp.status == 429:
                            retry_after = int(resp.headers.get("Retry-After", 30 * (attempt + 1)))
                            print(f"      Rate limited, waiting {retry_after}s (attempt {attempt + 1}/{self.max_retries})")
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            error_text = await resp.text()
                            print(f"      DALL-E error ({resp.status}): {error_text[:100]}")
                            break
            except Exception as e:
                print(f"      DALL-E exception: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(10 * (attempt + 1))
                    continue
                break

        return ""

    async def generate_batch(self, visual_cues: list[str], vertical: bool = False) -> dict[str, str]:
        results = {}
        for i, cue in enumerate(visual_cues):
            print(f"      Generating image {i+1}/{len(visual_cues)}: {cue[:50]}...")
            path = await self.generate(cue, vertical=vertical)
            if path:
                results[cue] = path
        return results


class StockFootageManager:
    def __init__(self, vertical: bool = False, use_dalle: bool = True, output_dir: str = None):
        self.pixabay = PixabayClient()
        self.pexels = PexelsClient()
        self.ai_gen = AIImageGenerator()
        self.dalle_gen = DalleImageGenerator()
        self.use_dalle = use_dalle and self.dalle_gen.available
        self.used_assets: list[dict] = []
        self.vertical = vertical
        if output_dir:
            self.set_output_dir(output_dir)

    def set_output_dir(self, output_dir: str):
        self.dalle_gen.set_output_dir(output_dir)

    def get_attribution_text(self) -> str:
        if not self.used_assets:
            return ""

        pixabay_ids = set()
        for asset in self.used_assets:
            if asset.get("source") == "pixabay":
                pixabay_ids.add(asset.get("id"))

        if pixabay_ids:
            return f"Stock footage provided by Pixabay (https://pixabay.com). License: https://pixabay.com/service/license-summary/"
        return ""

    def get_attribution_links(self) -> list[str]:
        links = []
        seen = set()
        for asset in self.used_assets:
            if asset.get("page_url") and asset.get("page_url") not in seen:
                seen.add(asset.get("page_url"))
                links.append(asset.get("page_url"))
        return links

    async def get_footage_for_cues(self, visual_cues: list[str], clips_per_cue: int = 3) -> dict[str, list[VideoClip]]:
        footage = {}

        for cue in visual_cues:
            search_terms = self._extract_search_terms(cue)
            clips = []

            orientation = "portrait" if self.vertical else "landscape"
            for term in search_terms[:2]:
                if config.pixabay_api_key:
                    results = await self.pixabay.search_videos(term, per_page=clips_per_cue)
                    clips.extend(results)
                elif config.pexels_api_key:
                    results = await self.pexels.search_videos(term, per_page=clips_per_cue, orientation=orientation)
                    clips.extend(results)

                if len(clips) >= clips_per_cue:
                    break
                await asyncio.sleep(0.2)

            footage[cue] = clips[:clips_per_cue]

        return footage

    async def get_images_for_cues(self, visual_cues: list[str], images_per_cue: int = 1) -> dict[str, list[str]]:
        images = {}

        if self.use_dalle:
            print(f"      Using DALL-E for {len(visual_cues)} visual cues...")
            for i, cue in enumerate(visual_cues):
                print(f"      [{i+1}/{len(visual_cues)}] {cue[:60]}...")
                path = await self.dalle_gen.generate(cue, vertical=self.vertical)
                if path:
                    images[cue] = [path]
                    self.used_assets.append({
                        "id": hashlib.md5(cue.encode()).hexdigest()[:12],
                        "source": "dalle",
                        "type": "image",
                    })
                else:
                    images[cue] = []
            return images

        for cue in visual_cues:
            search_terms = self._extract_search_terms(cue)
            cue_images = []

            for term in search_terms[:2]:
                if config.pixabay_api_key:
                    results = await self.pixabay.search_images(term, per_page=images_per_cue, vertical=self.vertical)
                    for img in results:
                        path = await self.pixabay.download_image(img)
                        if path:
                            cue_images.append(path)
                            self.used_assets.append({
                                "id": img.id,
                                "source": img.source,
                                "page_url": img.page_url,
                                "type": "image",
                            })
                else:
                    path = await self.ai_gen.generate(term, vertical=self.vertical)
                    if path:
                        cue_images.append(path)

                if len(cue_images) >= images_per_cue:
                    break
                await asyncio.sleep(0.3)

            images[cue] = cue_images[:images_per_cue]

        return images

    async def download_all(self, footage: dict[str, list[VideoClip]]) -> dict[str, list[str]]:
        paths = {}

        for cue, clips in footage.items():
            cue_paths = []
            for clip in clips:
                if config.pixabay_api_key:
                    path = await self.pixabay.download_clip(clip)
                else:
                    path = await self.pexels.download_clip(clip)
                if path:
                    cue_paths.append(path)
                    self.used_assets.append({
                        "id": clip.id,
                        "source": clip.source,
                        "page_url": clip.page_url,
                        "type": "video",
                    })
            paths[cue] = cue_paths

        return paths

    def _extract_search_terms(self, cue: str) -> list[str]:
        cue_lower = cue.lower()

        skip_words = {
            "show", "display", "footage", "video", "clip", "image", "visual",
            "of", "the", "a", "an", "with", "showing", "depicting", "featuring",
            "related", "to", "about", "some", "various", "different", "multiple",
            "scene", "shot", "shots", "scenes", "showing", "illustrating",
            "demonstrating", "people", "person", "thing", "things", "example",
            "examples", "like", "such", "as", "etc", "other", "others", "more",
            "many", "few", "several", "lots", "bunch", "group", "groups",
            "being", "doing", "having", "getting", "making", "using", "taking",
            "going", "coming", "looking", "seeing", "watching", "moving",
        }

        cue_clean = cue_lower.replace(",", " ").replace(".", " ").replace("-", " ")
        words = cue_clean.split()
        filtered = [w for w in words if w not in skip_words and len(w) > 2]

        noun_phrases = []
        i = 0
        while i < len(filtered):
            if i + 1 < len(filtered):
                pair = f"{filtered[i]} {filtered[i+1]}"
                noun_phrases.append(pair)
            i += 1

        terms = []

        if len(filtered) >= 2:
            terms.append(f"{filtered[0]} {filtered[1]}")
        if filtered:
            terms.append(filtered[0])

        for phrase in noun_phrases[:2]:
            if phrase not in terms:
                terms.append(phrase)

        if len(filtered) >= 3:
            three_word = f"{filtered[0]} {filtered[1]} {filtered[2]}"
            if three_word not in terms:
                terms.append(three_word)

        return terms[:4]
