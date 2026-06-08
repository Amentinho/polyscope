"""News ingestion from multiple sources."""

import os
import time
import feedparser
import httpx
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Iterator


@dataclass
class NewsItem:
    id: str
    title: str
    body: str
    url: str
    source: str
    published_at: datetime
    category: str  # politics, finance, sports, science, crypto, etc.


RSS_FEEDS = {
    "politics": [
        "https://feeds.reuters.com/reuters/politicsNews",
        "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
        "https://feeds.bbci.co.uk/news/politics/rss.xml",
    ],
    "world": [
        "https://feeds.reuters.com/reuters/worldNews",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    ],
    "finance": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.wsj.com/wsj/xml/rss/3_7031.xml",
    ],
    "crypto": [
        "https://cointelegraph.com/rss",
        "https://coindesk.com/arc/outboundfeeds/rss/",
    ],
    "science": [
        "https://feeds.reuters.com/reuters/scienceNews",
    ],
    "sports": [
        "https://feeds.bbci.co.uk/sport/rss.xml",
        "https://www.espn.com/espn/rss/news",
    ],
}


def _parse_date(entry) -> datetime:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def fetch_rss(max_per_feed: int = 10) -> Iterator[NewsItem]:
    for category, urls in RSS_FEEDS.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_per_feed]:
                    body = ""
                    if hasattr(entry, "summary"):
                        body = entry.summary
                    elif hasattr(entry, "description"):
                        body = entry.description
                    yield NewsItem(
                        id=entry.get("id", entry.get("link", "")),
                        title=entry.get("title", ""),
                        body=body,
                        url=entry.get("link", ""),
                        source=feed.feed.get("title", url),
                        published_at=_parse_date(entry),
                        category=category,
                    )
            except Exception as e:
                print(f"[ingester] RSS error {url}: {e}")


def fetch_newsapi(query: str = "top headlines", max_results: int = 50) -> Iterator[NewsItem]:
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        return
    try:
        resp = httpx.get(
            "https://newsapi.org/v2/top-headlines",
            params={"apiKey": api_key, "pageSize": max_results, "language": "en"},
            timeout=10,
        )
        resp.raise_for_status()
        for article in resp.json().get("articles", []):
            yield NewsItem(
                id=article.get("url", ""),
                title=article.get("title", ""),
                body=article.get("description") or article.get("content") or "",
                url=article.get("url", ""),
                source=article.get("source", {}).get("name", "NewsAPI"),
                published_at=datetime.fromisoformat(
                    article.get("publishedAt", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")
                ),
                category="general",
            )
    except Exception as e:
        print(f"[ingester] NewsAPI error: {e}")


def fetch_all(max_age_hours: int = 6) -> list[NewsItem]:
    cutoff = time.time() - max_age_hours * 3600
    items = []
    seen = set()
    for item in fetch_rss():
        if item.id not in seen and item.published_at.timestamp() > cutoff:
            seen.add(item.id)
            items.append(item)
    for item in fetch_newsapi():
        if item.id not in seen and item.published_at.timestamp() > cutoff:
            seen.add(item.id)
            items.append(item)
    return items
