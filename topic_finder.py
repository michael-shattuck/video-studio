import asyncio
import aiohttp
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import json
import re

from .config import config


@dataclass
class TrendingTopic:
    title: str
    source: str
    score: float
    category: str
    controversy_score: float
    url: str = ""
    description: str = ""


class TopicFinder:
    def __init__(self):
        self.cache_dir = Path(config.cache_dir) / "topics"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def find_topics(self, limit: int = 20, filter_sports: bool = True) -> list[TrendingTopic]:
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_reddit_controversial(session),
                self._fetch_google_trends(session),
                self._fetch_news_headlines(session),
                self._fetch_youtube_trending(session),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_topics = []
        for result in results:
            if isinstance(result, list):
                all_topics.extend(result)
            elif isinstance(result, Exception):
                print(f"    Warning: {result}")

        if filter_sports:
            sports_keywords = [
                "vs", "game", "match", "score", "playoff", "championship",
                "nba", "nfl", "mlb", "nhl", "premier league", "serie a",
                "lazio", "milan", "mavericks", "cavaliers", "lakers", "celtics",
                "golf", "tennis", "basketball", "football", "soccer", "baseball",
                "olympics", "fifa", "fiba", "pga", "tour", "fleetwood", "macintyre"
            ]
            all_topics = [
                t for t in all_topics
                if not any(kw in t.title.lower() for kw in sports_keywords)
            ]

        all_topics.sort(key=lambda x: x.score * x.controversy_score, reverse=True)

        seen_titles = set()
        unique_topics = []
        for topic in all_topics:
            normalized = self._normalize_title(topic.title)
            if normalized not in seen_titles:
                seen_titles.add(normalized)
                unique_topics.append(topic)

        return unique_topics[:limit]

    def _normalize_title(self, title: str) -> str:
        return re.sub(r'[^a-z0-9]', '', title.lower())

    async def _fetch_reddit_controversial(self, session: aiohttp.ClientSession) -> list[TrendingTopic]:
        topics = []
        subreddits = [
            "news", "worldnews", "politics", "technology",
            "science", "economics", "unpopularopinion"
        ]

        for subreddit in subreddits:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/controversial/.json?t=week&limit=10"
                headers = {"User-Agent": "VideoStudio/1.0"}
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for post in data.get("data", {}).get("children", []):
                            p = post.get("data", {})
                            score = p.get("score", 0)
                            comments = p.get("num_comments", 0)
                            ratio = p.get("upvote_ratio", 0.5)
                            controversy = 1 - abs(ratio - 0.5) * 2

                            topics.append(TrendingTopic(
                                title=p.get("title", ""),
                                source=f"reddit/{subreddit}",
                                score=score + comments * 2,
                                category=subreddit,
                                controversy_score=controversy,
                                url=f"https://reddit.com{p.get('permalink', '')}",
                                description=p.get("selftext", "")[:200]
                            ))
            except Exception as e:
                print(f"    Reddit {subreddit} error: {e}")

        return topics

    async def _fetch_google_trends(self, session: aiohttp.ClientSession) -> list[TrendingTopic]:
        topics = []
        try:
            url = "https://trends.google.com/trending/rss?geo=US"
            async with session.get(url) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    titles = re.findall(r'<title>([^<]+)</title>', text)
                    for i, title in enumerate(titles[1:20]):
                        topics.append(TrendingTopic(
                            title=title,
                            source="google_trends",
                            score=1000 - i * 50,
                            category="trending",
                            controversy_score=0.7,
                            url="",
                            description=""
                        ))
        except Exception as e:
            print(f"    Google Trends error: {e}")

        return topics

    async def _fetch_news_headlines(self, session: aiohttp.ClientSession) -> list[TrendingTopic]:
        topics = []

        feeds = [
            ("https://feeds.bbci.co.uk/news/rss.xml", "bbc"),
            ("https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "nytimes"),
            ("https://feeds.npr.org/1001/rss.xml", "npr"),
        ]

        controversial_keywords = [
            "war", "conflict", "controversy", "debate", "crisis", "scandal",
            "protest", "ban", "strike", "investigation", "accused", "fired",
            "court", "lawsuit", "abortion", "gun", "immigration", "election",
            "trump", "biden", "israel", "ukraine", "russia", "china", "iran",
            "ai", "layoff", "recession", "inflation", "climate"
        ]

        for feed_url, source in feeds:
            try:
                async with session.get(feed_url) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        items = re.findall(r'<item>.*?<title>([^<]+)</title>.*?</item>', text, re.DOTALL)

                        for i, title in enumerate(items[:15]):
                            title_lower = title.lower()
                            keyword_matches = sum(1 for k in controversial_keywords if k in title_lower)
                            controversy = min(1.0, 0.3 + keyword_matches * 0.15)

                            topics.append(TrendingTopic(
                                title=title,
                                source=source,
                                score=500 - i * 20,
                                category="news",
                                controversy_score=controversy,
                                url="",
                                description=""
                            ))
            except Exception as e:
                print(f"    News feed {source} error: {e}")

        return topics

    async def _fetch_youtube_trending(self, session: aiohttp.ClientSession) -> list[TrendingTopic]:
        topics = []

        try:
            url = "https://www.youtube.com/feed/trending"
            headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"', text)

                    for i, title in enumerate(titles[:20]):
                        topics.append(TrendingTopic(
                            title=title,
                            source="youtube",
                            score=800 - i * 30,
                            category="video",
                            controversy_score=0.5,
                            url="",
                            description=""
                        ))
        except Exception as e:
            print(f"    YouTube error: {e}")

        return topics

    def suggest_angles(self, topic: TrendingTopic) -> list[str]:
        base = topic.title
        return [
            f"{base}",
            f"The truth about {base.lower()}",
            f"Why {base.lower()} is more complicated than you think",
            f"{base}: Both sides are wrong",
            f"What nobody is saying about {base.lower()}",
        ]

    def get_evergreen_controversial(self) -> list[dict]:
        return [
            {"topic": "Is college worth it anymore?", "category": "economics"},
            {"topic": "Should we defund the police?", "category": "politics"},
            {"topic": "Is social media making us dumber?", "category": "technology"},
            {"topic": "Should billionaires exist?",  "category": "economics"},
            {"topic": "Is remote work killing productivity?", "category": "work"},
            {"topic": "Should we ban TikTok?", "category": "technology"},
            {"topic": "Is AI going to replace your job?", "category": "technology"},
            {"topic": "Should voting be mandatory?", "category": "politics"},
            {"topic": "Is cancel culture out of control?", "category": "culture"},
            {"topic": "Should we abolish the death penalty?", "category": "justice"},
            {"topic": "Is the housing market rigged?", "category": "economics"},
            {"topic": "Should we have universal basic income?", "category": "economics"},
            {"topic": "Is climate change already too late to fix?", "category": "science"},
            {"topic": "Should parents be able to track their kids' phones?", "category": "parenting"},
            {"topic": "Is meritocracy a myth?", "category": "culture"},
            {"topic": "Should there be an age limit for politicians?",  "category": "politics"},
            {"topic": "Is the two-party system broken?", "category": "politics"},
            {"topic": "Should we legalize all drugs?", "category": "policy"},
            {"topic": "Is hustle culture toxic?", "category": "work"},
            {"topic": "Should zoos exist?", "category": "ethics"},
            {"topic": "Is therapy overrated?", "category": "health"},
            {"topic": "Should student debt be forgiven?", "category": "economics"},
            {"topic": "Is monogamy outdated?", "category": "relationships"},
            {"topic": "Should we eat the rich?", "category": "economics"},
            {"topic": "Is true crime content exploitative?", "category": "media"},
        ]

    async def get_topics_for_video(self, count: int = 10) -> list[dict]:
        topics = await self.find_topics(limit=count * 2)

        results = []
        for topic in topics[:count]:
            results.append({
                "topic": topic.title,
                "source": topic.source,
                "controversy_score": round(topic.controversy_score, 2),
                "suggested_angles": self.suggest_angles(topic),
                "category": topic.category,
            })

        return results


async def main():
    finder = TopicFinder()
    print("Finding trending controversial topics...\n")

    topics = await finder.get_topics_for_video(count=15)

    for i, t in enumerate(topics, 1):
        print(f"{i}. [{t['source']}] {t['topic']}")
        print(f"   Controversy: {t['controversy_score']} | Category: {t['category']}")
        print(f"   Angles: {t['suggested_angles'][0]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
