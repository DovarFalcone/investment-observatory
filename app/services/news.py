
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NewsItem, NewsSecurityLink, Security
from app.domain.news import news_group_key
from app.providers.registry import news_provider


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


def recent_news(db: Session, security_id: int | None = None, limit: int = 12) -> list[NewsItem]:
    query = select(NewsItem).order_by(NewsItem.published_at.desc().nullslast()).limit(limit)
    if security_id is not None:
        query = query.join(NewsItem.security_links).where(NewsSecurityLink.security_id == security_id)
    return list(db.scalars(query).unique().all())
