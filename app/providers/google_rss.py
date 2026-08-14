from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser
import httpx

from app.config import settings
from app.domain.types import NewsArticle
from app.providers.base import NewsProvider


class GoogleRssNewsProvider(NewsProvider):
    """Headline/link adapter; article bodies are never copied into the app."""

    name = "google_rss"
    base_url = "https://news.google.com/rss/search"

    def recent(self, symbol: str, name: str) -> list[NewsArticle]:
        query = quote_plus(f'"{symbol}" {name}')
        try:
            response = httpx.get(
                self.base_url,
                params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
                headers={"User-Agent": settings.user_agent},
                timeout=settings.http_timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        parsed = feedparser.parse(response.content)
        articles: list[NewsArticle] = []
        for entry in parsed.entries[:20]:
            published_at = self._published_at(entry)
            articles.append(
                NewsArticle(
                    url=str(entry.get("link", "")),
                    title=str(entry.get("title", "")).strip(),
                    publisher=self._publisher(entry),
                    published_at=published_at,
                    excerpt=None,
                    security_symbol=symbol,
                    source=self.name,
                )
            )
        return [article for article in articles if article.url and article.title]

    @staticmethod
    def _published_at(entry: dict) -> datetime | None:
        value = entry.get("published") or entry.get("updated")
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _publisher(entry: dict) -> str | None:
        source = entry.get("source")
        if isinstance(source, dict):
            return source.get("title")
        return None
