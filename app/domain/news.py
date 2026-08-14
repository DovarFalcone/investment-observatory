from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.domain.types import NewsArticle


def news_group_key(title: str) -> str:
    words = "".join(character.lower() if character.isalnum() else " " for character in title).split()
    stop_words = {"the", "a", "an", "to", "of", "and", "for", "on", "in"}
    return " ".join(word for word in words if word not in stop_words)[:180]


def group_recent_news(articles: Iterable[NewsArticle], hours: int = 72) -> list[list[NewsArticle]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    groups: dict[str, list[NewsArticle]] = {}
    for article in articles:
        if article.published_at and article.published_at < cutoff:
            continue
        groups.setdefault(news_group_key(article.title), []).append(article)
    return sorted(groups.values(), key=lambda group: max((item.published_at or datetime.min) for item in group), reverse=True)
