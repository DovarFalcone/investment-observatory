
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NewsItem, NewsSecurityLink, Security
from app.domain.news import news_group_key
from app.providers.registry import news_provider


@dataclass(frozen=True)
class NewsGroup:
    representative: NewsItem
    article_count: int
    source_count: int


def sync_news_for_security(db: Session, security: Security) -> int:
    articles = news_provider().recent(security.canonical_symbol, security.name)
    inserted = 0
    for article in articles:
        existing = db.scalar(select(NewsItem).where(NewsItem.canonical_url == article.url))
        if existing is None:
            existing = NewsItem(
                canonical_url=article.url,
                title=article.title,
                publisher=article.publisher,
                published_at=article.published_at,
                excerpt=article.excerpt,
                source=article.source,
                group_key=news_group_key(article.title),
            )
            db.add(existing)
            db.flush()
            inserted += 1
        linked = db.scalar(
            select(NewsSecurityLink).where(
                NewsSecurityLink.news_id == existing.id,
                NewsSecurityLink.security_id == security.id,
            )
        )
        if linked is None:
            db.add(NewsSecurityLink(news_item=existing, security=security, relevance="symbol"))
    db.commit()
    return inserted


def recent_news(
    db: Session,
    security_id: int | None = None,
    limit: int = 12,
    hours: int = 72,
) -> list[NewsGroup]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = (
        select(NewsItem)
        .where(NewsItem.published_at.is_(None) | (NewsItem.published_at >= cutoff))
        .order_by(NewsItem.published_at.desc().nullslast(), NewsItem.id.desc())
        .limit(max(limit * 4, 24))
    )
    if security_id is not None:
        query = query.join(NewsItem.security_links).where(NewsSecurityLink.security_id == security_id)
    articles = list(db.scalars(query).unique().all())
    grouped: dict[str, list[NewsItem]] = {}
    for article in articles:
        key = article.group_key or f"article:{article.id}"
        grouped.setdefault(key, []).append(article)

    summaries: list[NewsGroup] = []
    for group in grouped.values():
        group.sort(
            key=lambda article: (
                article.published_at is not None,
                article.published_at.timestamp() if article.published_at else float("-inf"),
                article.id,
            ),
            reverse=True,
        )
        sources = {article.publisher or article.source for article in group}
        summaries.append(
            NewsGroup(
                representative=group[0],
                article_count=len(group),
                source_count=len(sources),
            )
        )
    summaries.sort(
        key=lambda summary: (
            summary.representative.published_at is not None,
            summary.representative.published_at.timestamp()
            if summary.representative.published_at
            else float("-inf"),
            summary.representative.id,
        ),
        reverse=True,
    )
    return summaries[:limit]
